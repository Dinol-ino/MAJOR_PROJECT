import re
from typing import Tuple, Optional

# Regex and keyword rules for Layer 1
INJECTION_KEYWORDS = [
    r"ignore\s+(?:previous|the)\s+instructions",
    r"you\s+are\s+now\s+dan",
    r"system\s+prompt\s+extraction",
    r"role\s+override",
    r"delimiter\s+breaking"
]

SQL_PROBES = [
    r"';\s*drop\s+table",
    r"union\s+select",
    r"or\s+1\s*=\s*1",
    r"exec\s*\(\s*char\("
]

class Layer1InputGuard:
    def __init__(self, max_length: int = 1000):
        self.max_length = max_length

    def validate(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Validates the incoming message against Layer 1 rules.
        Returns:
            Tuple[bool, Optional[str]]: (is_clean, block_reason)
        """
        # 1. Length Check
        if len(message) > self.max_length:
            return False, "Query length exceeds maximum limit."

        # 2. Injection Pattern Checks
        for pattern in INJECTION_KEYWORDS:
            if re.search(pattern, message, re.IGNORECASE):
                return False, f"Potential prompt injection detected (pattern: {pattern})."

        # 3. SQL / Command Injection Probe Checks
        for pattern in SQL_PROBES:
            if re.search(pattern, message, re.IGNORECASE):
                return False, f"Potential SQL/command injection probe detected."

        return True, None
