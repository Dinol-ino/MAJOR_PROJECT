import os
import hashlib
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings
from app.db.engine import get_sync_session
from app.db.models import DocumentMemory, DocumentPage, ProjectVault, utcnow
from app.services.document_store import document_store
from app.security.pdf_sanitizer import pdf_sanitizer
from app.ingestion.chunker import SectionAwareChunker
from app.retrieval.client import get_shared_chroma_client, get_shared_embedding_function, DenseRetrievalUnavailable
from app.retrieval.bm25_index import PersistentBM25Index

logger = logging.getLogger(__name__)


def compute_file_hash(content: bytes) -> str:
    """Computes SHA-256 hash of file content for deduplication."""
    return hashlib.sha256(content).hexdigest()


# Bump when extraction or chunking changes so stale indexes can be found and rebuilt
# from the stored originals (rebuilding an index never touches the original file).
PARSER_VERSION = "pymupdf-text/page-provenance-1"

_IN_FLIGHT_STATES = ("pending", "parsing", "chunking", "embedding", "indexing")


def _page_at(offsets: List[Tuple[int, int, int]], position: int) -> Optional[int]:
    for start, end, page_no in offsets:
        if start <= position < end:
            return page_no
    return offsets[-1][2] if offsets and position >= offsets[-1][1] else None


def locate_chunk_pages(full_text: str, offsets: List[Tuple[int, int, int]], chunk_text: str,
                       cursor: int = 0) -> Tuple[Optional[int], Optional[int], int]:
    """Best-effort mapping of a chunk back to the pages it came from.

    Returns (page_start, page_end, new_cursor). (None, None, cursor) when the chunk text
    cannot be located verbatim - a missing page is reported as missing, never guessed.
    """
    text = (chunk_text or "").strip()
    if not text:
        return None, None, cursor
    for probe_len in (80, 40):
        probe = text[:probe_len]
        idx = full_text.find(probe, max(0, cursor - 400))
        if idx < 0:
            idx = full_text.find(probe)
        if idx >= 0:
            end = min(idx + len(text), len(full_text)) - 1
            return _page_at(offsets, idx), _page_at(offsets, max(idx, end)), idx
    return None, None, cursor


def get_vault_collection_name(vault_id: str) -> str:
    """Generates a valid Chroma collection name for a project vault."""
    clean_id = vault_id.replace("-", "_")
    return f"vault_{clean_id}"[:63]


