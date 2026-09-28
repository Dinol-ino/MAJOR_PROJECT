import os
import hashlib
import logging
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Dict, Any

_SHARED_CLIENTS: Dict[str, Any] = {}


def get_shared_chroma_client(persist_dir: str):
    """
    Singleton ChromaDB client factory to prevent duplicate initialization
    and settings mismatch errors within the same process.
    """
    global _SHARED_CLIENTS
    norm_path = os.path.abspath(persist_dir)
    if norm_path not in _SHARED_CLIENTS:
        _SHARED_CLIENTS[norm_path] = chromadb.PersistentClient(
            path=norm_path,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                is_persistent=True
            )
        )
    return _SHARED_CLIENTS[norm_path]


_SHARED_EMB_FN = None
_DENSE_STATUS: Dict[str, Any] = {"available": None, "backend": None, "reason": None}

logger = logging.getLogger(__name__)


class DenseRetrievalUnavailable(RuntimeError):
    """Raised when no real embedding model is loaded; callers fall back to lexical (BM25) retrieval."""


class DeterministicHashEmbeddingFunction(chromadb.EmbeddingFunction):
    """
    Deterministic, process-stable pseudo-embedding for automated tests ONLY.
    Uses SHA-256 (Python's hash() is salted per process and would corrupt persisted vectors).
    It carries no semantic meaning and is never used outside test mode.
    """
    def __call__(self, input_texts):
        vectors = []
        for t in input_texts:
            digest = hashlib.sha256(t.encode("utf-8", errors="ignore")).digest()
            vectors.append([digest[i % len(digest)] / 255.0 for i in range(384)])
        return vectors


class UnavailableEmbeddingFunction(chromadb.EmbeddingFunction):
    """Placeholder that refuses to embed so meaningless vectors are never written or queried."""
    def __call__(self, input_texts):
        raise DenseRetrievalUnavailable("Embedding model unavailable; dense retrieval disabled.")


def _test_mode() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("DFRAG_TEST_MODE", "0") == "1"


def dense_retrieval_status() -> Dict[str, Any]:
    return dict(_DENSE_STATUS)


def get_shared_embedding_function(model_name: str = "all-MiniLM-L6-v2"):
    """
    Singleton embedding function factory.

    - Test mode: deterministic SHA-256 vectors (no model download, hermetic).
    - Otherwise: the configured sentence-transformers model loaded locally (no network if cached).
    - If that fails: dense retrieval is DISABLED (lexical BM25 continues). Garbage vectors are never produced.
    """
    global _SHARED_EMB_FN
    if _SHARED_EMB_FN is None:
        if _test_mode():
            _SHARED_EMB_FN = DeterministicHashEmbeddingFunction()
            _DENSE_STATUS.update({"available": True, "backend": "test-deterministic", "reason": None})
        else:
            try:
                from chromadb.utils import embedding_functions
                _SHARED_EMB_FN = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=model_name,
                    device=os.getenv("EMBEDDING_DEVICE", "cpu"),
                )
                _DENSE_STATUS.update({"available": True, "backend": f"sentence-transformers:{model_name}", "reason": None})
            except Exception as exc:
                logger.error(
                    "Embedding model '%s' could not be loaded (%s). Dense retrieval is DISABLED; "
                    "lexical BM25 retrieval continues.", model_name, type(exc).__name__,
                )
                _SHARED_EMB_FN = UnavailableEmbeddingFunction()
                _DENSE_STATUS.update({"available": False, "backend": None, "reason": type(exc).__name__})
    return _SHARED_EMB_FN
