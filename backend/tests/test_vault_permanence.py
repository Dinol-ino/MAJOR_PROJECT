"""
Canonical-document permanence, page provenance and vault isolation.

Rules under test (see app/services/document_store.py):
  original file  ->  row  ->  pages  ->  chunks  ->  indexes  ->  caches
Only an explicit delete may remove the original. Cache eviction, index purge/rebuild,
restart recovery and soft-deleting a vault must never touch it.
"""
import io

import fitz
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.engine import get_sync_session
from app.db.models import DocumentMemory, DocumentPage
from app.main import app
from app.services.document_store import DocumentStore, DocumentStoreError, document_store
from app.services.ingest import ingest_service, locate_chunk_pages
from tests.auth_helpers import register_user

client = TestClient(app)


def _pdf(pages):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        y = 72
        for line in text.split("\n"):
            page.insert_text((50, y), line)
            y += 16
    data = doc.write()
    doc.close()
    return data


PAGES_A = [
    "Statement of facts. The appellant Zephyrcorp Industries delivered goods to the respondent.",
    "Analysis. The arbitration clause requires a sole arbitrator seated at Mangaluru harbour.",
    "Conclusion. Damages of quantum meruit are awarded for the marmalade consignment.",
]


def _make_vault(headers, name="Matter"):
    r = client.post("/vaults", json={"vault_name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload(vault_id, headers, pdf, name="case.pdf"):
    r = client.post(f"/vaults/{vault_id}/documents", headers=headers,
                    files={"file": (name, io.BytesIO(pdf), "application/pdf")})
    assert r.status_code == 202, r.text
    return r.json()


def _row(doc_id):
    with get_sync_session() as s:
        d = s.query(DocumentMemory).filter_by(doc_id=doc_id).first()
        return d.to_dict() | {"storage_path": d.storage_path}


def test_original_pdf_is_stored_byte_for_byte_and_downloadable():
    _, h = register_user(client, "perm")
    vault_id = _make_vault(h)
    pdf = _pdf(PAGES_A)
    doc_id = _upload(vault_id, h, pdf)["document_id"]
    row = _row(doc_id)
    assert row["storage_path"] and document_store.exists(row["storage_path"])
    assert document_store.read(row["storage_path"]) == pdf
    assert row["doc_type"] == "pdf" and row["has_original"] is True
    dl = client.get(f"/vaults/{vault_id}/documents/{doc_id}/file", headers=h)
    assert dl.status_code == 200 and dl.content == pdf


def test_ingestion_records_page_provenance_and_parser_version():
    _, h = register_user(client, "prov")
    vault_id = _make_vault(h)
    doc_id = _upload(vault_id, h, _pdf(PAGES_A))["document_id"]
    ingest_service.ingest_document(doc_id=doc_id, vault_id=vault_id, filename="case.pdf")
    row = _row(doc_id)
    assert row["ingest_status"] == "ready" and row["page_count"] == 3
    assert row["parser_version"] and row["indexed_at"]
    hits = ingest_service.query_vault(vault_id, "arbitrator seated Mangaluru harbour", top_k=3)
    assert hits, "vault query returned nothing"
    meta = hits[0]["metadata"]
    assert meta["doc_id"] == doc_id and meta["vault_id"] == vault_id
    assert meta["page_start"] == 2, "the arbitration clause is on page 2"


def test_locate_chunk_pages_reports_missing_instead_of_guessing():
    full = "page one text\n\npage two text"
    offsets = [(0, 13, 1), (15, 28, 2)]
    assert locate_chunk_pages(full, offsets, "page two text")[:2] == (2, 2)
    assert locate_chunk_pages(full, offsets, "not present anywhere in the document")[:2] == (None, None)


def test_index_purge_and_cache_clear_never_delete_the_original_and_reindex_restores_retrieval():
    _, h = register_user(client, "evict")
    vault_id = _make_vault(h)
    pdf = _pdf(PAGES_A)
    doc_id = _upload(vault_id, h, pdf)["document_id"]
    ingest_service.ingest_document(doc_id=doc_id, vault_id=vault_id, filename="case.pdf")
    path = _row(doc_id)["storage_path"]

    from app.cache import l2_retrieval_cache
    l2_retrieval_cache.clear()                                       # cache eviction
    ingest_service.delete_document_vectors(vault_id, doc_id)          # index wipe
    assert ingest_service.query_vault(vault_id, "quantum meruit marmalade", top_k=3) == []
    assert document_store.read(path) == pdf                           # original untouched
    assert _row(doc_id)["file_hash"]                                  # canonical record untouched

    r = client.post(f"/vaults/{vault_id}/documents/{doc_id}/reindex", headers=h)
    assert r.status_code == 202
    ingest_service.ingest_document(doc_id=doc_id, vault_id=vault_id, filename="case.pdf")
    assert ingest_service.query_vault(vault_id, "quantum meruit marmalade", top_k=3)
    with get_sync_session() as s:   # re-indexing replaces pages, it does not duplicate them
        assert s.query(DocumentPage).filter_by(doc_id=doc_id).count() == 3


def test_restart_recovery_resumes_interrupted_ingestion_from_stored_original():
    _, h = register_user(client, "resume")
    vault_id = _make_vault(h)
    doc_id = _upload(vault_id, h, _pdf(PAGES_A))["document_id"]
    with get_sync_session() as s:      # simulate: process died mid-parse
        s.query(DocumentMemory).filter_by(doc_id=doc_id).update({"ingest_status": "parsing", "ingest_progress": 10})
    assert doc_id in ingest_service.resume_incomplete()
    assert _row(doc_id)["ingest_status"] == "ready"


def test_recovery_marks_document_failed_when_original_is_gone():
    _, h = register_user(client, "lost")
    vault_id = _make_vault(h)
    doc_id = _upload(vault_id, h, _pdf(PAGES_A))["document_id"]
    path = _row(doc_id)["storage_path"]
    document_store.delete_document(path)
    with get_sync_session() as s:
        s.query(DocumentMemory).filter_by(doc_id=doc_id).update({"ingest_status": "pending"})
    assert doc_id not in ingest_service.resume_incomplete()
    row = _row(doc_id)
    assert row["ingest_status"] == "failed" and "upload it again" in row["ingest_error"]


def test_soft_delete_keeps_originals_hard_delete_removes_them():
    _, h = register_user(client, "del")
    keep = _make_vault(h, "soft")
    doc_keep = _upload(keep, h, _pdf(PAGES_A))["document_id"]
    p_keep = _row(doc_keep)["storage_path"]
    assert client.delete(f"/vaults/{keep}", headers=h).status_code == 200            # soft (default)
    assert document_store.exists(p_keep), "soft-deleting a vault must not delete originals"

    gone = _make_vault(h, "hard")
    doc_gone = _upload(gone, h, _pdf(PAGES_A[:1]))["document_id"]
    p_gone = _row(doc_gone)["storage_path"]
    assert client.delete(f"/vaults/{gone}?soft_delete=false", headers=h).status_code == 200
    assert not document_store.exists(p_gone)


def test_deleting_one_document_removes_only_its_original():
    _, h = register_user(client, "one")
    vault_id = _make_vault(h)
    a = _upload(vault_id, h, _pdf(PAGES_A), "a.pdf")["document_id"]
    b = _upload(vault_id, h, _pdf(["A different second document about tenancy."]), "b.pdf")["document_id"]
    pa, pb = _row(a)["storage_path"], _row(b)["storage_path"]
    assert client.delete(f"/vaults/{vault_id}/documents/{a}", headers=h).status_code == 200
    assert not document_store.exists(pa) and document_store.exists(pb)


def test_other_users_cannot_download_reindex_or_delete_a_vault_document():
    _, owner = register_user(client, "owner")
    _, intruder = register_user(client, "intruder")
    vault_id = _make_vault(owner)
    doc_id = _upload(vault_id, owner, _pdf(PAGES_A))["document_id"]
    path = _row(doc_id)["storage_path"]
    for method, url in (("get", f"/vaults/{vault_id}/documents/{doc_id}/file"),
                        ("post", f"/vaults/{vault_id}/documents/{doc_id}/reindex"),
                        ("delete", f"/vaults/{vault_id}/documents/{doc_id}"),
                        ("delete", f"/vaults/{vault_id}")):
        assert getattr(client, method)(url, headers=intruder).status_code == 404, (method, url)
    assert document_store.exists(path)


def test_retrieval_never_crosses_vaults():
    _, h = register_user(client, "iso")
    v1, v2 = _make_vault(h, "one"), _make_vault(h, "two")
    d1 = _upload(v1, h, _pdf(PAGES_A))["document_id"]
    d2 = _upload(v2, h, _pdf(["Confidential settlement figure for Quillfeather Holdings is undisclosed."]), "b.pdf")["document_id"]
    ingest_service.ingest_document(doc_id=d1, vault_id=v1, filename="case.pdf")
    ingest_service.ingest_document(doc_id=d2, vault_id=v2, filename="b.pdf")
    leaked = ingest_service.query_vault(v1, "Quillfeather Holdings settlement", top_k=5)
    assert all("Quillfeather" not in (x.get("text") or "") for x in leaked)
    assert ingest_service.query_vault(v2, "Quillfeather Holdings settlement", top_k=5)


def test_oversized_upload_is_rejected_before_it_is_stored(monkeypatch):
    _, h = register_user(client, "big")
    vault_id = _make_vault(h)
    monkeypatch.setattr(settings.retrieval, "max_file_size_mb", 0)
    r = client.post(f"/vaults/{vault_id}/documents", headers=h,
                    files={"file": ("x.pdf", io.BytesIO(_pdf(PAGES_A)), "application/pdf")})
    assert r.status_code == 413


def test_non_pdf_bytes_named_pdf_are_rejected():
    _, h = register_user(client, "fake")
    vault_id = _make_vault(h)
    r = client.post(f"/vaults/{vault_id}/documents", headers=h,
                    files={"file": ("x.pdf", io.BytesIO(b"MZ\x90\x00 not a pdf"), "application/pdf")})
    assert r.status_code == 400


def test_document_store_refuses_path_traversal(tmp_path):
    store = DocumentStore(str(tmp_path))
    for bad in ("../evil", "a/b", "", "x" * 200, "..", "a b"):
        with pytest.raises(DocumentStoreError):
            store.save(bad, "doc1", b"x")
        with pytest.raises(DocumentStoreError):
            store.save("vault1", bad, b"x")
    with pytest.raises(DocumentStoreError):
        store.path("../../etc/passwd")
    assert store.delete_document("../../etc/passwd") is False


def test_citations_carry_document_page_and_source_kind():
    from app.runtime.citation_builder import CitationBuilder
    chunks = [
        {"act": "case.pdf", "section": "Page 2", "text": "clause", "doc_type": "vault_document",
         "metadata": {"doc_id": "d1", "page_start": 2, "page_end": 2, "filename": "case.pdf"}},
        {"act": "case.pdf", "section": "Page 3", "text": "other passage", "doc_type": "vault_document",
         "metadata": {"doc_id": "d1", "page_start": 3, "page_end": 3, "filename": "case.pdf"}},
        {"act": "Indian Contract Act, 1872", "section": "73", "text": "compensation", "doc_type": "statutory_law",
         "metadata": {}},
        {"act": "web-tool", "section": "", "text": "external", "doc_type": "mcp_tool_result", "metadata": {}},
    ]
    cites = CitationBuilder().build(chunks)
    by_kind = {c.source_kind for c in cites}
    assert by_kind == {"user_document", "statute", "external_source"}
    pages = sorted(c.page_start for c in cites if c.source_kind == "user_document")
    assert pages == [2, 3], "two passages of one document must remain two citations"
    assert all(c.doc_id == "d1" for c in cites if c.source_kind == "user_document")


# ---------------------------------------------------------------- relevance gate
def _ready_vault(prefix="rel", pages=None):
    _, h = register_user(client, prefix)
    vault_id = _make_vault(h)
    doc_id = _upload(vault_id, h, _pdf(pages or PAGES_A))["document_id"]
    ingest_service.ingest_document(doc_id=doc_id, vault_id=vault_id, filename="case.pdf")
    return h, vault_id, doc_id


def test_off_topic_query_retrieves_nothing_from_the_vault():
    _, vault_id, _ = _ready_vault("off")
    assert ingest_service.query_vault(vault_id, "What is the capital of France?", top_k=5) == []
    assert ingest_service.query_vault(vault_id, "quantum entanglement in superconductors", top_k=5) == []


def test_on_topic_query_still_finds_the_right_page():
    _, vault_id, _ = _ready_vault("on")
    hits = ingest_service.query_vault(vault_id, "Who is the sole arbitrator and where is the arbitration seated?", top_k=3)
    assert hits and hits[0]["metadata"]["page_start"] == 2


def test_overview_request_serves_leading_passages_in_reading_order():
    _, vault_id, doc_id = _ready_vault("ovw")
    hits = ingest_service.query_vault(vault_id, "Summarise this document", top_k=3)
    assert [h["metadata"]["page_start"] for h in hits] == [1, 2, 3]
    assert all(h["metadata"]["doc_id"] == doc_id for h in hits)


def test_chat_refuses_off_topic_question_instead_of_answering_from_unrelated_pages():
    h, vault_id, _ = _ready_vault("chat")
    r = client.post("/chat", headers=h, json={
        "message": "What is the capital of France?", "session_id": "s_offtopic_1",
        "vault_id": vault_id, "shield_on": True, "reasoning_effort": "off"})
    assert r.status_code == 200
    body = r.json()
    assert body["sources"] == [], "no citation may be shown when nothing supports the answer"
    assert body["failure_kind"] in ("insufficient_evidence", "out_of_scope")


def test_chat_cites_the_exact_page_for_an_on_topic_question():
    h, vault_id, _ = _ready_vault("chat2")
    r = client.post("/chat", headers=h, json={
        "message": "Where is the arbitrator seated under the arbitration clause?", "session_id": "s_ontopic_1",
        "vault_id": vault_id, "shield_on": True, "reasoning_effort": "off"})
    body = r.json()
    user_cites = [s for s in body["sources"] if s["source_kind"] == "user_document"]
    assert user_cites and user_cites[0]["page_start"] == 2 and user_cites[0]["filename"] == "case.pdf"
    assert all(s["page_start"] in (2,) for s in user_cites), "unrelated pages must not be cited"
