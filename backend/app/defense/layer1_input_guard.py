import re
import hashlib
from typing import Tuple, Optional, Dict, Any

# Regex and keyword rules for Layer 1
INJECTION_KEYWORDS = [
    r"ignore\s+(?:previous|the|all)\s+instructions",
    r"you\s+are\s+now\s+dan",
    r"system\s+prompt\s+extraction",
    r"role\s+override",
    r"delimiter\s+breaking",
    r"forget\s+(?:everything|your\s+rules)",
    r"reveal\s+system\s+prompt"
]

SQL_PROBES = [
    r"';\s*drop\s+table",
    r"union\s+select",
    r"or\s+1\s*=\s*1",
    r"exec\s*\(\s*char\("
]

class Layer1InputGuard:
    def __init__(self, max_length: int = 1000, risk_threshold: float = 0.7):
        self.max_length = max_length
        self.risk_threshold = risk_threshold
        # Cache keyed on SHA-256 hash of normalized query to ensure deduplication
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_query_hash(self, message: str) -> str:
        """Computes SHA-256 hash of the normalized query string."""
        normalized = message.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def validate_with_score(self, message: str) -> Tuple[bool, Optional[str], float, str]:
        """
        Validates incoming message against Layer 1 rules with deduplicated query hash caching.
        Returns:
            Tuple[bool, Optional[str], float, str]: (is_safe, block_reason, injection_score, query_hash)
        """
        query_hash = self.get_query_hash(message)

        # Check cache for deduplication (Layer 1 / Layer 1.5 deduplication)
        if query_hash in self._cache:
            cached = self._cache[query_hash]
            return cached["is_safe"], cached["block_reason"], cached["injection_score"], query_hash

        # 1. Length Check
        if len(message) > self.max_length:
            result = (False, "Query length exceeds maximum limit.", 1.0, query_hash)
            self._cache[query_hash] = {"is_safe": False, "block_reason": result[1], "injection_score": 1.0}
            return result

        score = 0.0

        # 2. Injection Pattern Checks
        for pattern in INJECTION_KEYWORDS:
            if re.search(pattern, message, re.IGNORECASE):
                score = max(score, 0.95)
                block_reason = f"Potential prompt injection detected (pattern: {pattern})."
                self._cache[query_hash] = {"is_safe": False, "block_reason": block_reason, "injection_score": score}
                return False, block_reason, score, query_hash

        # 3. SQL / Command Injection Probe Checks
        for pattern in SQL_PROBES:
            if re.search(pattern, message, re.IGNORECASE):
                score = max(score, 0.90)
                block_reason = "Potential SQL/command injection probe detected."
                self._cache[query_hash] = {"is_safe": False, "block_reason": block_reason, "injection_score": score}
                return False, block_reason, score, query_hash

        # 4. Score-based Hard Gate evaluation
        is_safe = score < self.risk_threshold
        block_reason = None if is_safe else f"Injection risk score ({score:.2f}) exceeds threshold ({self.risk_threshold})."

        self._cache[query_hash] = {"is_safe": is_safe, "block_reason": block_reason, "injection_score": score}
        return is_safe, block_reason, score, query_hash

    def validate(self, message: str) -> Tuple[bool, Optional[str]]:
        """Backwards compatible validate method."""
        is_safe, block_reason, _, _ = self.validate_with_score(message)
        return is_safe, block_reason

