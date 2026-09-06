import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions

from app.retrieval.client import get_shared_chroma_client
from app.retrieval.hybrid_rank import fuse_bm25_dense
from app.retrieval.bm25_index import PersistentBM25Index
from app.retrieval.fusion_router import deduplicate_chunks
from app.ingestion.chunker import SectionAwareChunker
from app.config import settings

logger = logging.getLogger(__name__)


class Tier2UserRetrieval:
    """
    Tier-2 User Uploaded Document Retrieval Engine (Phase 06).
    Provides hybrid dense+sparse retrieval isolated per session with persistent BM25.
    """

    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        self.client = get_shared_chroma_client(persist_dir)
        self._emb_fn = None
        self._collection = None
        self.bm25_index = PersistentBM25Index(index_name="tier2_user_bm25")

    @property
    def emb_fn(self):
        if self._emb_fn is None:
            from app.retrieval.client import get_shared_embedding_function
            self._emb_fn = get_shared_embedding_function(settings.retrieval.embedding_model_name)
        return self._emb_fn

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name="tier2_user",
                embedding_function=self.emb_fn
            )
        return self._collection

    def add_documents(self, session_id: str, filename: str, text: str) -> int:
        """
        Chunks the extracted PDF text and adds it to ChromaDB and BM25,
        associating it with the given session_id.
        """
        chunker = SectionAwareChunker(default_act_name=filename)
        chunks = chunker.chunk_document(text)
        
        if not chunks:
            return 0

        documents = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(chunks):
            doc_id = f"{session_id}_{filename}_{i}"
            meta = {
                "session_id": session_id,
                "filename": filename,
                "act": chunk.get("act", filename),
                "section": chunk.get("section", f"Chunk {i}"),
                "doc_type": "user_document",
            }
            documents.append(chunk["text"])
            metadatas.append(meta)
            ids.append(doc_id)

        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            # Sync to persistent BM25 index
            self.bm25_index.add_documents_batch(doc_ids=ids, documents=documents, metadatas=metadatas)
        except Exception as exc:
            if "InvalidDimensionException" in type(exc).__name__ or "dimensionality" in str(exc):
                self.client.delete_collection("tier2_user")
                self._collection = self.client.get_or_create_collection(
                    name="tier2_user",
                    embedding_function=self.emb_fn
                )
                self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
                self.bm25_index.add_documents_batch(doc_ids=ids, documents=documents, metadatas=metadatas)
            else:
                raise
        return len(chunks)

    def query(self, session_id: str, text: str, top_k: Optional[int] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        k = top_k or settings.retrieval.top_k

        # Check L2 Retrieval Cache (user/session scoped)
        try:
            from app.cache import l2_retrieval_cache
            cached = l2_retrieval_cache.get_tier2_results(
                query=text,
                top_k=k,
                user_id=user_id or session_id,
                session_id=session_id
            )
            if cached is not None:
                return cached
        except Exception as e:
            logger.debug(f"L2 tier2 cache lookup error: {e}")

        try:
            count = self.collection.count()
        except Exception:
            return []

        if count == 0:
            return []

        # 1. Dense query filtering by session_id
        dense_docs = []
        try:
            dense_results = self.collection.query(
                query_texts=[text],
                where={"session_id": session_id},
                n_results=min(k * 2, count)
            )
            
            if dense_results and dense_results.get("documents") and dense_results["documents"][0]:
                docs = dense_results["documents"][0]
                metas = dense_results["metadatas"][0]
                distances = dense_results["distances"][0] if "distances" in dense_results and dense_results["distances"] else [0.0] * len(docs)
                for i in range(len(docs)):
                    dense_docs.append({
                        "act": metas[i].get("act", metas[i].get("filename", "User Document")),
                        "section": metas[i].get("section", "General"),
                        "text": docs[i],
                        "score": 1.0 - distances[i],
                        "doc_type": "user_document",
                        "metadata": metas[i]
                    })

        except Exception as exc:
            logger.warning(f"ChromaDB tier2 query warning: {exc}")

        # 2. Fast Sparse (BM25) query filtering by session_id
        bm25_docs = self.bm25_index.search(
            query=text,
            top_k=k * 2,
            filter_fn=lambda m: m.get("session_id") == session_id
        )

        # 3. Fuse rankings (RRF)
        results = fuse_bm25_dense(bm25_docs, dense_docs, top_k=k)
        
        # 4. Deduplicate near-identical chunks
        deduped = deduplicate_chunks(results, similarity_threshold=settings.retrieval.dedup_similarity_threshold)

        try:
            from app.cache import l2_retrieval_cache
            l2_retrieval_cache.set_tier2_results(
                query=text,
                top_k=k,
                results=deduped,
                user_id=user_id or session_id,
                session_id=session_id
            )
        except Exception as e:
            logger.debug(f"L2 tier2 cache store error: {e}")

        return deduped
