"""Helpers for tests that need real, distinct authenticated users."""
import uuid


def register_user(client, prefix: str = "user", password: str = "Str0ngPass!word"):
    """Registers a fresh user and returns (user_dict, auth_headers)."""
    uid = uuid.uuid4().hex[:8]
    resp = client.post("/auth/register", json={
        "username": f"{prefix}_{uid}",
        "email": f"{prefix}_{uid}@example.com",
        "password": password,
        "full_name": f"{prefix} {uid}",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["user"], {"Authorization": f"Bearer {data['token']}"}
