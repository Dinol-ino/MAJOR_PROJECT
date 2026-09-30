import httpx
import pytest

from app.mcp.connectors import ecourts
from app.mcp.gateway import mcp_gateway
from app.network.mode_enforcer import mode_enforcer

PAYLOAD = {"data": {"results": [{"cnr": "DLHC010001232024", "caseType": "RFA", "caseStatus": "PENDING",
           "filingDate": "2024-01-15", "petitioners": ["ABC Pvt Ltd"], "respondents": ["XYZ Corp"],
           "courtCode": "DLHC01", "judges": ["J. Sharma"]}], "totalHits": 1}, "meta": {}}


@pytest.fixture
def mock_api(monkeypatch):
    seen = {}
    def handler(req: httpx.Request):
        seen["auth"] = req.headers.get("authorization"); seen["url"] = str(req.url)
        return httpx.Response(200, json=PAYLOAD)
    monkeypatch.setattr(ecourts, "_transport", httpx.MockTransport(handler))
    monkeypatch.setenv("ECOURTSINDIA_API_KEY", "eci_live_test")
    yield seen
    mode_enforcer._current_mode = "OFFLINE"


def test_blocked_in_offline_mode(mock_api):
    mode_enforcer._current_mode = "OFFLINE"
    r = mcp_gateway.execute_tool("ecourts_case_search", {"keywords": "bail cheating"}, session_id="s")
    assert r.success is False and "url" not in mock_api


def test_online_returns_labelled_external_metadata(mock_api):
    mode_enforcer._current_mode = "ONLINE"
    r = mcp_gateway.execute_tool("ecourts_case_search", {"keywords": "bail cheating"}, session_id="s")
    assert r.success is True, r
    out = r.output if hasattr(r, "output") else r.data
    assert out["cases"][0]["source_kind"] == "external"
    assert "external source" in out["source"]
    assert mock_api["auth"] == "Bearer eci_live_test"
    assert "webapi.ecourtsindia.com" in mock_api["url"]


def test_pii_is_scrubbed_from_outbound_query(mock_api):
    mode_enforcer._current_mode = "ONLINE"
    mcp_gateway.execute_tool("ecourts_case_search",
                             {"keywords": "bail for client raj.kumar@example.com"}, session_id="s")
    assert "raj.kumar" not in mock_api.get("url", "")


def test_missing_key_reports_unavailable(monkeypatch):
    monkeypatch.delenv("ECOURTSINDIA_API_KEY", raising=False)
    mode_enforcer._current_mode = "ONLINE"
    try:
        r = mcp_gateway.execute_tool("ecourts_case_search", {"keywords": "bail cheating"}, session_id="s")
        assert r.success is False
    finally:
        mode_enforcer._current_mode = "OFFLINE"
