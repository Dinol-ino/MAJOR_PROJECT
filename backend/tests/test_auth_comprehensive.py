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
        "password": "pass1234",
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
        "password": "mypass",
        "full_name": "Login User",
        "role": "attorney"
    })
    resp = client.post("/auth/login", json={
        "username": f"login_{uid}",
        "password": "mypass"
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
        "password": "pass1234",
        "full_name": "Token Test",
        "role": "attorney"
    })
    # Get token
    login_resp = client.post("/auth/login", json={
        "username": f"tok_{uid}",
        "password": "pass1234"
    })
    token = login_resp.json()["token"]
    # Use invalid token
    resp = client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401