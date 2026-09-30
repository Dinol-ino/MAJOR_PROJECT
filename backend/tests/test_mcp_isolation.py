"""Session-scoped user documents must not be reachable by another user via MCP, memory, or history."""
import io
import fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import register_user

client = TestClient(app)
SECRET = "Zanzibar indemnity clause 77"


def _pdf(text):
    d = fitz.open(); p = d.new_page(); p.insert_text((72, 100), text); b = d.tobytes(); d.close(); return b


def _victim_session(sid):
    _, h = register_user(client, "mcpvictim")
    r = client.post("/upload", headers=h, data={"session_id": sid},
                    files={"file": ("secret.pdf", io.BytesIO(_pdf(SECRET)), "application/pdf")})
    assert r.status_code == 200, r.text
    return h


def test_mcp_tool_call_rejects_foreign_session():
    _victim_session("sess_mcp_v1")
    _, atk = register_user(client, "mcpatk")
    r = client.post("/mcp/tool-call", headers=atk, json={
        "tool_name": "user_document_search", "arguments": {"query": "Zanzibar indemnity"},
        "session_id": "sess_mcp_v1"})
    assert r.status_code == 404, r.text
    assert "Zanzibar" not in r.text


def test_memory_documents_rejects_foreign_session():
    _victim_session("sess_mcp_v2")
    _, atk = register_user(client, "memhatk")
    r = client.get("/memory/documents/sess_mcp_v2", headers=atk)
    assert r.status_code == 404
    assert "secret.pdf" not in r.text


def test_upload_cannot_bind_to_foreign_session():
    _victim_session("sess_mcp_v3")
    _, atk = register_user(client, "bindatk")
    r = client.post("/upload", headers=atk, data={"session_id": "sess_mcp_v3"},
                    files={"file": ("x.pdf", io.BytesIO(_pdf("hello")), "application/pdf")})
    assert r.status_code == 404


def test_mcp_history_is_scoped_to_caller():
    vh = _victim_session("sess_mcp_v4")
    client.post("/mcp/tool-call", headers=vh, json={
        "tool_name": "user_document_search", "arguments": {"query": "Zanzibar"}, "session_id": "sess_mcp_v4"})
    _, atk = register_user(client, "histatk")
    r = client.get("/mcp/history", headers=atk)
    assert r.status_code == 200
    assert "Zanzibar" not in r.text and "sess_mcp_v4" not in r.text


def test_owner_still_works():
    vh = _victim_session("sess_mcp_v5")
    r = client.post("/mcp/tool-call", headers=vh, json={
        "tool_name": "user_document_search", "arguments": {"query": "Zanzibar indemnity"}, "session_id": "sess_mcp_v5"})
    assert r.status_code == 200
    assert client.get("/memory/documents/sess_mcp_v5", headers=vh).status_code == 200


def test_uncited_act_with_no_evidence_fails_validation():
    from app.security.output_validator import output_validator
    ok, reason = output_validator.verify_citations_exist("Under the Companies Act the director is liable.", [])
    assert ok is False and "unverified" in reason
    assert output_validator.verify_citations_exist("I do not have enough information.", [])[0] is True
