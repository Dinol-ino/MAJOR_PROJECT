"""
Regression tests for the Phase 1 high-severity fixes.

Each of these guarded a guarantee the README makes and was violated before:
  #1 was withdrawn: returning an unavailable tag is deliberate (see the test below)
  #2 a verified token stayed cached for its full 7-day life, surviving revocation
  #3 default_limits never applied, leaving /chat, /upload and /research unlimited
"""
import asyncio
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import register_user

client = TestClient(app)


# --------------------------------------------------------------- #1 model state
def _svc_with(models, online=True):
    from app.runtime.model_state import ModelStateService

    svc = ModelStateService()

    async def fake_tags(force=False):
        return {"online": online, "models": [{"name": m} for m in models], "checked_at": "x"}

    svc.list_installed = fake_tags
    return svc


def test_offline_runtime_still_resolves_so_the_pipeline_can_degrade_honestly():
    """
    An unavailable model is deliberately still returned.

    The chat route turns ModelNotAvailable into a 409 before retrieval runs, so raising
    here would throw away the retrieved evidence and replace an honest degraded answer
    ("the local model did not produce an answer", sources intact,
    failure_kind="model_unavailable") with a bare error. Retrieval must run regardless;
    the model failure is reported downstream.
    """
    svc = _svc_with([], online=False)
    svc._active_cache, svc._active_loaded = "qwen2.5:3b", True
    assert asyncio.run(svc.resolve_for_request(None)) == "qwen2.5:3b"


def test_explicitly_requested_uninstalled_model_is_still_refused():
    """The honest-degradation path above must not weaken an explicit bad request."""
    from app.runtime.model_state import ModelNotAvailable

    svc = _svc_with(["llama3.2:3b"], online=True)
    with pytest.raises(ModelNotAvailable) as exc:
        asyncio.run(svc.resolve_for_request("qwen2.5:3b"))
    assert exc.value.code == "model_not_installed"


def test_no_model_at_all_is_reported():
    from app.runtime.model_state import ModelNotAvailable

    svc = _svc_with([], online=True)
    svc._active_cache, svc._active_loaded = None, True
    with pytest.raises(ModelNotAvailable) as exc:
        asyncio.run(svc.resolve_for_request(None))
    assert exc.value.code == "no_active_model"


def test_installed_active_model_still_resolves():
    svc = _svc_with(["qwen2.5:3b"], online=True)
    svc._active_cache, svc._active_loaded = "qwen2.5:3b", True
    assert asyncio.run(svc.resolve_for_request(None)) == "qwen2.5:3b"


# --------------------------------------------------------------- #2 token cache
def test_revoked_token_stops_working_immediately_even_when_cached():
    """Logout must take effect on the next request, not when the token expires."""
    from app.routes import auth as auth_module

    _, headers = register_user(client, "revoke")

    # Prime the cache with a verified request.
    assert client.get("/auth/me", headers=headers).status_code == 200
    token = headers["Authorization"].split(" ", 1)[1]
    assert auth_module._TOKEN_CACHE.get(token) is not None, "expected a cache entry"

    # Revoke the jti only, leaving the cache entry in place, which is exactly the
    # state a logout served by another worker would produce.
    payload = auth_module._decode_payload(token)
    auth_module._REVOKED.revoke(payload["jti"], float(payload["exp"]))

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_verified_token_is_not_cached_for_its_whole_lifetime():
    """The cache is a request-level optimisation, not a session extension."""
    from app.routes import auth as auth_module

    _, headers = register_user(client, "ttl")
    assert client.get("/auth/me", headers=headers).status_code == 200

    token = headers["Authorization"].split(" ", 1)[1]
    entry = auth_module._TOKEN_CACHE._data.get(token)
    assert entry is not None
    _, cached_until = entry

    assert cached_until - time.time() <= auth_module._TOKEN_CACHE_TTL_SECONDS + 1
    # ...and far short of the token's own expiry.
    assert cached_until < float(auth_module._decode_payload(token)["exp"])


def test_logout_still_revokes_immediately():
    _, headers = register_user(client, "logout")
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401


# --------------------------------------------------------------- #3 rate limiting
def test_rate_limit_middleware_is_registered():
    """
    slowapi applies default_limits only through SlowAPIMiddleware. Without it the
    expensive endpoints are unlimited however RATE_LIMIT_DEFAULT is configured.

    The limiter itself is disabled under pytest (DynamicTestLimiter), so this asserts
    the wiring rather than driving a real 429.
    """
    from slowapi.middleware import SlowAPIMiddleware

    assert any(m.cls is SlowAPIMiddleware for m in app.user_middleware), (
        "SlowAPIMiddleware is not registered: default_limits would never be applied"
    )
    assert app.state.limiter is not None, "app.state.limiter must be set for slowapi"


def test_default_limit_is_configured():
    """RATE_LIMIT_DEFAULT must actually reach the limiter, not sit unused."""
    from app.security.rate_limit import limiter

    assert limiter._default_limits, "no default limits configured on the limiter"
