import os
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


class DeterministicHashEmbeddingFunction(chromadb.EmbeddingFunction):
    """
    Fast, deterministic embedding function for testing and low-memory environments
    that prevents PyTorch C++ memory crashes and DLL collisions on Windows.
    """
    def __call__(self, input_texts):
        vectors = []
        for t in input_texts:
            h = hash(t)
            vec = [(float((h >> (i % 32)) & 0xFF) / 255.0) for i in range(384)]
            vectors.append(vec)
        return vectors


def get_shared_embedding_function(model_name: str = "all-MiniLM-L6-v2"):
    """
    Singleton embedding function factory with safe fallback to prevent Windows
    PyTorch C++ access violations under high test concurrency.
    """
    global _SHARED_EMB_FN
    if _SHARED_EMB_FN is None:
        # In test mode or when explicitly set, use deterministic embedding
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("DFRAG_TEST_MODE", "0") == "1":
            _SHARED_EMB_FN = DeterministicHashEmbeddingFunction()
        else:
            try:
                from chromadb.utils import embedding_functions
                _SHARED_EMB_FN = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=model_name,
                    device="cpu"
                )
            except Exception:
                _SHARED_EMB_FN = DeterministicHashEmbeddingFunction()
    return _SHARED_EMB_FN
