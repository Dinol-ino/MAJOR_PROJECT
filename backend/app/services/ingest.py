import os
import hashlib
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings
from app.db.engine import get_sync_session
from app.db.models import DocumentMemory, DocumentPage, ProjectVault
from app.security.pdf_sanitizer import pdf_sanitizer
from app.ingestion.chunker import SectionAwareChunker
from app.retrieval.client import get_shared_chroma_client, get_shared_embedding_function, DenseRetrievalUnavailable
from app.retrieval.bm25_index import PersistentBM25Index

logger = logging.getLogger(__name__)


def compute_file_hash(content: bytes) -> str:
    """Computes SHA-256 hash of file content for deduplication."""
    return hashlib.sha256(content).hexdigest()


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
        content: bytes,
    ) -> Dict[str, Any]:
        """
        Executes full ingestion pipeline for a PDF case file/statute within a vault.
        Stores per-page text in DocumentPage and chunks in vault-scoped ChromaDB + BM25.
        """
        logger.info(f"Starting ingestion for document {doc_id} ({filename}) in vault {vault_id}")

        try:
            # 1. Parsing stage (10%)
            self.update_doc_state(doc_id, status="parsing", progress=10)

            # Validate & extract using PyMuPDF through pdf_sanitizer
            is_valid, err = pdf_sanitizer.validate_pdf_bytes(content)
            if not is_valid:
                raise ValueError(err or "PDF validation failed.")

            import fitz
            doc = fitz.open(stream=content, filetype="pdf")
            total_pages = len(doc)
            pages_data = []

            for p_num in range(total_pages):
                page = doc.load_page(p_num)
                text = page.get_text("text") or ""
                pages_data.append((p_num + 1, text))
            doc.close()

            full_text = "\n\n".join([p[1] for p in pages_data])

            # Persist per-page records into document_pages table
            with get_sync_session() as session:
                for page_no, raw_text in pages_data:
                    dp = DocumentPage(
                        id=str(uuid.uuid4()),
                        doc_id=doc_id,
                        page_no=page_no,
                        raw_text=raw_text[:100000],  # safeguard page size
                    )
                    session.add(dp)

            # 2. Chunking stage (40%)
            self.update_doc_state(doc_id, status="chunking", progress=40, page_count=total_pages)

            chunker = SectionAwareChunker(default_act_name=filename)
            raw_chunks = chunker.chunk_document(full_text)
            if not raw_chunks:
                # Fallback: simple page-level chunking if no section boundaries found
                raw_chunks = [{"text": p[1], "section": f"Page {p[0]}", "act": filename} for p in pages_data if p[1].strip()]

            # 3. Embedding stage (70%)
            self.update_doc_state(doc_id, status="embedding", progress=70, chunk_count=len(raw_chunks))

            col = self.get_vault_collection(vault_id)

            ids = []
            documents = []
            metadatas = []

            for i, chunk in enumerate(raw_chunks):
                chunk_id = f"{doc_id}_c{i}"
                ids.append(chunk_id)
                documents.append(chunk["text"])
                metadatas.append({
                    "doc_id": doc_id,
                    "vault_id": vault_id,
                    "filename": filename,
                    "act": chunk.get("act", filename),
                    "section": chunk.get("section", f"Chunk {i}"),
                    "doc_type": "vault_document",
                })

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

        if not bm25_docs and not dense_docs:
            return []
        return fuse_bm25_dense(bm25_docs, dense_docs, top_k=top_k)

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
