"""
/chat/stream must enforce the same tenant isolation as /chat, and private material must
never be sent to a cloud provider whatever the fallback settings say.
"""
import io

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.ingest import ingest_service
from tests.auth_helpers import register_user
from tests.test_vault_permanence import PAGES_A, _make_vault, _pdf, _upload

client = TestClient(app)


def _vault_with_doc(prefix):
    _, h = register_user(client, prefix)
    vault_id = _make_vault(h)
    doc_id = _upload(vault_id, h, _pdf(PAGES_A))["document_id"]
    ingest_service.ingest_document(doc_id=doc_id, vault_id=vault_id, filename="case.pdf")
    return h, vault_id


def _stream(headers, body):
    with client.stream("POST", "/chat/stream", headers=headers, json=body) as r:
        text = "".join(r.iter_text())
        return r.status_code, text


def test_stream_rejects_another_users_vault():
    _, victim_vault = _vault_with_doc("victim")
    _, attacker = register_user(client, "attacker")
    status, body = _stream(attacker, {"message": "Where is the arbitrator seated under the arbitration clause?",
                                       "session_id": "s_att_1", "vault_id": victim_vault, "shield_on": True})
    assert status == 404, body
    assert "Mangaluru" not in body


def test_stream_rejects_another_users_conversation_and_its_bound_vault():
    victim_h, victim_vault = _vault_with_doc("victim2")
    # The victim's conversation is bound to their vault.
    r = client.post("/chat", headers=victim_h, json={"message": "Where is the arbitrator seated under the arbitration clause?",
                                                      "session_id": "s_victim_conv", "vault_id": victim_vault,
                                                      "shield_on": True, "reasoning_effort": "off"})
    assert r.status_code == 200
    _, attacker = register_user(client, "attacker2")
    status, body = _stream(attacker, {"message": "arbitration seat", "session_id": "s_victim_conv", "shield_on": True})
    assert status == 404, body
    assert "Mangaluru" not in body


def test_stream_still_works_for_the_owner():
    h, vault_id = _vault_with_doc("owner_stream")
    status, body = _stream(h, {"message": "Where is the arbitrator seated under the arbitration clause?",
                                "session_id": "s_owner_1", "vault_id": vault_id, "shield_on": True})
    assert status == 200


# ------------------------------------------------------------------ cloud egress
def test_cloud_runtime_refuses_when_private_context_is_marked(monkeypatch):
    import asyncio
    from app.runtime import egress_guard
    from app.runtime.cloud_runtime import CloudRuntime, CloudEgressBlocked

    monkeypatch.setattr(settings.cloud_fallback, "enabled", True)
    token = egress_guard.mark_private_context("vault evidence in prompt")
    try:
        with pytest.raises(CloudEgressBlocked):
            asyncio.run(CloudRuntime(provider="grok").generate("privileged client text"))

        async def drain():
            async for _ in CloudRuntime(provider="grok").generate_stream("privileged client text"):
                pass
        with pytest.raises(CloudEgressBlocked):
            asyncio.run(drain())
    finally:
        egress_guard.reset_private_context(token)


def test_cloud_runtime_refuses_when_cloud_fallback_is_not_enabled(monkeypatch):
    import asyncio
    from app.runtime.cloud_runtime import CloudRuntime, CloudEgressBlocked
    monkeypatch.setattr(settings.cloud_fallback, "enabled", False)
    with pytest.raises(CloudEgressBlocked):
        asyncio.run(CloudRuntime(provider="grok").generate("statute question"))


def test_private_chunks_mark_the_context_and_public_ones_do_not():
    from app.runtime import egress_guard
    tok = egress_guard.mark_private_from_chunks([{"doc_type": "statutory_law"}])
    assert tok is None and not egress_guard.is_private_context()
    tok = egress_guard.mark_private_from_chunks([{"doc_type": "statutory_law"}, {"doc_type": "vault_document"}])
    try:
        assert egress_guard.is_private_context()
    finally:
        egress_guard.reset_private_context(tok)
    assert not egress_guard.is_private_context()
