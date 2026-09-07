import os
import re
import pickle
import logging
import threading
from typing import List, Dict, Any, Optional, Callable
# pyrefly: ignore [missing-import]
from rank_bm25 import BM25Plus

from app.config import settings

logger = logging.getLogger(__name__)


STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when",
    "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "to",
    "from", "up", "down", "in", "out", "on", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "is", "am",
    "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "having", "do", "does", "did", "doing", "would", "should", "could",
    "ought", "i", "you", "he", "she", "it", "we", "they", "this", "that",
    "yes", "no", "hello", "hi", "hey", "can", "please", "help", "thank", "thanks", "what", "which", "who", "whom"
}

def default_tokenizer(text: str) -> List[str]:
    """Tokenizes and normalizes input text for BM25 indexing with stop words removed."""
    if not text:
        return []
    tokens = re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in STOP_WORDS]


class PersistentBM25Index:
    """
    Persistent, incrementally updated BM25 Index (Phase 06).
    Replaces full on-the-fly rebuilds per query with persistent inverted index state.
    """

    def __init__(self, index_name: str = "tier1_bm25", persist_dir: Optional[str] = None):
        self.index_name = index_name
        self.persist_dir = persist_dir or settings.retrieval.bm25_index_dir
        self.persist_path = os.path.join(self.persist_dir, f"{index_name}.pkl")
        self._lock = threading.Lock()
        
        self.documents: List[str] = []
        self.metadatas: List[Dict[str, Any]] = []
        self.doc_ids: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Plus] = None
        self._dirty = False

        self._ensure_dir()
        self.load()

    def _ensure_dir(self):
        if not os.path.exists(self.persist_dir):
            try:
                os.makedirs(self.persist_dir, exist_ok=True)
            except Exception as e:
                logger.debug(f"Could not create BM25 persist dir {self.persist_dir}: {e}")

    def load(self) -> bool:
        """Loads serialized index state from disk if available."""
        with self._lock:
            if not os.path.exists(self.persist_path):
                return False
            try:
                with open(self.persist_path, "rb") as f:
                    data = pickle.load(f)
                    self.documents = data.get("documents", [])
                    self.metadatas = data.get("metadatas", [])
                    self.doc_ids = data.get("doc_ids", [])
                    self.tokenized_corpus = data.get("tokenized_corpus", [])
                    if self.tokenized_corpus:
                        self.bm25 = BM25Plus(self.tokenized_corpus)
                    self._dirty = False
                    logger.info(f"Loaded BM25 index '{self.index_name}' with {len(self.documents)} documents from {self.persist_path}")
                    return True
            except Exception as exc:
                logger.warning(f"Failed to load BM25 index from {self.persist_path}: {exc}")
                return False

    def save(self) -> bool:
        """Persists current index state to disk."""
        with self._lock:
            if not self._dirty:
                return True
            self._ensure_dir()
            try:
                data = {
                    "documents": self.documents,
                    "metadatas": self.metadatas,
                    "doc_ids": self.doc_ids,
                    "tokenized_corpus": self.tokenized_corpus
                }
                with open(self.persist_path, "wb") as f:
                    pickle.dump(data, f)
                self._dirty = False
                logger.debug(f"Saved BM25 index '{self.index_name}' ({len(self.documents)} docs)")
                return True
            except Exception as exc:
                logger.error(f"Failed to save BM25 index '{self.index_name}': {exc}")
                return False

    def count(self) -> int:
        with self._lock:
            return len(self.documents)

    def add_document(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        """Adds or updates a single document in the index."""
        with self._lock:
            tokens = default_tokenizer(text)
            meta = metadata or {}
            
            if doc_id in self.doc_ids:
                idx = self.doc_ids.index(doc_id)
                self.documents[idx] = text
                self.metadatas[idx] = meta
                self.tokenized_corpus[idx] = tokens
            else:
                self.doc_ids.append(doc_id)
                self.documents.append(text)
                self.metadatas.append(meta)
                self.tokenized_corpus.append(tokens)

            self.bm25 = BM25Plus(self.tokenized_corpus)
            self._dirty = True

    def add_documents_batch(
        self,
        doc_ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        """Batch ingestion of documents, rebuilding BM25 internal weights only once per batch."""
        if not doc_ids or not documents:
            return

        with self._lock:
            metas = metadatas or [{} for _ in documents]
            for doc_id, text, meta in zip(doc_ids, documents, metas):
                tokens = default_tokenizer(text)
                if doc_id in self.doc_ids:
                    idx = self.doc_ids.index(doc_id)
                    self.documents[idx] = text
                    self.metadatas[idx] = meta
                    self.tokenized_corpus[idx] = tokens
                else:
                    self.doc_ids.append(doc_id)
                    self.documents.append(text)
                    self.metadatas.append(meta)
                    self.tokenized_corpus.append(tokens)

            if self.tokenized_corpus:
                self.bm25 = BM25Plus(self.tokenized_corpus)
            self._dirty = True

        self.save()

    def delete_document(self, doc_id: str) -> bool:
        """Deletes a document by ID."""
        with self._lock:
            if doc_id not in self.doc_ids:
                return False
            idx = self.doc_ids.index(doc_id)
            self.doc_ids.pop(idx)
            self.documents.pop(idx)
            self.metadatas.pop(idx)
            self.tokenized_corpus.pop(idx)
            if self.tokenized_corpus:
                self.bm25 = BM25Plus(self.tokenized_corpus)
            else:
                self.bm25 = None
            self._dirty = True
        self.save()
        return True

    def clear(self):
        """Clears all indexed documents."""
        with self._lock:
            self.documents = []
            self.metadatas = []
            self.doc_ids = []
            self.tokenized_corpus = []
            self.bm25 = None
            self._dirty = True
        self.save()

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes sparse BM25 retrieval without rebuilding the corpus.
        Filters out superseded documents by default if configured.
        """
        with self._lock:
            if not self.bm25 or not self.documents:
                return []

            query_tokens = default_tokenizer(query)
            if not query_tokens:
                return []

            scores = self.bm25.get_scores(query_tokens)
            
            results = []
            for i, score in enumerate(scores):
                if score <= 0.0:
                    continue
                meta = self.metadatas[i]
                
                # Check filter condition
                if filter_fn and not filter_fn(meta):
                    continue

                # Superseded provision exclusion check (Phase 06 Requirement)
                if settings.retrieval.exclude_superseded and meta.get("superseded_by"):
                    continue

                results.append({
                    "id": self.doc_ids[i],
                    "act": meta.get("act", "General Law"),
                    "section": meta.get("section", "General"),
                    "text": self.documents[i],
                    "score": float(score),
                    "metadata": meta
                })

            # Sort by BM25 score descending
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]


# Global instance for Tier-1 law collection
tier1_bm25_index = PersistentBM25Index(index_name="tier1_law_bm25")
