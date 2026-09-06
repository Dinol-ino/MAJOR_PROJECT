import time
import threading
from collections import OrderedDict
from typing import Any, Optional, Dict, Tuple


class BaseCache:
    """
    Thread-safe, bounded in-memory LRU cache with TTL expiration and observability metrics.
    """

    def __init__(self, max_size: int = 1000, default_ttl_seconds: int = 3600):
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()
        
        # Telemetry metrics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieves a cached value if present and not expired."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            value, expires_at = self._cache[key]
            now = time.time()

            if now > expires_at:
                # Expired item
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Stores a value with bounded LRU eviction and TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = time.time() + ttl

        with self._lock:
            if key in self._cache:
                self._cache[key] = (value, expires_at)
                self._cache.move_to_end(key)
                return

            # Check capacity and evict oldest
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._evictions += 1

            self._cache[key] = (value, expires_at)

    def invalidate(self, key: str) -> bool:
        """Removes a specific key from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clears all entries in the cache."""
        with self._lock:
            self._cache.clear()

    def get_metrics(self) -> Dict[str, Any]:
        """Returns observable cache hit/miss/eviction metrics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = round(self._hits / total_requests, 4) if total_requests > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "total_requests": total_requests,
                "hit_rate": hit_rate,
            }
