import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.defense.audit_log import AuditLogger
from app.observability.metrics import metrics_collector


@pytest.fixture
def client():
    return TestClient(app)


def test_audit_ledger_verification_and_export(client):
    """
    Task 8.1.1, 8.1.2 & 8.1.3: Verify cryptographic audit ledger verification,
    category breakdowns, and JSON export endpoint.
    """
    audit_logger = AuditLogger()
    # Log simulated events across multiple categories
    audit_logger.log(action="chat_completed:Section 420 IPC", layer="orchestrator")
    audit_logger.log(action="upload_pdf:fir_matter_brief.pdf", layer="persistence")
    audit_logger.log(action="blocked_security:prompt_injection", layer="input_guard", validation_pass_fail="fail")
    audit_logger.log(action="mcp_tool_call:local_statute_search", layer="mcp_gateway")

    # 1. Test verification endpoint
    v_resp = client.get("/audit/verify")
    assert v_resp.status_code == 200
    v_data = v_resp.json()
    assert v_data["valid"] is True
    assert "verified_at" in v_data
    assert v_data["total_events"] >= 4

    # 2. Test audit list with category breakdowns
    list_resp = client.get("/audit/all")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert "rows" in list_data
    assert list_data["total_count"] >= 4
    assert list_data["chat_count"] >= 1
    assert list_data["upload_count"] >= 1
    assert list_data["blocked_count"] >= 1
    assert list_data["mcp_count"] >= 1

    # 3. Test export endpoint
    exp_resp = client.get("/audit/export/json")
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()
    assert "export_metadata" in exp_data
    assert exp_data["export_metadata"]["integrity_verification"]["valid"] is True
    assert len(exp_data["records"]) >= 4


def test_diagnostics_trace_and_live_summary(client):
    """
    Task 8.2.1 & 8.2.2: Verify live metrics summary and correlated request trace lookup.
    """
    from app.observability.metrics import RequestMetric, StageMetric
    test_req_id = f"req_{uuid.uuid4().hex[:10]}"

    # Record metric with stages in collector
    req_metric = RequestMetric(
        request_id=test_req_id,
        session_id="test_diag_session",
        endpoint="/chat",
        total_duration_ms=120.5,
        model_name="gemma2:2b",
        output_tokens=180,
        stages=[
            StageMetric(stage_name="classify", duration_ms=12.0),
            StageMetric(stage_name="retrieve", duration_ms=35.0),
            StageMetric(stage_name="generate", duration_ms=73.5)
        ]
    )
    metrics_collector.record_request_metric(req_metric)

    # 1. Query metrics summary
    sum_resp = client.get("/diagnostics/metrics/summary")
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert "p50_latency_ms" in sum_data
    assert "p95_latency_ms" in sum_data
    assert sum_data["total_requests"] >= 1

    # 2. Query correlated trace
    trace_resp = client.get(f"/diagnostics/trace/{test_req_id}")
    assert trace_resp.status_code == 200
    trace_data = trace_resp.json()
    assert trace_data["request_id"] == test_req_id
    assert trace_data["total_duration_ms"] == 120.5
    assert len(trace_data["stages"]) == 3

    # 3. Non-existent trace returns 404
    missing_resp = client.get("/diagnostics/trace/non_existent_id_999")
    assert missing_resp.status_code == 404


def test_auth_registration_login_and_bearer_token(client):
    """
    Task 8.3.1 & 8.3.2: Verify PBKDF2 authentication, token issuance, and /auth/me profile.
    """
    test_uid = uuid.uuid4().hex[:8]
    reg_payload = {
        "username": f"advocate_{test_uid}",
        "email": f"advocate_{test_uid}@legalbar.in",
        "password": "SecurePassword#2026",
        "full_name": "Advocate Ramesh Sharma",
        "role": "senior_counsel"
    }

    # 1. Register
    reg_resp = client.post("/auth/register", json=reg_payload)
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert "token" in reg_data
    assert reg_data["user"]["username"] == f"advocate_{test_uid}"

    # 2. Login with issued credentials
    login_payload = {
        "username": f"advocate_{test_uid}",
        "password": "SecurePassword#2026"
    }
    login_resp = client.post("/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["token"]
    assert token is not None

    # 3. Authenticated /auth/me request
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["username"] == f"advocate_{test_uid}"
    assert me_data["full_name"] == "Advocate Ramesh Sharma"


def test_system_health_and_database_status(client):
    """
    Task 8.4.1: Verify /health and /health/db endpoints return structured database and runtime status.
    """
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "ollama" in data

    db_resp = client.get("/health/db")
    assert db_resp.status_code == 200
    db_data = db_resp.json()
    assert "status" in db_data
