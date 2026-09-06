import logging
from fastapi import APIRouter
from app.cache import l1_cache, l2_retrieval_cache, l3_embedding_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/metrics")
def get_cache_metrics():
    """
    Returns observable telemetry metrics across L1, L2, and L3 cache layers.
    Feeds Phase 11 observability and profiling.
    """
    return {
        "status": "ok",
        "layers": {
            "l1_process": l1_cache.get_metrics(),
            "l2_retrieval": l2_retrieval_cache.get_metrics(),
            "l3_embedding": l3_embedding_cache.get_metrics(),
        },
        "architectural_decisions": {
            "l1_process_cache": "IMPLEMENTED (bounded LRU, request deduplication)",
            "l2_retrieval_cache": "IMPLEMENTED (hybrid BM25/dense results, corpus-versioned)",
            "l3_embedding_cache": "IMPLEMENTED (dense vectors, exact text hash)",
            "l4_model_prompt_cache": "REJECTED (Ollama native KV-cache manages context reuse)",
            "l5_response_cache": "REJECTED (legal answers are stateful and context-dependent; prevents stale outputs)",
        }
    }


@router.post("/clear")
def clear_all_caches():
    """Flushes L1, L2, and L3 caches."""
    l1_cache.clear()
    l2_retrieval_cache.clear()
    l3_embedding_cache.clear()
    return {"status": "ok", "message": "All L1-L3 cache layers flushed successfully."}
