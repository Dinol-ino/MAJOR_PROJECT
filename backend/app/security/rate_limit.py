"""Shared slowapi rate limiter (import-safe: no FastAPI app dependency)."""
import os
import sys
from slowapi import Limiter
from slowapi.util import get_remote_address

class DynamicTestLimiter(Limiter):
    @property
    def enabled(self) -> bool:
        if (
            "pytest" in sys.modules
            or os.environ.get("PYTEST_CURRENT_TEST")
            or os.environ.get("TESTING") == "1"
            or os.environ.get("DFRAG_TEST_MODE") == "1"
            or os.environ.get("AUTH_DISABLED_FOR_TESTS") == "1"
        ):
            return False
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

limiter = DynamicTestLimiter(
    key_func=get_remote_address,
    default_limits=["100/minute"]
)

