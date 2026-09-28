"""
Statutory corpus pipeline (single implementation used by the API, the seed script and tests).

raw act text files + manifest.yaml
  -> PageIndex structure (Act -> Chapter -> Section)
  -> section-aware chunks with provenance metadata
  -> persistent BM25 (authoritative) + dense vectors (only when an embedding model is loaded)
  -> Statute / StatuteSection rows (what the Statute Library shows)
  -> cross-reference edges extracted from the statute text itself

Nothing in here contains legal content. If the directory is empty, the corpus is empty
and the UI says so.
"""
import hashlib
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

from app.config import settings

logger = logging.getLogger(__name__)

DERIVATION_TEXT_CROSS_REFERENCE = "text_extraction"
CORPUS_ORIGIN = "corpus_text"
CORPUS_SOURCE = "local_corpus"

# Markers written by the retired hardcoded seeder; used once to purge fabricated rows.
_LEGACY_SEED_SOURCES = ("mcp:nyaya", "mcp:themis", "mcp:ansvar", "mcp:taxbykk", "seed_india_code")
_LEGACY_SEED_DERIVATIONS = ("curated_legal_relationship", "mcp_case_law_lookup")


def acts_dir() -> str:
    configured = os.getenv("ACTS_RAW_DIR", "").strip()
    if configured:
        return configured
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(here, "..", "..", "..", "data", "acts_raw"),  # repo layout
        os.path.join(here, "..", "..", "data", "acts_raw"),        # backend-only layout (Docker image)
    ):
        candidate = os.path.normpath(candidate)
        if os.path.isdir(candidate):
            return candidate
    return os.path.normpath(os.path.join(here, "..", "..", "..", "data", "acts_raw"))


def load_manifest(directory: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    path = os.path.join(directory or acts_dir(), "manifest.yaml")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {str(k): (v or {}) for k, v in (data.get("acts") or {}).items()}
    except Exception as exc:
        logger.error("Corpus manifest unreadable (%s); acts will be indexed as unverified.", type(exc).__name__)
        return {}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:120]


def _section_heading(section_text: str, number: str) -> str:
    first = section_text.split("\n", 1)[0].strip()
    m = re.match(r"^Section\s+[\w]+\s*[.:\-]*\s*(.*)$", first, re.IGNORECASE)
    if m and m.group(1).strip():
        rest = m.group(1).strip()
        for sep in (" - ", " — ", ". "):
            if sep in rest:
                rest = rest.split(sep)[0]
                break
        rest = rest.rstrip(".").strip()
        if len(rest) > 2:
            return rest[:500]
    return f"Section {number}"


def extract_cross_references(section_text: str, own_number: str, known: set) -> List[str]:
    """Section numbers of the same Act mentioned in the text (only ones that exist in the corpus)."""
    found = []
    for m in re.finditer(r"(?i)\bsections?\s+((?:\d+[A-Z]{0,3})(?:\s*(?:,|and|or|to)\s*\d+[A-Z]{0,3})*)", section_text):
        for num in re.findall(r"\d+[A-Z]{0,3}", m.group(1)):
            num = num.upper()
            if num != own_number.upper() and num in known and num not in found:
                found.append(num)
    return found


