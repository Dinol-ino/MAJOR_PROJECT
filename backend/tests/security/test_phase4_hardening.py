"""
Regression tests for the Phase 4 findings (medium and low severity).
"""
import time

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import register_user

client = TestClient(app)


# ------------------------------------------------------------------ #4 timing
def test_unknown_user_still_pays_the_password_verification_cost():
    """
    Short-circuiting on a missing user leaks account existence through response time.
    Compare the work done for an unknown user against a known one with a wrong password.
    """
    from app.routes.auth import _verify_login, _hash_password

    real = _hash_password("the-real-password")

    t0 = time.perf_counter()
    assert _verify_login("wrong-password", real) is False
    known_ms = time.perf_counter() - t0

    t0 = time.perf_counter()
    assert _verify_login("wrong-password", None) is False
    unknown_ms = time.perf_counter() - t0

    # Same order of magnitude: the unknown-user path must not be an order faster.
    assert unknown_ms > known_ms * 0.5, (
        f"unknown-user path is far faster ({unknown_ms:.4f}s vs {known_ms:.4f}s): "
        "account existence is observable through timing"
    )


# ------------------------------------------------------------------ #5 pbkdf2
def test_password_hash_records_its_iteration_count():
    from app.routes.auth import _hash_password, _verify_password, _PBKDF2_ITERATIONS

    h = _hash_password("correct horse battery staple")
    salt, iterations, key = h.split("$")
    assert int(iterations) == _PBKDF2_ITERATIONS >= 600_000
    assert _verify_password("correct horse battery staple", h)
    assert not _verify_password("wrong", h)


def test_legacy_two_part_hashes_still_verify():
    """Accounts created before the upgrade must keep working."""
    import hashlib
    from app.routes.auth import _verify_password, _LEGACY_PBKDF2_ITERATIONS

    salt = "0123456789abcdef0123456789abcdef"
    key = hashlib.pbkdf2_hmac("sha256", b"legacy-pw", salt.encode(), _LEGACY_PBKDF2_ITERATIONS)
    assert _verify_password("legacy-pw", f"{salt}${key.hex()}")
    assert not _verify_password("other", f"{salt}${key.hex()}")


# ------------------------------------------------------- #6 registration policy
def test_registration_can_be_closed_once_the_workspace_has_an_owner(monkeypatch):
    from app.config import settings

    register_user(client, "openreg")  # workspace now has accounts

    monkeypatch.setattr(settings.auth, "registration_open", False)
    resp = client.post("/auth/register", json={
        "username": "should_be_refused",
        "email": "refused@example.com",
        "password": "Str0ngPass!word",
    })
    assert resp.status_code == 403


def test_registration_default_is_closed():
    """Production default: the workspace does not stay open to new sign-ups."""
    import os
    from app.config.settings import AuthConfig

    prior = os.environ.pop("AUTH_REGISTRATION_OPEN", None)
    try:
        assert AuthConfig().registration_open is False
    finally:
        if prior is not None:
            os.environ["AUTH_REGISTRATION_OPEN"] = prior


# --------------------------------------------------------- #7 admin write scope
def test_admin_may_read_but_not_write_another_users_resource():
    from app.security.ownership import owns

    admin = {"id": "usr_admin", "role": "admin"}
    owner = {"id": "usr_owner", "role": "attorney"}

    assert owns("usr_owner", admin) is True            # read across users: allowed
    assert owns("usr_owner", admin, write=True) is False  # mutate another's vault: never
    assert owns("usr_owner", owner, write=True) is True   # the owner may write
    assert owns("usr_other", owner) is False


# ------------------------------------------------------------- #11 health leak
def test_health_does_not_disclose_the_model_inventory():
    body = client.get("/health").json()
    assert "installed_models" not in body["ollama"], "model inventory exposed pre-auth"
    assert "installed_model_count" in body["ollama"]


# ---------------------------------------------------------------- #12 cors
def test_wildcard_origin_is_never_combined_with_credentials():
    from starlette.middleware.cors import CORSMiddleware

    cors = next((m for m in app.user_middleware if m.cls is CORSMiddleware), None)
    assert cors is not None
    opts = cors.kwargs
    if "*" in opts.get("allow_origins", []):
        assert opts.get("allow_credentials") is False
