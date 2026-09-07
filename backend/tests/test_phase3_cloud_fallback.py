import pytest
import os
import time
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.config.api_vault import api_vault, APIKeyVault
from app.runtime.circuit_breaker import CircuitBreaker, CircuitBreakerState, FailureKind
from app.runtime.cloud_runtime import CloudRuntime, CloudRuntimeError
from app.runtime.router import FallbackRouter


client = TestClient(app)


def test_api_vault_masking_and_resolution(monkeypatch):
    vault = APIKeyVault()

    # 1. Masking verification
    assert vault.mask("xai-1234567890abcdef") == "xai-...cdef"
    assert vault.mask("zai-9876543210fedcba") == "zai-...dcba"
    assert vault.mask("generic_key_here") == "gen...here"
    assert vault.mask("") is None
    assert vault.mask(None) is None

    # 2. Database resolution
    vault.set_from_ui("grok", "xai-test-key-db-12345")
    assert vault.is_configured("grok") is True
    assert vault.get("grok") == "xai-test-key-db-12345"
    assert vault.mask(vault.get("grok")) == "xai-...2345"

    vault.set_from_ui("zai", "zai-test-key-db-67890")
    assert vault.is_configured("zai") is True
    assert vault.get("zai") == "zai-test-key-db-67890"

    # 3. Environment variable precedence
    monkeypatch.setenv("GROK_API_KEY", "xai-env-priority-99999")
    assert vault.get("grok") == "xai-env-priority-99999"

    monkeypatch.delenv("GROK_API_KEY", raising=False)
    assert vault.get("grok") == "xai-test-key-db-12345"

    # 4. Status dictionary masks all keys
    status = vault.get_status()
    assert status["grok_configured"] is True
    assert status["zai_configured"] is True
    assert "xai-test-key-db-12345" not in str(status)
    assert status["grok_masked"] == "xai-...2345"

    # 5. Clean up
    vault.delete("grok")
    vault.delete("zai")
    assert vault.get("grok") is None
    assert vault.get("zai") is None


def test_circuit_breaker_lifecycle():
    breaker = CircuitBreaker(failure_threshold=3, window_seconds=10.0, cooldown_seconds=2.0)
    model = "test_legal_model:latest"

    # Initial state: CLOSED
    assert breaker.get_state(model) == CircuitBreakerState.CLOSED
    assert breaker.can_execute(model) is True

    # 1st failure (non-severe empty generation does not trip)
    breaker.record_failure(model, kind=FailureKind.EMPTY_GENERATION)
    assert breaker.get_state(model) == CircuitBreakerState.CLOSED

    # 2 severe failures
    breaker.record_failure(model, kind=FailureKind.CONNECT_ERROR)
    breaker.record_failure(model, kind=FailureKind.OOM_TIMEOUT)
    assert breaker.get_state(model) == CircuitBreakerState.CLOSED

    # 3rd severe failure trips breaker to OPEN
    state = breaker.record_failure(model, kind=FailureKind.CONNECT_ERROR)
    assert state == CircuitBreakerState.OPEN
    assert breaker.get_state(model) == CircuitBreakerState.OPEN
    assert breaker.can_execute(model) is False

    # Simulate cooldown elapse
    breaker._models[model]["opened_at"] = time.time() - 3.0  # past 2.0s cooldown
    assert breaker.get_state(model) == CircuitBreakerState.HALF_OPEN
    assert breaker.can_execute(model) is True

    # If probe fails in HALF_OPEN, immediately return to OPEN
    breaker.record_failure(model, kind=FailureKind.CONNECT_ERROR)
    assert breaker.get_state(model) == CircuitBreakerState.OPEN
    assert breaker.can_execute(model) is False

    # Simulate cooldown elapse again and probe succeeds
    breaker._models[model]["opened_at"] = time.time() - 3.0
    assert breaker.get_state(model) == CircuitBreakerState.HALF_OPEN
    breaker.record_success(model)
    assert breaker.get_state(model) == CircuitBreakerState.CLOSED
    assert breaker.can_execute(model) is True


@pytest.mark.anyio
async def test_cloud_runtime_generate():
    api_vault.set_from_ui("grok", "xai-test-key-mock")

    runtime = CloudRuntime(provider="grok")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Section 420 of Indian Penal Code deals with cheating and dishonestly inducing delivery of property."
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        ans = await runtime.generate("Explain IPC 420")
        assert "Section 420" in ans

    api_vault.delete("grok")


@pytest.mark.anyio
async def test_cloud_runtime_streaming():
    api_vault.set_from_ui("zai", "zai-test-key-mock")

    runtime = CloudRuntime(provider="zai")

    async def mock_aiter_lines():
        lines = [
            'data: {"choices": [{"delta": {"content": "Supreme "}}]}',
            'data: {"choices": [{"delta": {"content": "Court "}}]}',
            'data: {"choices": [{"delta": {"content": "of India."}}]}',
            'data: [DONE]'
        ]
        for l in lines:
            yield l

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines = mock_aiter_lines
    mock_stream_ctx.__aenter__.return_value = mock_response
    mock_stream_ctx.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        tokens = []
        async for token in runtime.generate_stream("What is the apex court?"):
            tokens.append(token)
        assert "".join(tokens) == "Supreme Court of India."

    api_vault.delete("zai")


def test_settings_api_lifecycle():
    # 1. GET /settings/fallback
    res = client.get("/settings/fallback")
    assert res.status_code == 200
    data = res.json()
    assert "enabled" in data
    assert "auto_fallback" in data
    assert "grok_configured" in data
    assert "zai_configured" in data

    # 2. POST /settings/fallback
    update_res = client.post("/settings/fallback", json={
        "enabled": True,
        "auto_fallback": True,
        "active_provider": "grok",
        "grok_key": "xai-unit-test-key-abcd1234"
    })
    assert update_res.status_code == 200
    up_data = update_res.json()
    assert up_data["status"] == "success"
    assert up_data["settings"]["grok_configured"] is True
    assert up_data["settings"]["grok_masked"] == "xai-...1234"

    # 3. GET /runtime/status includes circuit_breakers & cloud_fallback
    status_res = client.get("/runtime/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "circuit_breakers" in status_data
    assert "cloud_fallback" in status_data
    assert status_data["cloud_fallback"]["grok_configured"] is True

    # 4. Clean up key
    client.post("/settings/fallback", json={"grok_key": ""})
