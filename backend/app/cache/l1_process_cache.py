import logging
from typing import Optional, Any
from app.cache.base import BaseCache
from app.cache.keys import make_l1_process_key
from app.config import settings

logger = logging.getLogger(__name__)


class L1ProcessCache:
    """
    Layer 1 (L1) In-Process Cache:
    Catches exact duplicate requests within a short timeframe (e.g. UI double-submits, rapid repeated actions).
    Bounded in-memory LRU with short TTL.
    """

    def __init__(self):
        max_size = settings.performance.l1_cache_max_size
        ttl = settings.performance.l1_cache_ttl_seconds
        self._cache = BaseCache(max_size=max_size, default_ttl_seconds=ttl)

    @property
    def enabled(self) -> bool:
        return settings.performance.cache_enabled

    def get_response(self, session_id: str, raw_query: str) -> Optional[Any]:
        if not self.enabled:
            return None
        key = make_l1_process_key(session_id, raw_query)
        result = self._cache.get(key)
        if result is not None:
            logger.debug(f"[L1 Cache HIT] session={session_id}")
        return result

    def set_response(self, session_id: str, raw_query: str, response_data: Any) -> None:
        if not self.enabled:
            return
        key = make_l1_process_key(session_id, raw_query)
        self._cache.set(key, response_data)

    def invalidate_session(self, session_id: str) -> None:
        """Clears L1 cache entries or resets state."""
        # For simplicity, L1 items expire quickly via TTL (60s default)
        pass

    def get_metrics(self):
        return self._cache.get_metrics()

    def clear(self):
        self._cache.clear()


l1_cache = L1ProcessCache()
