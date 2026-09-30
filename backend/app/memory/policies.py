import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from app.config import settings


class MemoryPolicy:
    """
    Shared policy rules for retention, deduplication, provenance, and user isolation.
    """

    ALLOWED_SEMANTIC_CATEGORIES = {
        "preference",
        "jurisdiction",
        "practice_area",
        "user_profile",
        "citation_format",
        "fact",
        "entity",
    }


    @staticmethod
    def compute_hash(text: str) -> str:
        """Generates normalized SHA-256 content hash for deduplication."""
        normalized = " ".join(text.lower().strip().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def stamp_provenance(user_id: str, source: str = "user_input", session_id: Optional[str] = None) -> Dict[str, Any]:
        """Stamps authorship, timestamp, and origin metadata for memory entries."""
        return {
            "created_by": user_id,
            "source": source,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epoch_ts": time.time(),
        }

    @staticmethod
    def as_utc(value: datetime) -> datetime:
        """Normalises a timestamp to aware UTC.

        Rows written before the timezone fix are naive; rows written after are aware.
        Comparing the two raises TypeError, so both are coerced here. A naive value is
        assumed to be UTC, which is what the old code intended when it called utcnow().
        """
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def is_expired(created_at: datetime, retention_days: int) -> bool:
        """Checks if a memory record has exceeded its retention TTL."""
        if not created_at or retention_days <= 0:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        return MemoryPolicy.as_utc(created_at) < cutoff

    @staticmethod
    def validate_user_access(resource_user_id: str, authenticated_user_id: str) -> bool:
        """Enforces identity isolation: users can only access their own memory layers."""
        if not resource_user_id or not authenticated_user_id:
            return False
        return resource_user_id == authenticated_user_id


policies = MemoryPolicy()
