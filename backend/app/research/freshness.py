import re
import time
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FreshnessResult(BaseModel):
    requires_freshness: bool
    reason: str
    confidence: float = 1.0
    recommended_source_category: Optional[str] = None
    target_statute_hint: Optional[str] = None


class FreshnessDetector:
    """
    Freshness Detection Engine (Phase 10).
    Determines whether a legal query requires live statutory / gazette verification
    (e.g., whether an Act has been amended, repealed, or superseded by recent codes like BNS 2023).
    """

    FRESHNESS_KEYWORDS = [
        "latest", "current", "amendment", "amended", "repealed", "repeal",
        "in force", "valid today", "recent", "notification", "gazette",
        "bns", "bnss", "bsa", "bharatiya nyaya", "bharatiya nagarik",
        "2023 amendment", "2024", "2025", "2026", "is section still",
        "new law", "replaced by", "stay order", "overruled"
    ]

    def __init__(self, staleness_threshold_days: int = 90):
        self.staleness_threshold_seconds = staleness_threshold_days * 86400

    def detect(self, query: str, local_metadata: Optional[List[Dict[str, Any]]] = None) -> FreshnessResult:
        """
        Evaluates query string and corpus chunk metadata for freshness requirements.
        """
        q_lower = query.lower()

        # 1. Deterministic Heuristic Analysis on Query
        for kw in self.FRESHNESS_KEYWORDS:
            if kw in q_lower:
                category = "CURRENT_LAW"
                if "case" in q_lower or "judgment" in q_lower or "overruled" in q_lower:
                    category = "CASE_LAW_SEARCH"
                elif "gazette" in q_lower or "notification" in q_lower:
                    category = "GOVERNMENT_SOURCE"

                return FreshnessResult(
                    requires_freshness=True,
                    reason=f"Query explicitly queries live temporal status (matched: '{kw}').",
                    confidence=0.95,
                    recommended_source_category=category,
                    target_statute_hint=self._extract_statute_hint(query)
                )

        # 2. Corpus Metadata Staleness & Superseded Flag Check
        if local_metadata:
            now = time.time()
            for meta in local_metadata:
                if not isinstance(meta, dict):
                    continue
                # Check if flagged superseded in corpus
                if meta.get("is_superseded") or meta.get("superseded_by"):
                    return FreshnessResult(
                        requires_freshness=True,
                        reason=f"Corpus record for {meta.get('act', 'statute')} is flagged as superseded by {meta.get('superseded_by', 'newer enactment')}.",
                        confidence=1.0,
                        recommended_source_category="CURRENT_LAW",
                        target_statute_hint=meta.get("act")
                    )
                # Check staleness timestamp
                last_verified = meta.get("last_verified_at")
                if last_verified and isinstance(last_verified, (int, float)):
                    if (now - last_verified) > self.staleness_threshold_seconds:
                        days_old = int((now - last_verified) / 86400)
                        return FreshnessResult(
                            requires_freshness=True,
                            reason=f"Corpus data for {meta.get('act', 'statute')} last verified {days_old} days ago (> {int(self.staleness_threshold_seconds / 86400)} days threshold).",
                            confidence=0.85,
                            recommended_source_category="CURRENT_LAW",
                            target_statute_hint=meta.get("act")
                        )

        return FreshnessResult(
            requires_freshness=False,
            reason="Query concerns settled statutory law with up-to-date corpus verification.",
            confidence=0.90,
            recommended_source_category=None
        )

    def _extract_statute_hint(self, query: str) -> Optional[str]:
        q_lower = query.lower()
        if "bns" in q_lower or "bharatiya nyaya sanhita" in q_lower:
            return "Bharatiya Nyaya Sanhita, 2023"
        if "bnss" in q_lower or "bharatiya nagarik" in q_lower:
            return "Bharatiya Nagarik Suraksha Sanhita, 2023"
        if "bsa" in q_lower or "bharatiya sakshya" in q_lower:
            return "Bharatiya Sakshya Adhiniyam, 2023"
        if "ipc" in q_lower or "indian penal code" in q_lower:
            return "Indian Penal Code, 1860"
        if "crpc" in q_lower or "code of criminal procedure" in q_lower:
            return "Code of Criminal Procedure, 1973"
        if "it act" in q_lower or "information technology" in q_lower:
            return "Information Technology Act, 2000"
        return None


freshness_detector = FreshnessDetector()
