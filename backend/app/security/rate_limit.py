"""Shared slowapi rate limiter (import-safe: no FastAPI app dependency)."""
import os
import sys
from slowapi import Limiter
from slowapi.util import get_remote_address


class DynamicTestLimiter(Limiter):
    """Rate limiting is disabled only inside an in-process pytest run.

    Environment variables cannot switch it off, so a misconfigured deployment
    can never silently lose brute-force protection.
    """

    @property
    def enabled(self) -> bool:
        if "pytest" in sys.modules:
            return False
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value


limiter = DynamicTestLimiter(
    key_func=get_remote_address,
    default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "100/minute")],
)
