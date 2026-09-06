import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi
from app.retrieval.hybrid_rank import fuse_bm25_dense

logger = logging.getLogger(__name__)


_cached_default_emb_fn = None

def get_default_embedding_function():
    global _cached_default_emb_fn
    if _cached_default_emb_fn is None:
        _cached_default_emb_fn = embedding_functions.DefaultEmbeddingFunction()
    return _cached_default_emb_fn


class Tier1LawRetrieval:
    def __init__(self, persist_dir: str, model_name: str = "law-ai/InLegalBERT"):
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.model_name = model_name

        # Respect RETRIEVAL_EMBEDDINGS env var to control RAM usage
        embeddings_mode = os.getenv("RETRIEVAL_EMBEDDINGS", "local").lower()

        if embeddings_mode == "model":
            try:
                self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=model_name
                )
            except Exception as e:
                logger.warning(f"Could not load {model_name} ({e}), falling back to default embeddings")
                self.emb_fn = get_default_embedding_function()
        else:
            # 'local' mode: use ChromaDB's lightweight default embeddings (zero additional RAM)
            self.emb_fn = get_default_embedding_function()
            logger.info("Using lightweight default embeddings (RETRIEVAL_EMBEDDINGS=local)")

        self.collection = self.client.get_or_create_collection(
            name="tier1_law", 
            embedding_function=self.emb_fn
        )

        # BM25 Index Cache (rebuilt ONLY on corpus write/invalidation, never per query)
        self._bm25_instance: Optional[BM25Okapi] = None
        self._bm25_documents: List[str] = []
        self._bm25_metas: List[Dict[str, Any]] = []

    def _ensure_bm25_index(self):
        """Builds or returns cached BM25 index."""
        if self._bm25_instance is not None:
            return self._bm25_instance, self._bm25_documents, self._bm25_metas

        try:
            all_data = self.collection.get()
        except Exception:
            all_data = None

        if not all_data or not all_data.get("documents"):
            self._bm25_instance = None
            self._bm25_documents = []
            self._bm25_metas = []
            return None, [], []

        docs = all_data["documents"]
        metas = all_data["metadatas"]

        # Filter out superseded entries if marked
        valid_docs = []
        valid_metas = []
        for d, m in zip(docs, metas):
            if m.get("superseded_by") is None or m.get("superseded_by") == "":
                valid_docs.append(d)
                valid_metas.append(m)

        tokenized_corpus = [doc.lower().split() for doc in valid_docs]
        if tokenized_corpus:
            self._bm25_instance = BM25Okapi(tokenized_corpus)
            self._bm25_documents = valid_docs
            self._bm25_metas = valid_metas
        else:
            self._bm25_instance = None
            self._bm25_documents = []
            self._bm25_metas = []

        return self._bm25_instance, self._bm25_documents, self._bm25_metas

    def invalidate_bm25_cache(self):
        """Invalidates BM25 cache when new documents are written."""
        self._bm25_instance = None
        self._bm25_documents = []
        self._bm25_metas = []

    def query(self, text: str, top_k: int = 3, jurisdiction: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            count = self.collection.count()
        except Exception:
            return []

        if count == 0:
            return []

        # 1. Dense query with metadata filtering
        dense_docs = []
        try:
            dense_results = self.collection.query(
                query_texts=[text],
                n_results=min(top_k * 2, count)
            )
            
            if dense_results and dense_results.get("documents") and dense_results["documents"][0]:
                docs = dense_results["documents"][0]
                metas = dense_results["metadatas"][0]
                distances = dense_results["distances"][0] if "distances" in dense_results and dense_results["distances"] else [0.0] * len(docs)
                for i in range(len(docs)):
                    meta = metas[i]
                    # Filter out superseded documents
                    if meta.get("superseded_by"):
                        continue
                    if jurisdiction and meta.get("jurisdiction") and meta.get("jurisdiction").lower() != jurisdiction.lower():
                        continue

                    dense_docs.append({
                        "act": meta.get("act", "General Law"),
                        "section": meta.get("section", "General"),
                        "text": docs[i],
                        "score": 1.0 - distances[i]
                    })
        except Exception as exc:
            logger.warning(f"ChromaDB tier1 query warning: {exc}")
            if "InvalidDimensionException" in type(exc).__name__ or "dimensionality" in str(exc):
                try:
                    self.client.delete_collection("tier1_law")
                    self.collection = self.client.get_or_create_collection(
                        name="tier1_law",
                        embedding_function=self.emb_fn
                    )
                    self.invalidate_bm25_cache()
                except Exception:
                    pass

        # 2. Sparse (BM25) query using cached index
        bm25_inst, documents, metas = self._ensure_bm25_index()
        if not bm25_inst or not documents:
            return dense_docs[:top_k]

        tokenized_query = text.lower().split()
        scores = bm25_inst.get_scores(tokenized_query)

        bm25_docs = []
        for i, score in enumerate(scores):
            if score > 0:
                meta = metas[i]
                if jurisdiction and meta.get("jurisdiction") and meta.get("jurisdiction").lower() != jurisdiction.lower():
                    continue
                bm25_docs.append({
                    "act": meta.get("act", "General Law"),
                    "section": meta.get("section", "General"),
                    "text": documents[i],
                    "score": score
                })
        bm25_docs = sorted(bm25_docs, key=lambda x: x["score"], reverse=True)

        # 3. Fuse rankings
        return fuse_bm25_dense(bm25_docs, dense_docs, top_k=top_k)

