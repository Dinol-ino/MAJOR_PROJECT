import os
import logging
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi
from app.retrieval.hybrid_rank import fuse_bm25_dense

logger = logging.getLogger(__name__)


class Tier1LawRetrieval:
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-small-en"
        )
        self.collection = self.client.get_or_create_collection(
            name="tier1_law", 
            embedding_function=self.emb_fn
        )

    def query(self, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        try:
            count = self.collection.count()
        except Exception:
            return []

        if count == 0:
            return []

        # 1. Dense query
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
                    dense_docs.append({
                        "act": metas[i]["act"],
                        "section": metas[i]["section"],
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
                except Exception:
                    pass

        # 2. Sparse (BM25) query
        try:
            all_data = self.collection.get()
        except Exception:
            all_data = None

        if not all_data or not all_data.get("documents"):
            return dense_docs[:top_k]

        documents = all_data["documents"]
        metas = all_data["metadatas"]

        tokenized_corpus = [doc.lower().split() for doc in documents]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = text.lower().split()
        scores = bm25.get_scores(tokenized_query)

        bm25_docs = []
        for i, score in enumerate(scores):
            if score > 0:
                bm25_docs.append({
                    "act": metas[i]["act"],
                    "section": metas[i]["section"],
                    "text": documents[i],
                    "score": score
                })
        bm25_docs = sorted(bm25_docs, key=lambda x: x["score"], reverse=True)

        # 3. Fuse rankings
        return fuse_bm25_dense(bm25_docs, dense_docs, top_k=top_k)
