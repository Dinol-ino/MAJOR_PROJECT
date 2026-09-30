"""
Single choke point for data leaving the machine.

Policy (enforced inside CloudRuntime, so no call site can forget it):
  1. Cloud generation only runs when the operator has explicitly enabled it
     (CLOUD_FALLBACK_ENABLED / the settings API). Off by default.
  2. Private material - documents from a user's vault or session uploads - never goes to a
     cloud provider, whatever the settings say. A request is "private" if its evidence
     contains any such chunk, or if it is scoped to a vault.

The flag lives in a ContextVar, so it is per-request and cannot leak between concurrent
requests. It is set where evidence is assembled (mark_private_from_chunks) and read where
the network call is made (CloudRuntime.generate / generate_stream).
"""
from contextvars import ContextVar, Token
from typing import Iterable, Optional

PRIVATE_DOC_TYPES = frozenset({"vault_document", "user_document"})

_private: ContextVar[Optional[str]] = ContextVar("dfrag_private_context", default=None)


def mark_private_context(reason: str = "private material in request") -> Token:
    return _private.set(reason)


def reset_private_context(token: Optional[Token]) -> None:
    if token is not None:
        try:
            _private.reset(token)
        except ValueError:
            _private.set(None)


def is_private_context() -> bool:
    return _private.get() is not None


def private_reason() -> Optional[str]:
    return _private.get()


def mark_private_from_chunks(chunks: Iterable[dict]) -> Optional[Token]:
    """Marks the request private if any evidence chunk is user/vault material. Returns the token (or None)."""
    for c in chunks or []:
        meta = c.get("metadata") or {}
        if (c.get("doc_type") or meta.get("doc_type")) in PRIVATE_DOC_TYPES:
            return mark_private_context("user document evidence in prompt")
    return None
