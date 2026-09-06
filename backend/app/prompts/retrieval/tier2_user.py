import os
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi
from app.retrieval.hybrid_rank import fuse_bm25_dense
from app.ingestion.chunker import SectionAwareChunker

logger = logging.getLogger(__name__)


from app.retrieval.tier1_law import get_default_embedding_function


class Tier2UserRetrieval:
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
            logger.info("Tier2 using lightweight default embeddings (RETRIEVAL_EMBEDDINGS=local)")

        self.collection = self.client.get_or_create_collection(
            name="tier2_user", 
            embedding_function=self.emb_fn
        )

        # Per-session BM25 Index Cache (rebuilt only on add_documents, never per query)
        self._bm25_cache: Dict[str, Tuple[BM25Okapi, List[str], List[Dict[str, Any]]]] = {}

    def invalidate_bm25_cache(self, session_id: Optional[str] = None):
        """Invalidates BM25 cache for a given session or all sessions."""
        if session_id:
            self._bm25_cache.pop(session_id, None)
        else:
            self._bm25_cache.clear()

    def _ensure_bm25_index(self, session_id: str):
        """Returns cached BM25 index for session_id or builds it from ChromaDB."""
        if session_id in self._bm25_cache:
            return self._bm25_cache[session_id]

        try:
            all_data = self.collection.get(where={"session_id": session_id})
        except Exception:
            all_data = None

        if not all_data or not all_data.get("documents"):
            return None, [], []

        docs = all_data["documents"]
        metas = all_data["metadatas"]

        tokenized_corpus = [doc.lower().split() for doc in docs]
        if tokenized_corpus:
            bm25_inst = BM25Okapi(tokenized_corpus)
            self._bm25_cache[session_id] = (bm25_inst, docs, metas)
            return bm25_inst, docs, metas

        return None, [], []

    def add_documents(
        self, 
        session_id: str, 
        filename: str, 
        text: str, 
        jurisdiction: str = "India",
        effective_date: str = "now"
    ) -> int:
        """
        Chunks the extracted PDF text and adds it to Tier-2 collection with full metadata schema.
        Invalidates BM25 cache for this session_id.
        """
        chunker = SectionAwareChunker(default_act_name=filename)
        chunks = chunker.chunk_document(text)
        
        if not chunks:
            return 0
            
        ingestion_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        documents = [c["text"] for c in chunks]
        metadatas = [
            {
                "act": c["act"],
                "section": str(c["section"]),
                "session_id": session_id,
                "jurisdiction": jurisdiction,
                "effective_date": effective_date,
                "superseded_by": "",
                "ingestion_hash": ingestion_hash
            }
            for c in chunks
        ]
        ids = [f"{session_id}_{filename}_{i}" for i in range(len(chunks))]
        
        try:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        except Exception as exc:
            if "InvalidDimensionException" in type(exc).__name__ or "dimensionality" in str(exc):
                logger.warning(f"Dimension mismatch in tier2_user during add, recreating collection: {exc}")
                try:
                    self.client.delete_collection("tier2_user")
                except Exception:
                    pass
                self.collection = self.client.get_or_create_collection(
                    name="tier2_user",
                    embedding_function=self.emb_fn
                )
                self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            else:
                raise

        # Invalidate BM25 cache for session on document addition
        self.invalidate_bm25_cache(session_id)
        return len(chunks)

    def query(self, session_id: str, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
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
                n_results=min(top_k * 2, count)
            )
            
            if dense_results and dense_results.get("documents") and dense_results["documents"][0]:
                docs = dense_results["documents"][0]
                metas = dense_results["metadatas"][0]
                distances = dense_results["distances"][0] if "distances" in dense_results and dense_results["distances"] else [0.0] * len(docs)
                for i in range(len(docs)):
                    meta = metas[i]
                    if meta.get("superseded_by"):
                        continue
                    dense_docs.append({
                        "act": meta.get("act", filename if 'filename' in locals() else "User Document"),
                        "section": meta.get("section", "General"),
                        "text": docs[i],
                        "score": 1.0 - distances[i]
                    })
        except Exception as exc:
            logger.warning(f"ChromaDB tier2 query warning: {exc}")
            if "InvalidDimensionException" in type(exc).__name__ or "dimensionality" in str(exc):
                try:
                    self.client.delete_collection("tier2_user")
                    self.collection = self.client.get_or_create_collection(
                        name="tier2_user",
                        embedding_function=self.emb_fn
                    )
                    self.invalidate_bm25_cache(session_id)
                except Exception:
                    pass

        # 2. Sparse (BM25) query using per-session cached index
        bm25_inst, documents, metas = self._ensure_bm25_index(session_id)
        if not bm25_inst or not documents:
            return dense_docs[:top_k]

        tokenized_query = text.lower().split()
        scores = bm25_inst.get_scores(tokenized_query)

        bm25_docs = []
        for i, score in enumerate(scores):
            if score > 0:
                meta = metas[i]
                if meta.get("superseded_by"):
                    continue
                bm25_docs.append({
                    "act": meta.get("act", "User Document"),
                    "section": meta.get("section", "General"),
                    "text": documents[i],
                    "score": score
                })
        bm25_docs = sorted(bm25_docs, key=lambda x: x["score"], reverse=True)

        # 3. Fuse rankings
        return fuse_bm25_dense(bm25_docs, dense_docs, top_k=top_k)

