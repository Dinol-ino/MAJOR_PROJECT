import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.models import User
from app.db.engine import get_sync_session

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        yield client

@pytest.fixture
def db_session():
    with get_sync_session() as session:
        yield session

def test_register_success(client, db_session):
    uid = uuid.uuid4().hex[:8]
    resp = client.post("/auth/register", json={
        "username": f"user_{uid}",
        "email": f"test_{uid}@example.com",
        "password": "securepass",
        "full_name": "Test User",
        "role": "attorney"
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert "token" in data
    assert data["user"]["username"] == f"user_{uid}"

def test_register_duplicate(client, db_session):
    uid = uuid.uuid4().hex[:8]
    # First registration
    client.post("/auth/register", json={
        "username": f"dup_{uid}",
        "email": f"dup_{uid}@example.com",
        "password": "pass1234-long",
        "full_name": "Dup",
        "role": "attorney"
    })
    # Second registration with same username
    resp = client.post("/auth/register", json={
        "username": f"dup_{uid}",
        "email": f"dup2_{uid}@example.com",
        "password": "anotherpass",
        "full_name": "Dup2",
        "role": "attorney"
    })
    assert resp.status_code == 409
    assert "already exists" in resp.text

def test_login_success(client):
    uid = uuid.uuid4().hex[:8]
    # Register a user first
    client.post("/auth/register", json={
        "username": f"login_{uid}",
        "email": f"login_{uid}@example.com",
        "password": "mypass-2026",
        "full_name": "Login User",
        "role": "attorney"
    })
    resp = client.post("/auth/login", json={
        "username": f"login_{uid}",
        "password": "mypass-2026"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["username"] == f"login_{uid}"

def test_login_failure(client):
    resp = client.post("/auth/login", json={
        "username": f"nonexistent_{uuid.uuid4().hex[:8]}",
        "password": "wrong"
    })
    assert resp.status_code == 401
    assert "Invalid" in resp.text

def test_lockout_after_max_attempts(client):
    uid = uuid.uuid4().hex[:8]
    # Attempt 5 failed logins
    for _ in range(5):
        client.post("/auth/login", json={
            "username": f"lock_{uid}",
            "password": "wrongpass"
        })
    # Sixth attempt should be locked
    resp = client.post("/auth/login", json={
        "username": f"lock_{uid}",
        "password": "wrongpass"
    })
    assert resp.status_code == 429
    assert "Try again" in resp.text

def test_auth_disabled_in_test_env(monkeypatch, client):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_anything")
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "legal_practitioner"

def test_protected_route_without_token(monkeypatch, client):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    resp = client.get("/vaults")
    assert resp.status_code == 401

def test_invalid_token(client):
    uid = uuid.uuid4().hex[:8]
    # Register a user first
    client.post("/auth/register", json={
        "username": f"tok_{uid}",
        "email": f"tok_{uid}@example.com",
        "password": "pass1234-long",
        "full_name": "Token Test",
        "role": "attorney"
    })
    # Get token
    login_resp = client.post("/auth/login", json={
        "username": f"tok_{uid}",
        "password": "pass1234-long"
    })
    token = login_resp.json()["token"]
    # Use invalid token
    resp = client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401

# --- Fail-closed session model (root cause of "Authentication required" in a token-less UI) ---

def test_no_tokenless_first_run_identity(monkeypatch, client):
    """Without a token, protected routes are 401 even if the DB is empty or unreachable."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert client.get("/auth/me").status_code == 401
    assert client.get("/conversations").status_code == 401


def test_auth_status_is_public_and_minimal(monkeypatch, client):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    resp = client.get("/auth/status")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"accounts_exist", "registration_open", "password_min_length"}


def test_register_cannot_self_assign_admin(client):
    from tests.auth_helpers import register_user
    uid = uuid.uuid4().hex[:8]
    resp = client.post("/auth/register", json={
        "username": f"esc_{uid}", "email": f"esc_{uid}@example.com",
        "password": "Str0ngPass!word", "role": "admin",
    })
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] != "admin"


def test_short_password_rejected(client):
    uid = uuid.uuid4().hex[:8]
    resp = client.post("/auth/register", json={
        "username": f"short_{uid}", "email": f"short_{uid}@example.com", "password": "abc",
    })
    assert resp.status_code == 400


def test_logout_revokes_token(monkeypatch, client):
    from tests.auth_helpers import register_user
    _, headers = register_user(client, "logout")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_query_token_only_accepted_on_stream_paths(monkeypatch, client):
    from tests.auth_helpers import register_user
    _, headers = register_user(client, "qtok")
    token = headers["Authorization"].split(" ", 1)[1]
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert client.get(f"/auth/me?token={token}").status_code == 401
    assert client.get(f"/conversations?token={token}").status_code == 401


def test_forged_token_rejected(monkeypatch, client):
    import jwt as pyjwt
    import time as _t
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    forged = pyjwt.encode({"sub": "default_user", "iat": int(_t.time()), "exp": int(_t.time()) + 60}, "guessed-secret", algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
