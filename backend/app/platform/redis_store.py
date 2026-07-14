from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from redis import Redis

from app.config import settings


@lru_cache(maxsize=2)
def get_redis_client(redis_url: str | None = None) -> Redis:
    return Redis.from_url(
        redis_url or settings.REDIS_URL,
        decode_responses=True,
        health_check_interval=30,
    )


def check_redis_connection(redis_url: str | None = None) -> bool:
    return bool(get_redis_client(redis_url).ping())


class SessionMemoryStore:
    def __init__(self, redis_client: Redis | None = None, ttl_seconds: int | None = None):
        self.redis = redis_client or get_redis_client()
        self.ttl_seconds = ttl_seconds or settings.SESSION_TTL_SECONDS

    @staticmethod
    def _key(session_id: str) -> str:
        return f"dfrag:session:{session_id}"

    def put_context(self, session_id: str, payload: dict[str, Any]) -> None:
        self.redis.set(self._key(session_id), json.dumps(payload), ex=self.ttl_seconds)

    def get_context(self, session_id: str) -> dict[str, Any] | None:
        raw_value = self.redis.get(self._key(session_id))
        if raw_value is None:
            return None
        return json.loads(raw_value)

    def clear_context(self, session_id: str) -> None:
        self.redis.delete(self._key(session_id))
