import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.system.hardware_detector import HardwareDetector, HardwareProfile
from app.system.model_registry import ModelRegistry
from app.routes.recommend import _manual_overrides


@pytest.fixture
def client():
    return TestClient(app)


def test_atomic_system_hardware_endpoint(client):
    """
    Task 6.1.1: Verify GET /system/hardware returns atomic snapshot with
    probed_at timestamp, CPU, RAM, and independent GPU fallback state.
    """
    resp = client.get("/system/hardware")
    assert resp.status_code == 200
    data = resp.json()

    assert "probed_at" in data
    assert "cpu_cores" in data
    assert "ram_total_gb" in data
    assert "hardware_tier" in data
    assert "cpu" in data
    assert "ram" in data
    assert "gpu_available" in data

    # Verify independent probe format
    if not data["gpu_available"]:
        assert data["gpu"] is None
        assert data["gpu_reason"] is not None


def test_recommend_endpoint_and_deterministic_tie_break(client):
    """
    Task 6.2.1: Verify GET /recommend and POST /recommend adhere to deterministic tie-break rules.
    """
    # Clean up overrides before test
    _manual_overrides.clear()

    resp = client.get("/recommend")
    assert resp.status_code == 200
    data = resp.json()

    assert "recommended" in data
    assert len(data["recommended"]) > 0
    assert data["selection_source"] == "recommended"
    assert "VRAM governs over RAM" in data["tie_break_rule"]
    assert data["override_applied"] is False


def test_recommend_manual_override_lifecycle(client):
    """
    Task 6.2.1: Verify POST /recommend/override sets persistent manual override,
    and POST /recommend/reset cleanly restores hardware recommendation.
    """
    _manual_overrides.clear()

    # 1. Apply manual override for Qwen 2.5 14B
    override_payload = {
        "model_id": "qwen2.5:14b",
        "session_id": "test_sess_100",
        "reason": "User accepts slower CPU offload for higher legal reasoning accuracy"
    }
    resp = client.post("/recommend/override", json=override_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["active_model_id"] == "qwen2.5:14b"
    assert data["selection_source"] == "manually_selected"
    assert data["override_applied"] is True

    # 2. Subsequent GET /recommend with session_id returns the override
    resp2 = client.get("/recommend?session_id=test_sess_100")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["active_model_id"] == "qwen2.5:14b"
    assert data2["selection_source"] == "manually_selected"

    # 3. Reset override
    resp3 = client.post("/recommend/reset?session_id=test_sess_100")
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["selection_source"] == "recommended"
    assert data3["override_applied"] is False


def test_model_catalog_states_and_specialization(client):
    """
    Task 6.3.1 & 6.3.2: Verify model recommendation catalog exposes
    status states (NOT_PULLED/ACTIVE/PULLED_INACTIVE) and fine-tuning metadata.
    """
    resp = client.get("/models/recommended")
    assert resp.status_code == 200
    data = resp.json()

    assert "recommended" in data
    models = data["recommended"]
    assert len(models) > 0

    # Verify specialization metadata on dfrag-legal:7b
    dfrag_model = next((m for m in models if "dfrag" in m["model_id"].lower()), None)
    if dfrag_model:
        assert dfrag_model["specialization"] == "Fine-tuned for Indian Law"
        assert dfrag_model["is_fine_tuned"] is True

    # Check status_state presence
    for m in models:
        assert "status_state" in m
        assert m["status_state"] in ["NOT_PULLED", "PULLED_INACTIVE", "ACTIVE"]


def test_mock_runtime_hard_safety_check(client):
    """
    Section 6.5: Verify MockRuntime cannot be switched to outside test/CI environments.
    """
    env_copy = os.environ.copy()
    env_copy.pop("PYTEST_CURRENT_TEST", None)
    env_copy["TESTING"] = "0"
    with patch.dict(os.environ, env_copy, clear=True):
        resp = client.post("/runtime/switch", json={"runtime_name": "mock"})
        assert resp.status_code == 403
        assert "MockRuntime is restricted" in resp.json()["detail"]


def test_mcp_named_tools_execution_and_audit(client):
    """
    Task 6.4.1 & 6.4.4: Verify MCP tool execution for legal tools and history audit recording.
    """
    # 1. Test local_statute_search
    req1 = {
        "tool_name": "local_statute_search",
        "arguments": {"query": "cheating fraud", "top_k": 2},
        "session_id": "test_mcp_session"
    }
    resp1 = client.post("/mcp/tool-call", json=req1)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["success"] is True
    assert data1["category"] == "LOCAL_RETRIEVAL"

    # 2. Test local_provision_lookup
    req2 = {
        "tool_name": "local_provision_lookup",
        "arguments": {"act": "Indian Penal Code", "section": "Section 420"},
        "session_id": "test_mcp_session"
    }
    resp2 = client.post("/mcp/tool-call", json=req2)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["success"] is True

    # 3. Test indiacode_fetcher in ONLINE mode
    req3 = {
        "tool_name": "indiacode_fetcher",
        "arguments": {"act_id": "act_1860_45"},
        "session_id": "test_mcp_session",
        "network_mode": "ONLINE"
    }
    resp3 = client.post("/mcp/tool-call", json=req3)
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["success"] is True

    # 4. Verify history endpoint returns recorded tool calls
    hist_resp = client.get("/mcp/history?limit=10")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["total"] >= 1
    assert any(c["tool_name"] == "local_statute_search" for c in hist_data["history"])