def _act_record(filename: str, text: str, manifest: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    entry = manifest.get(filename, {})
    base = os.path.splitext(filename)[0]
    title = (entry.get("title") or base.replace("_", " ")).strip()
    return {
        "filename": filename,
        "slug": (entry.get("slug") or _slugify(title)),
        "title": title,
        "year": entry.get("year") if isinstance(entry.get("year"), int) else None,
        "domain": (entry.get("domain") or "unclassified").strip(),
        "jurisdiction": (entry.get("jurisdiction") or "").strip() or None,
        "source_url": (entry.get("source_url") or "").strip() or None,
        "source_version": (entry.get("source_version") or "").strip() or None,
        "publication_date": (entry.get("publication_date") or "").strip() or None,
        "legal_status": (entry.get("legal_status") or "unverified").strip(),
        "verified_at": (entry.get("verified_at") or "").strip() or None,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "in_manifest": bool(entry),
    }


def purge_legacy_seed_data(session) -> Dict[str, int]:
    """Removes rows produced by the retired hardcoded seeder (fabricated section text / 'MCP' provenance)."""
    from app.db.models import CitationEdge, Statute

    removed_edges = (
        session.query(CitationEdge)
        .filter(CitationEdge.origin == "mcp_relation", CitationEdge.derivation_method.in_(_LEGACY_SEED_DERIVATIONS))
        .delete(synchronize_session=False)
    )
    legacy = session.query(Statute).filter(Statute.source.in_(_LEGACY_SEED_SOURCES)).all()
    for statute in legacy:
        session.delete(statute)  # cascades to its sections
    return {"legacy_statutes_removed": len(legacy), "legacy_edges_removed": int(removed_edges or 0)}


def index_statutory_corpus(directory: Optional[str] = None, rebuild_retrieval: bool = True) -> Dict[str, Any]:
    """Idempotently (re)indexes every raw act file. Returns honest statistics."""
    from app.db.engine import get_sync_session
    from app.db.models import CitationEdge, Statute, StatuteSection
    from app.ingestion.chunker import SectionAwareChunker
    from app.retrieval.bm25_index import tier1_bm25_index
    from app.retrieval.client import (
        DenseRetrievalUnavailable,
        get_shared_chroma_client,
        get_shared_embedding_function,
    )
    from app.retrieval.pageindex import PageIndexBuilder

    directory = directory or acts_dir()
    stats: Dict[str, Any] = {
        "acts_dir_exists": os.path.isdir(directory),
        "acts_indexed": 0,
        "sections_indexed": 0,
        "chunks_indexed": 0,
        "cross_references": 0,
        "dense_indexed": False,
        "unverified_acts": [],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    files = sorted(f for f in os.listdir(directory) if f.endswith(".txt")) if stats["acts_dir_exists"] else []
    manifest = load_manifest(directory)
    pageindex = PageIndexBuilder()
    chunker = SectionAwareChunker()

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    with get_sync_session() as session:
        stats.update(purge_legacy_seed_data(session))
        seen_slugs = set()
        for filename in files:
            with open(os.path.join(directory, filename), "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            if not text.strip():
                continue
            act = _act_record(filename, text, manifest)
            seen_slugs.add(act["slug"])
            if act["legal_status"] == "unverified" or not act["verified_at"]:
                stats["unverified_acts"].append(act["title"])

            tree = pageindex.build_tree_from_text(text)
            sections: Dict[str, str] = {}
            for chapter in tree.get("chapters", {}).values():
                sections.update(chapter.get("sections", {}))

            statute = session.query(Statute).filter_by(slug=act["slug"]).first()
            if not statute:
                statute = Statute(id=str(uuid.uuid4()), slug=act["slug"], title=act["title"], domain=act["domain"], source=CORPUS_SOURCE)
                session.add(statute)
                session.flush()
            statute.title = act["title"]
            statute.year = act["year"]
            statute.domain = act["domain"]
            statute.source = CORPUS_SOURCE
            statute.source_url = act["source_url"]
            statute.source_version = act["source_version"]
            statute.publication_date = act["publication_date"]
            statute.legal_status = act["legal_status"]
            statute.verified_at = act["verified_at"]
            statute.content_hash = act["content_hash"]
            statute.section_count = len(sections)
            statute.updated_at = datetime.utcnow()

            existing = {s.number: s for s in session.query(StatuteSection).filter_by(statute_id=statute.id).all()}
            for number, sec_text in sections.items():
                row = existing.pop(number, None)
                if row is None:
                    row = StatuteSection(id=str(uuid.uuid4()), statute_id=statute.id, number=number)
                    session.add(row)
                row.heading = _section_heading(sec_text, number)
                row.raw_text = sec_text
                row.embedding_ready = True
            for stale in existing.values():  # sections no longer present in the source text
                session.delete(stale)

            # Cross-references found in the text itself (replaced wholesale on each index run).
            session.query(CitationEdge).filter(
                CitationEdge.origin == CORPUS_ORIGIN,
                CitationEdge.src_key.like(f"section:{act['slug']}:%"),
            ).delete(synchronize_session=False)
            known = {n.upper() for n in sections}
            for number, sec_text in sections.items():
                for ref in extract_cross_references(sec_text, number, known):
                    session.add(CitationEdge(
                        id=str(uuid.uuid4()),
                        src_type="section", src_key=f"section:{act['slug']}:{number}",
                        dst_type="section", dst_key=f"section:{act['slug']}:{ref}",
                        relation="references", origin=CORPUS_ORIGIN,
                        derivation_method=DERIVATION_TEXT_CROSS_REFERENCE,
                        confidence=1.0, created_at=datetime.utcnow(),
                    ))
                    stats["cross_references"] += 1

            for i, chunk in enumerate(chunker.chunk_document(text, act_name=act["title"])):
                sec = str(chunk["section"])
                chunk_id = f"{act['slug']}:{sec}:{i}"
                ids.append(chunk_id)
                documents.append(chunk["text"])
                metadatas.append({
                    "act": act["title"],
                    "act_slug": act["slug"],
                    "section": sec,
                    "doc_type": "statutory_law",
                    "source": act["filename"],
                    "domain": act["domain"],
                    "jurisdiction": act["jurisdiction"] or "",
                    "trust_level": "LOCAL_CORPUS",
                    "legal_status": act["legal_status"],
                    "verified_at": act["verified_at"] or "",
                    "content_hash": hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest(),
                    "document_version": act["source_version"] or "",
                    "publication_date": act["publication_date"] or "",
                    "retrieval_method": "local_hybrid_bm25_vector",
                    "source_url": act["source_url"] or "",
                })

            stats["acts_indexed"] += 1
            stats["sections_indexed"] += len(sections)

        # Acts whose source file was removed are no longer part of the corpus.
        for statute in session.query(Statute).filter(Statute.source == CORPUS_SOURCE).all():
            if statute.slug not in seen_slugs:
                session.delete(statute)

    stats["chunks_indexed"] = len(ids)
    if rebuild_retrieval:
        tier1_bm25_index.clear()
        if ids:
            tier1_bm25_index.add_documents_batch(doc_ids=ids, documents=documents, metadatas=metadatas)
        client = get_shared_chroma_client(settings.CHROMA_PERSIST_DIR)
        try:
            client.delete_collection("tier1_law")
        except Exception:
            pass
        try:
            collection = client.get_or_create_collection(
                "tier1_law", embedding_function=get_shared_embedding_function(settings.retrieval.embedding_model_name)
            )
            if ids:
                batch = int(os.getenv("CORPUS_EMBED_BATCH", "64"))
                for start in range(0, len(ids), batch):
                    collection.add(
                        ids=ids[start:start + batch],
                        documents=documents[start:start + batch],
                        metadatas=metadatas[start:start + batch],
                    )
                stats["dense_indexed"] = True
        except DenseRetrievalUnavailable:
            stats["dense_indexed"] = False
        try:
            from app.cache import l2_retrieval_cache
            l2_retrieval_cache.clear()
        except Exception:
            pass

    logger.info(
        "Statutory corpus indexed: %d acts, %d sections, %d chunks, %d cross-references (dense=%s).",
        stats["acts_indexed"], stats["sections_indexed"], stats["chunks_indexed"], stats["cross_references"], stats["dense_indexed"],
    )
    return stats
