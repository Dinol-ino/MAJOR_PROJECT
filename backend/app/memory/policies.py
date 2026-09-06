import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from app.config import settings


class MemoryPolicy:
    """
    Shared policy rules for retention, deduplication, provenance, and user isolation.
    """

    ALLOWED_SEMANTIC_CATEGORIES = {
        "preference",
        "fact",
        "legal_facts",
        "entity",
        "jurisdiction",
        "practice_area",
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
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "epoch_ts": time.time(),
        }

    @staticmethod
    def is_expired(created_at: datetime, retention_days: int) -> bool:
        """Checks if a memory record has exceeded its retention TTL."""
        if not created_at or retention_days <= 0:
            return False
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        return created_at < cutoff

    @staticmethod
    def validate_user_access(resource_user_id: str, authenticated_user_id: str) -> bool:
        """Enforces identity isolation: users can only access their own memory layers."""
        if not resource_user_id or not authenticated_user_id:
            return False
        return resource_user_id == authenticated_user_id


policies = MemoryPolicy()
