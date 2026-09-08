import os
import io
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.memory.durable_memory import DurableMemoryManager
from app.db.engine import get_sync_session
from app.db.models import ProjectVault, Conversation, Message, DocumentMemory

client = TestClient(app)
durable_memory = DurableMemoryManager()


def test_write_through_memory_rehydration():
    """
    Module 2 Task 2.2 / Acceptance Criteria:
    Database is the system of record for conversations and messages.
    Messages are written through on every turn and survive cache evictions.
    """
    session_id = f"test_conv_{uuid.uuid4().hex[:8]}"
    
    # 1. Send user message via /chat endpoint
    resp = client.post("/chat", json={
        "message": "What is the limitation period for breach of contract under Indian law?",
        "session_id": session_id,
        "shield_on": True,
        "reasoning_effort": "off"
    })
    assert resp.status_code == 200
    
    # 2. Directly verify database rows (bypassing any in-memory/Redis layer)
    with get_sync_session() as session:
        conv = session.query(Conversation).filter_by(conversation_id=session_id).first()
        assert conv is not None
        assert len(conv.messages) >= 2  # user message + assistant message
        roles = [m.role for m in conv.messages]
        assert "user" in roles
        assert "assistant" in roles

    # 3. Verify rehydration via GET /chat/sessions/{id}/messages
    hist_resp = client.get(f"/chat/sessions/{session_id}/messages")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert len(hist_data["messages"]) >= 2
    assert hist_data["session_id"] == session_id


def test_user_isolation_no_cross_leakage():
    """
    Module 2 Task 2.1.2 / Acceptance Criteria:
    ProjectVault and Conversation entities are strictly scoped to server-side user_id.
    User A cannot see User B's vaults or conversations.
    """
    user_a = f"attorney_a_{uuid.uuid4().hex[:6]}"
    user_b = f"attorney_b_{uuid.uuid4().hex[:6]}"

    # Create vault for User A
    v_a = client.post("/vaults", json={
        "vault_name": "Matter Alpha (Confidential)",
        "user_id": user_a,
        "description": "User A private case"
    }).json()
    vault_a_id = v_a["id"]

    # Create vault for User B
    v_b = client.post("/vaults", json={
        "vault_name": "Matter Beta (Confidential)",
        "user_id": user_b,
        "description": "User B private case"
    }).json()
    vault_b_id = v_b["id"]

    # List vaults for User A
    resp_a = client.get(f"/vaults?user_id={user_a}").json()
    vault_ids_a = [v["id"] for v in resp_a["vaults"]]
    assert vault_a_id in vault_ids_a
    assert vault_b_id not in vault_ids_a

    # List vaults for User B
    resp_b = client.get(f"/vaults?user_id={user_b}").json()
    vault_ids_b = [v["id"] for v in resp_b["vaults"]]
    assert vault_b_id in vault_ids_b
    assert vault_a_id not in vault_ids_b


def test_vault_file_cap_enforced():
    """
    Module 2 Task 2.3.2 / Acceptance Criteria:
    Per-vault file limit (RetrievalConfig.vault_max_files) is strictly enforced.
    Uploading beyond the quota returns HTTP 400 with a clear error message.
    """
    v_res = client.post("/vaults", json={"vault_name": "Cap Test Vault"}).json()
    vault_id = v_res["id"]

    # Simulate existing documents up to the configured limit
    max_files = settings.retrieval.vault_max_files
    with get_sync_session() as session:
        for i in range(max_files):
            doc = DocumentMemory(
                doc_id=f"doc_cap_{vault_id[:6]}_{i}",
                session_id=vault_id,
                project_vault_id=vault_id,
                filename=f"contract_{i}.pdf",
                file_hash=f"hash_{vault_id}_{i}",
                file_size_bytes=1024,
                ingest_status="ready"
            )
            session.add(doc)

    # Attempting to upload another file must fail with HTTP 400
    dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy legal document content")
    upload_resp = client.post(
        f"/vaults/{vault_id}/documents",
        files={"file": ("overflow_document.pdf", dummy_pdf, "application/pdf")}
    )
    assert upload_resp.status_code == 400
    assert "Vault file quota reached" in upload_resp.json()["detail"]


def test_vault_soft_delete_and_grace_retention():
    """
    Module 2 Task 2.3.1 / Acceptance Criteria:
    Vault deletion marks deleted_at timestamp (soft delete) for compliance retention.
    Soft-deleted vaults are omitted from standard active listings.
    """
    v_res = client.post("/vaults", json={"vault_name": "Compliance Matter To Delete"}).json()
    vault_id = v_res["id"]

    # Soft delete vault
    del_resp = client.delete(f"/vaults/{vault_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["soft_deleted"] is True

    # Confirm it does not appear in active listings
    list_resp = client.get("/vaults").json()
    active_ids = [v["id"] for v in list_resp["vaults"]]
    assert vault_id not in active_ids

    # Confirm record still exists in DB with deleted_at timestamp
    with get_sync_session() as session:
        vault_db = session.query(ProjectVault).filter_by(id=vault_id).first()
        assert vault_db is not None
        assert vault_db.deleted_at is not None


def test_conversation_rename_and_pagination():
    """
    Module 2 Task 2.2.2 & 2.2.3 / Acceptance Criteria:
    Conversations support server-side pagination and inline renaming via PATCH /conversations/{id}.
    """
    v_res = client.post("/vaults", json={"vault_name": "Pagination Vault"}).json()
    vault_id = v_res["id"]

    # Create 3 conversations in this vault
    c1 = client.post("/conversations", json={"project_vault_id": vault_id, "title": "Chat 1"}).json()
    c2 = client.post("/conversations", json={"project_vault_id": vault_id, "title": "Chat 2"}).json()
    c3 = client.post("/conversations", json={"project_vault_id": vault_id, "title": "Chat 3"}).json()

    # Test paginated vault conversations (limit=2, page=1)
    page1 = client.get(f"/vaults/{vault_id}/conversations?page=1&limit=2").json()
    assert page1["total_count"] >= 3
    assert len(page1["conversations"]) == 2

    # Test rename endpoint
    rename_resp = client.patch(f"/conversations/{c1['conversation_id']}", json={
        "title": "Corporate Due Diligence Review 2026"
    })
    assert rename_resp.status_code == 200
    assert rename_resp.json()["title"] == "Corporate Due Diligence Review 2026"


def test_deep_thinking_fsm_reasoning_trace():
    """
    Module 2 Task 2.4 / Acceptance Criteria:
    Deep Thinking mode routes through full FSM orchestrator and populates reasoning_trace.
    """
    session_id = f"test_dt_{uuid.uuid4().hex[:8]}"
    resp = client.post("/chat", json={
        "message": "Analyze director duties under Section 166 of the Companies Act 2013.",
        "session_id": session_id,
        "shield_on": True,
        "reasoning_effort": "high"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked_by"] is None
    # Reasoning trace must be populated for high reasoning effort
    assert data["reasoning_trace"] is not None
    assert len(data["reasoning_trace"]) > 20
