import logging
from typing import Optional, List
from app.cache.base import BaseCache
from app.cache.keys import make_l3_embedding_key
from app.config import settings

logger = logging.getLogger(__name__)


class L3EmbeddingCache:
    """
    Layer 3 (L3) Embedding Vector Cache:
    Caches calculated dense embedding vectors for text snippets keyed on exact text hash
    and embedding model name.
    Eliminates redundant embedding calculation during multi-turn queries.
    """

    def __init__(self):
        max_size = settings.performance.l3_embedding_cache_max_size
        ttl = settings.performance.l3_embedding_cache_ttl_seconds
        self._cache = BaseCache(max_size=max_size, default_ttl_seconds=ttl)
        self._ram_ok: Optional[bool] = None

    def _ram_allows_cache(self) -> bool:
        # Low-RAM machines skip the dense-vector cache to prevent RAM exhaustion (Fault 01).
        # Total RAM does not change at runtime, so this is measured once.
        if self._ram_ok is None:
            import os
            min_ram_gb = float(os.getenv("L3_EMBEDDING_CACHE_MIN_RAM_GB", "8.5"))
            try:
                import psutil
                self._ram_ok = psutil.virtual_memory().total / (1024 ** 3) > min_ram_gb
            except Exception:
                self._ram_ok = True
        return self._ram_ok

    @property
    def enabled(self) -> bool:
        if not settings.performance.cache_enabled:
            return False
        return self._ram_allows_cache()

    def get_embedding(self, text: str, model_name: str) -> Optional[List[float]]:
        if not self.enabled or not text:
            return None
        key = make_l3_embedding_key(text=text, model_name=model_name)
        embedding = self._cache.get(key)
        if embedding is not None:
            logger.debug(f"[L3 Embedding Cache HIT] model={model_name}")
        return embedding

    def set_embedding(self, text: str, model_name: str, embedding: List[float]) -> None:
        if not self.enabled or not text or not embedding:
            return
        key = make_l3_embedding_key(text=text, model_name=model_name)
        self._cache.set(key, embedding)

    def get_metrics(self):
        return self._cache.get_metrics()

    def clear(self):
        self._cache.clear()


l3_embedding_cache = L3EmbeddingCache()
