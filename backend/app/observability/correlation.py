import uuid
import contextvars
from contextlib import contextmanager
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_CORRELATION_ID_CTX: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def generate_correlation_id() -> str:
    """Generates a structured, unique request correlation ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


def get_correlation_id() -> str:
    """Retrieves the current request correlation ID, or initializes a new one if unset."""
    corr_id = _CORRELATION_ID_CTX.get()
    if not corr_id:
        corr_id = generate_correlation_id()
        _CORRELATION_ID_CTX.set(corr_id)
    return corr_id


def set_correlation_id(corr_id: str) -> None:
    """Sets the active correlation ID in the current async context."""
    _CORRELATION_ID_CTX.set(corr_id)


@contextmanager
def correlation_context(corr_id: Optional[str] = None):
    """Context manager scoping a correlation ID to a block of execution."""
    token = _CORRELATION_ID_CTX.set(corr_id or generate_correlation_id())
    try:
        yield _CORRELATION_ID_CTX.get()
    finally:
        _CORRELATION_ID_CTX.reset(token)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette Middleware that propagates X-Correlation-ID across all requests.
    """
    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("X-Correlation-ID") or generate_correlation_id()
        set_correlation_id(corr_id)
        request.state.correlation_id = corr_id

        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