class VaultDocumentIngestionService:
    """
    Asynchronous and background ingestion service for Project Vault documents (Spec 01 §4).
    Lifecycle: pending(0) -> parsing(10) -> chunking(40) -> embedding(70) -> indexing(95) -> ready(100).
    """

    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self.chroma_client = get_shared_chroma_client(self.persist_dir)
        self.bm25_index = PersistentBM25Index(index_name="vault_documents_bm25")

    def get_vault_collection(self, vault_id: str):
        col_name = get_vault_collection_name(vault_id)
        emb_fn = get_shared_embedding_function(settings.retrieval.embedding_model_name)
        return self.chroma_client.get_or_create_collection(
            name=col_name,
            embedding_function=emb_fn
        )

    def delete_vault_collection(self, vault_id: str):
        """Purges every retrieval representation of a vault: dense collection, BM25 entries, cached results."""
        col_name = get_vault_collection_name(vault_id)
        try:
            self.chroma_client.delete_collection(name=col_name)
        except Exception as e:
            logger.debug(f"Collection {col_name} delete error or already deleted: {e}")
        try:
            self.bm25_index.delete_documents_where(lambda _cid, m: m.get("vault_id") == vault_id)
        except Exception as e:
            logger.warning("BM25 purge failed for vault %s: %s", vault_id, type(e).__name__)
        try:
            from app.cache import l2_retrieval_cache
            l2_retrieval_cache.clear()
        except Exception:
            pass

    def update_doc_state(
        self,
        doc_id: str,
        status: str,
        progress: int,
        error: Optional[str] = None,
        page_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
    ):
        with get_sync_session() as session:
            doc = session.query(DocumentMemory).filter(DocumentMemory.doc_id == doc_id).first()
            if doc:
                doc.ingest_status = status
                doc.ingest_progress = progress
                if error is not None:
                    doc.ingest_error = error
                if page_count is not None:
                    doc.page_count = page_count
                if chunk_count is not None:
                    doc.chunk_count = chunk_count

    def ingest_document(
        self,
        doc_id: str,
        vault_id: str,
        filename: str,
        content: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Executes full ingestion pipeline for a PDF case file/statute within a vault.
        Stores per-page text in DocumentPage and chunks in vault-scoped ChromaDB + BM25.

        ``content`` is optional: when omitted the bytes are read from the canonical store,
        which is how restart recovery and re-indexing work. The pipeline is idempotent -
        running it again replaces this document's derived pages/chunks/vectors and never
        touches the original file.
        """
        logger.info(f"Starting ingestion for document {doc_id} ({filename}) in vault {vault_id}")

        try:
            if content is None:
                with get_sync_session() as session:
                    row = session.query(DocumentMemory).filter(DocumentMemory.doc_id == doc_id).first()
                    stored_path = row.storage_path if row else None
                if not document_store.exists(stored_path):
                    raise ValueError("The original document is not available in storage; upload it again.")
                content = document_store.read(stored_path)
            # 1. Parsing stage (10%)
            self.update_doc_state(doc_id, status="parsing", progress=10)

            # Validate & extract using PyMuPDF through pdf_sanitizer
            is_valid, err = pdf_sanitizer.validate_pdf_bytes(content)
            if not is_valid:
                raise ValueError(err or "PDF validation failed.")

            import fitz
            doc = fitz.open(stream=content, filetype="pdf")
            total_pages = len(doc)
            # This path looped over every page, so the vault ingester had no page budget
            # at all while the session uploader rejected anything over the limit. Both now
            # read at most MAX_FILE_PAGES pages: bounded memory, and a long document is
            # ingested in part rather than refused.
            max_pages = settings.retrieval.max_file_pages
            pages_to_read = min(total_pages, max_pages)
            if total_pages > pages_to_read:
                if settings.retrieval.pdf_page_overflow_mode == "reject":
                    doc.close()
                    raise ValueError(
                        f"PDF page count ({total_pages}) exceeds the maximum of {max_pages} pages."
                    )
                logger.warning(
                    "Vault document %s truncated at ingestion: %d of %d pages read.",
                    doc_id, pages_to_read, total_pages,
                )
            pages_data = []

            for p_num in range(pages_to_read):
                page = doc.load_page(p_num)
                text = page.get_text("text") or ""
                pages_data.append((p_num + 1, text))
            doc.close()

            full_text = "\n\n".join([p[1] for p in pages_data])
            page_offsets: List[Tuple[int, int, int]] = []
            _pos = 0
            for _page_no, _raw in pages_data:
                page_offsets.append((_pos, _pos + len(_raw), _page_no))
                _pos += len(_raw) + 2  # the "\n\n" joiner

            # Drop any derived state from an earlier run of THIS document (re-index / retry).
            self.delete_document_vectors(vault_id=vault_id, doc_id=doc_id)

            # Persist per-page records into document_pages table
            with get_sync_session() as session:
                session.query(DocumentPage).filter(DocumentPage.doc_id == doc_id).delete()
                for page_no, raw_text in pages_data:
                    dp = DocumentPage(
                        id=str(uuid.uuid4()),
                        doc_id=doc_id,
                        page_no=page_no,
                        raw_text=raw_text[:100000],  # safeguard page size
                    )
                    session.add(dp)

            # 2. Chunking stage (40%)
            self.update_doc_state(doc_id, status="chunking", progress=40, page_count=pages_to_read)

            chunker = SectionAwareChunker(default_act_name=filename)
            if chunker.builder.extract_section_headers(full_text):
                raw_chunks = chunker.chunk_document(full_text)
            else:
                # No statutory section structure (pleadings, judgments, contracts, notes):
                # chunk page by page so a chunk never straddles a page boundary and every
                # citation points at one exact page.
                raw_chunks = []
                for page_no, page_text in pages_data:
                    if not page_text.strip():
                        continue
                    parts = chunker.chunk_document(page_text)
                    for part_no, part in enumerate(parts, 1):
                        raw_chunks.append({
                            "text": part["text"],
                            "act": filename,
                            "section": f"Page {page_no}" if len(parts) == 1 else f"Page {page_no}, part {part_no}",
                            "page_start": page_no,
                            "page_end": page_no,
                        })
            if not raw_chunks:
                # Fallback: simple page-level chunking if no section boundaries found
                raw_chunks = [{"text": p[1], "section": f"Page {p[0]}", "act": filename,
                               "page_start": p[0], "page_end": p[0]} for p in pages_data if p[1].strip()]

            # 3. Embedding stage (70%)
            self.update_doc_state(doc_id, status="embedding", progress=70, chunk_count=len(raw_chunks))

            col = self.get_vault_collection(vault_id)

            ids = []
            documents = []
            metadatas = []

            cursor = 0
            for i, chunk in enumerate(raw_chunks):
                chunk_id = f"{doc_id}_c{i}"
                ids.append(chunk_id)
                documents.append(chunk["text"])
                p_start, p_end = chunk.get("page_start"), chunk.get("page_end")
                if p_start is None:
                    p_start, p_end, cursor = locate_chunk_pages(full_text, page_offsets, chunk["text"], cursor)
                meta = {
                    "doc_id": doc_id,
                    "vault_id": vault_id,
                    "filename": filename,
                    "act": chunk.get("act", filename),
                    "section": chunk.get("section", f"Chunk {i}"),
                    "doc_type": "vault_document",
                    "chunk_index": i,
                }
                if p_start is not None:  # Chroma rejects None metadata values
                    meta["page_start"] = int(p_start)
                    meta["page_end"] = int(p_end if p_end is not None else p_start)
                metadatas.append(meta)

            # 4. Indexing stage (95%)
            self.update_doc_state(doc_id, status="indexing", progress=95)

            if ids:
                # Lexical index is authoritative; dense vectors only when a real embedding model is loaded.
                self.bm25_index.add_documents_batch(doc_ids=ids, documents=documents, metadatas=metadatas)
                try:
                    col.add(documents=documents, metadatas=metadatas, ids=ids)
                except DenseRetrievalUnavailable:
                    pass

            # 5. Ready stage (100%)
            self.update_doc_state(
                doc_id,
                status="ready",
                progress=100,
                page_count=total_pages,
                chunk_count=len(raw_chunks)
            )
            with get_sync_session() as session:
                row = session.query(DocumentMemory).filter(DocumentMemory.doc_id == doc_id).first()
                if row:
                    row.parser_version = PARSER_VERSION
                    row.doc_type = row.doc_type or "pdf"
                    row.indexed_at = utcnow()

            logger.info(f"Ingestion succeeded for document {doc_id}: {total_pages} pages, {len(raw_chunks)} chunks.")
            return {
                "status": "ready",
                "doc_id": doc_id,
                "vault_id": vault_id,
                "pages": total_pages,
                "chunks": len(raw_chunks),
            }

        except Exception as exc:
            logger.error(f"Ingestion failed for doc {doc_id}: {exc}", exc_info=True)
            self.update_doc_state(doc_id, status="failed", progress=0, error=str(exc))
            return {
                "status": "failed",
                "doc_id": doc_id,
                "vault_id": vault_id,
                "error": str(exc),
            }

    def query_vault(
        self,
        vault_id: str,
        query_text: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Hybrid (BM25 + dense, RRF-fused) retrieval strictly scoped to one vault.
        Lexical results are filtered by vault_id metadata; dense results come from the vault's own collection.
        """
        from app.retrieval.hybrid_rank import fuse_bm25_dense

        bm25_docs: List[Dict[str, Any]] = []
        try:
            for hit in self.bm25_index.search(
                query=query_text,
                top_k=top_k * 2,
                filter_fn=lambda m: m.get("vault_id") == vault_id,
            ):
                meta = hit.get("metadata") or {}
                bm25_docs.append({**hit, "doc_type": "vault_document", "metadata": meta})
        except Exception as e:
            logger.debug("Vault BM25 query error for vault %s: %s", vault_id, type(e).__name__)

        dense_docs: List[Dict[str, Any]] = []
        try:
            col = self.get_vault_collection(vault_id)
            n = col.count()
            if n > 0:
                res = col.query(query_texts=[query_text], n_results=min(top_k * 2, n))
                if res and res.get("documents") and res["documents"][0]:
                    distances = res["distances"][0] if res.get("distances") else [0.0] * len(res["documents"][0])
                    for i, (doc_text, meta) in enumerate(zip(res["documents"][0], res["metadatas"][0])):
                        if (meta or {}).get("vault_id") not in (None, vault_id):
                            continue  # defence in depth: never surface another vault's chunk
                        dist = distances[i] if i < len(distances) else 0.0
                        dense_docs.append({
                            "act": (meta or {}).get("act") or (meta or {}).get("filename", "Vault Document"),
                            "section": (meta or {}).get("section", ""),
                            "text": doc_text,
                            "metadata": meta,
                            "doc_type": "vault_document",
                            "score": 1.0 / (1.0 + max(0.0, float(dist))),
                        })
        except DenseRetrievalUnavailable:
            pass
        except Exception as e:
            logger.debug("Vault dense query error for vault %s: %s", vault_id, type(e).__name__)

        # Relevance gate: ranking always returns *something*. Keep only chunks that share
        # subject matter with the question, so an off-topic query finds nothing (and the
        # answer pipeline refuses) instead of being answered from unrelated pages.
        from app.retrieval import relevance
        min_cov = settings.retrieval.evidence_min_term_coverage
        if relevance.is_document_level_query(query_text):
            # "Summarise this document" has no topical terms: serve the opening passages in order.
            return self._leading_chunks(vault_id, top_k)
        stats = self.bm25_index.term_stats(relevance.stem)
        bm25_docs = relevance.filter_supported(query_text, bm25_docs, min_cov, stats)
        dense_docs = [
            d for d in dense_docs
            if relevance.supports_query(query_text, d.get("text", ""), min_cov, stats)
            or d.get("score", 0.0) >= settings.retrieval.vault_dense_min_score
        ]

        if not bm25_docs and not dense_docs:
            return []
        return fuse_bm25_dense(bm25_docs, dense_docs, top_k=top_k)

    def _leading_chunks(self, vault_id: str, top_k: int) -> List[Dict[str, Any]]:
        """First chunks of each document in the vault, in reading order (used for overview requests)."""
        out: List[Dict[str, Any]] = []
        try:
            store = self.bm25_index
            rows = [
                (cid, store.documents[i], (store.metadatas[i] if hasattr(store, "metadatas") else {}) or {})
                for i, cid in enumerate(store.doc_ids)
            ] if hasattr(store, "doc_ids") else []
        except Exception:
            rows = []
        rows = [r for r in rows if r[2].get("vault_id") == vault_id]
        rows.sort(key=lambda r: (str(r[2].get("doc_id")), int(r[2].get("chunk_index", 0))))
        for cid, text, meta in rows[:top_k]:
            out.append({"act": meta.get("act") or meta.get("filename", "Vault Document"), "section": meta.get("section", ""),
                        "text": text, "metadata": meta, "doc_type": "vault_document", "score": 1.0})
        return out

    def resume_incomplete(self) -> List[str]:
        """Re-runs ingestion for documents a restart interrupted, from their stored originals.

        A document left in an in-flight state has no live worker after a restart; without
        this it would sit in "pending" forever. Documents with no stored original are
        marked failed so the user is told to re-upload instead of waiting indefinitely.
        """
        with get_sync_session() as session:
            rows = [
                (r.doc_id, r.project_vault_id, r.filename, r.storage_path)
                for r in session.query(DocumentMemory)
                .filter(DocumentMemory.ingest_status.in_(_IN_FLIGHT_STATES))
                .filter(DocumentMemory.project_vault_id.isnot(None))
                .all()
            ]
        resumed: List[str] = []
        for doc_id, vault_id, filename, storage_path in rows:
            if not document_store.exists(storage_path):
                self.update_doc_state(doc_id, status="failed", progress=0,
                                      error="Interrupted by a restart and the original file is unavailable; please upload it again.")
                continue
            self.ingest_document(doc_id=doc_id, vault_id=vault_id, filename=filename)
            resumed.append(doc_id)
        return resumed

    def delete_document_vectors(self, vault_id: str, doc_id: str):
        """Purges document chunks from vault Chroma collection and BM25 index."""
        try:
            col = self.get_vault_collection(vault_id)
            # Find and delete ids matching doc_id prefix
            col.delete(where={"doc_id": doc_id})
        except Exception as e:
            logger.warning(f"Error purging vectors for doc {doc_id} from vault {vault_id}: {e}")

        try:
            self.bm25_index.delete_documents_where(
                lambda cid, m: m.get("doc_id") == doc_id or cid.startswith(f"{doc_id}_")
            )
        except Exception as e:
            logger.warning("BM25 doc purge failed for doc %s: %s", doc_id, type(e).__name__)

        # Cached retrieval results may still reference the deleted chunks.
        try:
            from app.cache import l2_retrieval_cache
            l2_retrieval_cache.clear()
        except Exception:
            pass


ingest_service = VaultDocumentIngestionService()
