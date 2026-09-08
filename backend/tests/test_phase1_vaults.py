import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.ingest import ingest_service
from app.db.engine import get_sync_session
from app.db.models import ProjectVault, Conversation, DocumentMemory, DocumentPage

client = TestClient(app)


def test_vault_crud_lifecycle():
    # 1. Create Vault
    res = client.post("/vaults", json={
        "vault_name": "Test Supreme Court Arbitration",
        "description": "Matter regarding cross-border corporate breach",
        "user_id": "test_advocate"
    })
    assert res.status_code == 201
    vault_data = res.json()
    vault_id = vault_data["id"]
    assert vault_data["vault_name"] == "Test Supreme Court Arbitration"

    # 2. List Vaults
    list_res = client.get("/vaults?user_id=test_advocate")
    assert list_res.status_code == 200
    vaults = list_res.json()["vaults"]
    assert any(v["id"] == vault_id for v in vaults)

    # 3. Get Vault Details
    detail_res = client.get(f"/vaults/{vault_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == vault_id
    assert "conversations" in detail_res.json()
    assert "documents" in detail_res.json()

    # 4. Patch/Rename Vault
    patch_res = client.patch(f"/vaults/{vault_id}", json={
        "vault_name": "Renamed SC Matter 2026",
        "description": "Updated matter overview"
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["vault_name"] == "Renamed SC Matter 2026"

    # 5. Delete Vault
    del_res = client.delete(f"/vaults/{vault_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify not found
    assert client.get(f"/vaults/{vault_id}").status_code == 404


def test_conversation_management_and_rename():
    # 1. Create a parent vault
    v_res = client.post("/vaults", json={
        "vault_name": "High Court IP Dispute",
        "user_id": "test_advocate_2"
    })
    vault_id = v_res.json()["id"]

    # 2. Create conversation in this vault
    c_res = client.post("/conversations", json={
        "project_vault_id": vault_id,
        "title": "Initial Strategy Session",
        "user_id": "test_advocate_2"
    })
    assert c_res.status_code == 201
    conv_data = c_res.json()
    conv_id = conv_data["conversation_id"]
    assert conv_data["project_vault_id"] == vault_id
    assert conv_data["title"] == "Initial Strategy Session"

    # 3. List conversations filtered by vault
    conv_list = client.get(f"/conversations?vault_id={vault_id}&user_id=test_advocate_2")
    assert conv_list.status_code == 200
    assert len(conv_list.json()["conversations"]) == 1
    assert conv_list.json()["conversations"][0]["conversation_id"] == conv_id

    # 4. Rename Conversation (Spec 01 §3.3)
    rename_res = client.patch(f"/conversations/{conv_id}", json={
        "title": "Section 9 Injunction Strategy"
    })
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Section 9 Injunction Strategy"

    # 5. Get full conversation history
    hist_res = client.get(f"/conversations/{conv_id}")
    assert hist_res.status_code == 200
    assert hist_res.json()["title"] == "Section 9 Injunction Strategy"
    assert "messages" in hist_res.json()

    # 6. Delete conversation
    del_res = client.delete(f"/conversations/{conv_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Cleanup vault
    client.delete(f"/vaults/{vault_id}")


def test_vault_document_upload_and_deduplication():
    # Create test vault
    v_res = client.post("/vaults", json={"vault_name": "Contract Review Vault"})
    vault_id = v_res.json()["id"]

    # Minimal valid single-page PDF bytes
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Section 73 Compensation for loss or damage caused by breach of contract.")
    pdf_bytes = doc.write()
    doc.close()

    # 1. Upload Document
    upload_res = client.post(
        f"/vaults/{vault_id}/documents",
        files={"file": ("contract_sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_res.status_code == 202
    u_data = upload_res.json()
    doc_id = u_data["document_id"]
    assert u_data["duplicate"] is False
    assert u_data["status"] == "pending"

    # Synchronously run ingestion to verify pipeline
    ingest_service.ingest_document(
        doc_id=doc_id,
        vault_id=vault_id,
        filename="contract_sample.pdf",
        content=pdf_bytes
    )

    # 2. Check Document Status
    status_res = client.get(f"/vaults/{vault_id}/documents/{doc_id}/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "ready"
    assert status_res.json()["progress"] == 100
    assert status_res.json()["pages"] == 1

    # 3. Test Deduplication: upload exact same file again
    dup_res = client.post(
        f"/vaults/{vault_id}/documents",
        files={"file": ("contract_sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert dup_res.status_code == 202
    assert dup_res.json()["duplicate"] is True
    assert dup_res.json()["document_id"] == doc_id

    # 4. Query Vault Evidence
    evidence = ingest_service.query_vault(vault_id, "compensation for breach")
    assert len(evidence) > 0
    assert "Section 73" in evidence[0]["text"]

    # 5. Delete Document
    del_doc = client.delete(f"/vaults/{vault_id}/documents/{doc_id}")
    assert del_doc.status_code == 200

    # Cleanup
    client.delete(f"/vaults/{vault_id}")
