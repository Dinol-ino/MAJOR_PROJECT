"""
Performance & Intelligent Caching Package (L1–L3).

Layers:
- L1 Process Cache: Fast in-process request deduplication.
- L2 Retrieval Cache: Normalized query + corpus-versioned retrieval results.
- L3 Embedding Cache: Exact text hash dense vector embeddings.

Explicit Architectural Invariants:
- L4 Model/Prompt Cache: REJECTED by default (handled internally by Ollama KV-cache).
- L5 Response Cache: REJECTED by default (avoids serving stale legal advice across dynamic conversation contexts).
"""

from app.cache.base import BaseCache
from app.cache.keys import (
    normalize_query_text,
    hash_text,
    make_l1_process_key,
    make_l2_retrieval_key,
    make_l3_embedding_key,
)
from app.cache.l1_process_cache import l1_cache, L1ProcessCache
from app.cache.l2_retrieval_cache import l2_retrieval_cache, L2RetrievalCache
from app.cache.l3_embedding_cache import l3_embedding_cache, L3EmbeddingCache

__all__ = [
    "BaseCache",
    "normalize_query_text",
    "hash_text",
    "make_l1_process_key",
    "make_l2_retrieval_key",
    "make_l3_embedding_key",
    "l1_cache",
    "L1ProcessCache",
    "l2_retrieval_cache",
    "L2RetrievalCache",
    "l3_embedding_cache",
    "L3EmbeddingCache",
]
