"""
The citation graph must be data-driven and scoped:
  * vault scope without a vault is an empty state, not "everything";
  * conversation-derived edges are visible only to the conversation's owner;
  * unknown scopes never fall through to an unfiltered query.
"""
import uuid

from fastapi.testclient import TestClient

from app.db.engine import get_sync_session
from app.db.models import CitationEdge
from app.main import app
from tests.auth_helpers import register_user

client = TestClient(app)
MARKER = "section:private_marker_zz:1"


def _seed_private_edge(headers, vault_id=None):
    """Owner creates a conversation (optionally in a vault) and one citation edge derived from it."""
    session_id = f"s_graph_{uuid.uuid4().hex[:8]}"
    body = {"message": "What does the Indian Contract Act say about damages for breach?",
            "session_id": session_id, "shield_on": True, "reasoning_effort": "off"}
    if vault_id:
        body["vault_id"] = vault_id
    assert client.post("/chat", headers=headers, json=body).status_code == 200
    with get_sync_session() as s:
        s.add(CitationEdge(src_type="section", src_key="section:contract_act_1872:73", dst_type="section",
                           dst_key=MARKER, relation="cites", origin="llm_citation", conversation_id=session_id))
    return session_id


def test_vault_scope_without_a_vault_is_an_empty_state():
    _, h = register_user(client, "gv1")
    body = client.get("/statutes/graph?scope=vault", headers=h).json()
    assert body["nodes"] == [] and body["links"] == [] and body["empty_state"] is True


def test_unknown_scope_is_an_empty_state():
    _, h = register_user(client, "gv2")
    body = client.get("/statutes/graph?scope=everything", headers=h).json()
    assert body["nodes"] == [] and body["empty_state"] is True


def test_other_users_conversation_edges_are_never_visible():
    _, owner = register_user(client, "gv_owner")
    _seed_private_edge(owner)
    _, other = register_user(client, "gv_other")
    for scope in ("vault", "global", "conversation"):
        r = client.get(f"/statutes/graph?scope={scope}", headers=other)
        assert MARKER not in r.text, scope


def test_owner_sees_their_own_edges_in_vault_scope_only_for_that_vault():
    _, h = register_user(client, "gv_vault")
    v1 = client.post("/vaults", json={"vault_name": "one"}, headers=h).json()["id"]
    v2 = client.post("/vaults", json={"vault_name": "two"}, headers=h).json()["id"]
    _seed_private_edge(h, vault_id=v1)
    assert MARKER in client.get(f"/statutes/graph?scope=vault&vault_id={v1}", headers=h).text
    other_vault = client.get(f"/statutes/graph?scope=vault&vault_id={v2}", headers=h).json()
    assert MARKER not in str(other_vault) and other_vault["empty_state"] is True


def test_vault_graph_never_contains_corpus_wide_cross_references():
    _, h = register_user(client, "gv_corpus")
    v = client.post("/vaults", json={"vault_name": "clean"}, headers=h).json()["id"]
    body = client.get(f"/statutes/graph?scope=vault&vault_id={v}", headers=h).json()
    assert body["nodes"] == [] and body["empty_state"] is True
