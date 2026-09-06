import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions

from app.retrieval.client import get_shared_chroma_client
from app.retrieval.hybrid_rank import fuse_bm25_dense
from app.retrieval.bm25_index import tier1_bm25_index
from app.retrieval.fusion_router import fusion_router
from app.config import settings

logger = logging.getLogger(__name__)


class Tier1LawRetrieval:
    """
    Tier-1 Statutory Law Retrieval Engine (Phase 06).
    Combines:
    - ChromaDB dense vector search with lazy embedding model initialization.
    - Persistent BM25 index (incremental updates, zero rebuilds per query).
    - Reciprocal Rank Fusion (RRF).
    - PageIndex structural statutory tree navigation & Fusion Router.
    - Automatic near-identical chunk deduplication & superseded filtering.
    """

    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        self.client = get_shared_chroma_client(persist_dir)
        self._emb_fn = None
        self._collection = None
        self.bm25_index = tier1_bm25_index
        self._synced = False

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
                name="tier1_law",
                embedding_function=self.emb_fn
            )
        return self._collection

    def _sync_bm25_if_needed(self):
        """One-time startup sync from ChromaDB to persistent BM25 index if empty."""
        try:
            if self.bm25_index.count() == 0:
                count = self.collection.count()
                if count > 0:
                    all_data = self.collection.get()
                    if all_data and all_data.get("documents"):
                        self.bm25_index.add_documents_batch(
                            doc_ids=all_data.get("ids", [str(i) for i in range(len(all_data["documents"]))]),
                            documents=all_data["documents"],
                            metadatas=all_data.get("metadatas", [])
                        )
                        logger.info(f"Synchronized {count} statutory documents to persistent BM25 index.")
        except Exception as exc:
            logger.debug(f"BM25 index sync check deferred: {exc}")

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any]):
        """Adds a document to both ChromaDB dense index and persistent BM25 index."""
        self.collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata]
        )
        self.bm25_index.add_document(doc_id, text, metadata)
        self.bm25_index.save()

    def query(self, text: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        k = top_k or settings.retrieval.top_k

        # 1. Check L2 Retrieval Cache (Phase 04)
        try:
            from app.cache import l2_retrieval_cache
            cached = l2_retrieval_cache.get_tier1_results(query=text, top_k=k)
            if cached is not None:
                return cached
        except Exception as e:
            logger.debug(f"L2 cache lookup error: {e}")

        try:
            count = self.collection.count()
        except Exception:
            return []

        if count == 0:
            return []

        # 2. Dense query (ChromaDB)
        dense_docs = []
        try:
            dense_results = self.collection.query(
                query_texts=[text],
                n_results=min(k * 2, count)
            )
            
            if dense_results and dense_results.get("documents") and dense_results["documents"][0]:
                docs = dense_results["documents"][0]
                metas = dense_results["metadatas"][0]
                distances = dense_results["distances"][0] if "distances" in dense_results and dense_results["distances"] else [0.0] * len(docs)
                for i in range(len(docs)):
                    dense_docs.append({
                        "act": metas[i].get("act", "General Law"),
                        "section": metas[i].get("section", "General"),
                        "text": docs[i],
                        "score": 1.0 - distances[i],
                        "doc_type": "statutory_law",
                        "metadata": metas[i]
                    })
        except Exception as exc:
            logger.warning(f"ChromaDB tier1 query warning: {exc}")

        # 3. Fast Sparse BM25 query (Persistent Index with Zero Rebuild)
        bm25_docs = self.bm25_index.search(text, top_k=k * 2)

        # 4. Reciprocal Rank Fusion (RRF)
        hybrid_results = fuse_bm25_dense(bm25_docs, dense_docs, top_k=k * 2)

        # 5. Fusion Router (Structural PageIndex vs Semantic vs Both + Dedup + Superseded Filter)
        corpus_sample = [{"act": d.get("act", ""), "text": d.get("text", ""), "metadata": d.get("metadata", {})} for d in hybrid_results]
        final_results = fusion_router.fuse_retrieval(
            query=text,
            hybrid_results=hybrid_results,
            corpus_documents=corpus_sample,
            top_k=k
        )

        # 6. Store in L2 Retrieval Cache
        try:
            from app.cache import l2_retrieval_cache
            l2_retrieval_cache.set_tier1_results(query=text, top_k=k, results=final_results)
        except Exception as e:
            logger.debug(f"L2 cache store error: {e}")

        return final_results
