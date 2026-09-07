import logging
from typing import Optional, List, Dict, Any
from app.cache.base import BaseCache
from app.cache.keys import make_l2_retrieval_key
from app.config import settings

logger = logging.getLogger(__name__)


class L2RetrievalCache:
    """
    Layer 2 (L2) Retrieval Results Cache:
    Caches hybrid retrieval results (dense + sparse BM25) keyed by normalized query,
    corpus version, and retrieval parameters.
    Eliminates expensive BM25 and vector search on identical lookups.
    Automatically invalidates on corpus version updates.
    """

    def __init__(self):
        max_size = settings.performance.l2_retrieval_cache_max_size
        ttl = settings.performance.l2_retrieval_cache_ttl_seconds
        self._cache = BaseCache(max_size=max_size, default_ttl_seconds=ttl)

    @property
    def enabled(self) -> bool:
        return settings.performance.cache_enabled

    @property
    def corpus_version(self) -> str:
        return settings.performance.corpus_version_hash

    def get_tier1_results(self, query: str, top_k: int) -> Optional[List[Dict[str, Any]]]:
        if not self.enabled:
            return None
        key = make_l2_retrieval_key(
            query=query,
            top_k=top_k,
            corpus_version=self.corpus_version,
            tier="tier1"
        )
        results = self._cache.get(key)
        if results is not None:
            logger.debug(f"[L2 Tier1 Cache HIT] query='{query[:30]}...' top_k={top_k}")
        return results

    def set_tier1_results(self, query: str, top_k: int, results: List[Dict[str, Any]]) -> None:
        if not self.enabled or not results:
            return
        key = make_l2_retrieval_key(
            query=query,
            top_k=top_k,
            corpus_version=self.corpus_version,
            tier="tier1"
        )
        self._cache.set(key, results)

    def get_tier2_results(
        self,
        query: str,
        top_k: int,
        user_id: str,
        session_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        if not self.enabled:
            return None
        key = make_l2_retrieval_key(
            query=query,
            top_k=top_k,
            corpus_version=self.corpus_version,
            tier="tier2",
            user_id=user_id,
            session_id=session_id
        )
        results = self._cache.get(key)
        if results is not None:
            logger.debug(f"[L2 Tier2 Cache HIT] user={user_id} session={session_id}")
        return results

    def set_tier2_results(
        self,
        query: str,
        top_k: int,
        user_id: str,
        session_id: str,
        results: List[Dict[str, Any]]
    ) -> None:
        if not self.enabled or not results:
            return
        key = make_l2_retrieval_key(
            query=query,
            top_k=top_k,
            corpus_version=self.corpus_version,
            tier="tier2",
            user_id=user_id,
            session_id=session_id
        )
        self._cache.set(key, results)

    def get_metrics(self) -> Dict[str, Any]:
        metrics = self._cache.get_metrics()
        metrics["corpus_version"] = self.corpus_version
        return metrics

    def clear(self) -> None:
        self._cache.clear()


l2_retrieval_cache = L2RetrievalCache()
