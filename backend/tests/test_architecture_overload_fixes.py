import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.memory.request_memory import RequestMemory
from app.memory.research_memory import research_memory
from app.db.engine import get_sync_session
from app.db.models import ResearchSession, DocumentMemory
from app.cache.l3_embedding_cache import l3_embedding_cache
from app.orchestrator.state_machine import research_orchestrator, AgentState


def test_l1_request_memory():
    """Validates that RequestMemory tracks defense signals, tool calls, and latency."""
    mem = RequestMemory(session_id="test_sess", raw_query="What is IPC 302?")
    mem.record_defense_event("layer1", passed=True, details={"score": 0.05})
    mem.record_tool_call("local_server", "lookup", {"sec": 302}, "Murder definition")
    lat = mem.mark_completed()
    d = mem.to_dict()

    assert d["session_id"] == "test_sess"
    assert d["defense_signals"]["layer1"]["passed"] is True
    assert len(d["defense_signals"]) == 1
    assert d["tool_call_count"] == 1
    assert lat >= 0.0


def test_l5_research_memory_stale_cleanup():
    """Validates that active research sessions older than 1 hour are cleaned up to failed."""
    old_time = datetime.utcnow() - timedelta(hours=2)
    session_id = f"stale_sess_{int(time.time())}"
    with get_sync_session() as session:
        rs = ResearchSession(
            session_id=session_id,
            topic="Deep Legal Thinking Abandoned Run",
            status="active",
            created_at=old_time
        )
        session.add(rs)
        session.flush()

    cleaned = research_memory.cleanup_stale_active_sessions(max_age_seconds=3600)
    assert cleaned >= 1

    with get_sync_session() as session:
        rs_check = session.query(ResearchSession).filter_by(session_id=session_id).first()
        assert rs_check is not None
        assert rs_check.status == "failed"
        assert "timed out" in rs_check.findings


def test_l3_embedding_cache_memory_guard():
    """Validates that L3 embedding cache disables itself on systems with <= 8GB RAM."""
    mock_vm = MagicMock()
    mock_vm.total = 8 * (1024 ** 3)  # 8 GB

    with patch("psutil.virtual_memory", return_value=mock_vm):
        assert l3_embedding_cache.enabled is False

    mock_vm_16 = MagicMock()
    mock_vm_16.total = 16 * (1024 ** 3)  # 16 GB
    with patch("psutil.virtual_memory", return_value=mock_vm_16):
        assert l3_embedding_cache.enabled is True


def test_fsm_fast_path_detection():
    """Validates that simple statutory lookups trigger fast path detection."""
    assert research_orchestrator._is_simple_statutory_lookup("What is Section 302 of IPC?") is True
    assert research_orchestrator._is_simple_statutory_lookup("Section 420 IPC punishment") is True
    assert research_orchestrator._is_simple_statutory_lookup("Section 66 IT Act penalty") is True
    # Complex multihop queries should not use fast path
    assert research_orchestrator._is_simple_statutory_lookup("Compare Section 302 IPC with Section 103 BNS and synthesize deep research") is False


def test_consolidated_routes_available():
    """Validates that consolidated routers correctly expose telemetry, cache, and settings."""
    from app.main import app
    route_paths = [route.path for route in app.routes]

    # Models + Hardware
    assert "/telemetry/sample" in route_paths
    assert "/system/hardware" in route_paths
    assert "/models/auto-select" in route_paths

    # Diagnostics + Cache
    assert "/diagnostics" in route_paths
    assert "/cache/metrics" in route_paths
    assert "/cache/clear" in route_paths

    # Auth + Settings
    assert "/auth/login" in route_paths
    assert "/settings/fallback" in route_paths
