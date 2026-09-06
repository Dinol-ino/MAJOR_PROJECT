import logging
import psutil
from typing import Optional
from fastapi import APIRouter, HTTPException

from app.observability.metrics import metrics_collector
from app.runtime.manager import runtime_manager
from app.network.mode_enforcer import mode_enforcer
from app.orchestrator.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("")
async def get_diagnostics_overview():
    """
    Local-only diagnostics dashboard endpoint (Phase 11).
    Returns real-time system resource health, model tier status, network isolation status,
    circuit breakers, and latency aggregates.
    """
    try:
        proc = psutil.Process()
        cpu_pct = psutil.cpu_percent(interval=None)
        mem_info = proc.memory_info()
        sys_mem = psutil.virtual_memory()
    except Exception:
        cpu_pct = 0.0
        mem_info = None
        sys_mem = None

    summary = metrics_collector.get_summary()

    return {
        "status": "healthy",
        "system_resources": {
            "process_cpu_percent": cpu_pct,
            "process_memory_mb": round(mem_info.rss / (1024 * 1024), 2) if mem_info else 0.0,
            "system_memory_total_mb": round(sys_mem.total / (1024 * 1024), 2) if sys_mem else 0.0,
            "system_memory_available_mb": round(sys_mem.available / (1024 * 1024), 2) if sys_mem else 0.0,
            "system_memory_percent": sys_mem.percent if sys_mem else 0.0,
        },
        "network_isolation": {
            "mode": mode_enforcer.get_mode(),
            "is_offline": mode_enforcer.is_offline(),
        },
        "runtime_status": runtime_manager.get_status(),
        "circuit_breakers": circuit_breaker.get_all_status(),
        "metrics_summary": summary,
        "recent_requests_count": summary.get("active_buffer_size", 0),
    }


@router.get("/trace/{request_id}")
async def get_request_trace(request_id: str):
    """
    Returns the correlated per-request trace across all state machine stages,
    retrieval layers, and model inferences.
    """
    trace = metrics_collector.get_trace(request_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"No trace found for request_id '{request_id}'")
    return trace


@router.get("/metrics/recent")
async def get_recent_metrics(limit: int = 50):
    """
    Returns recent sanitized request telemetry records.
    """
    return {
        "count": min(limit, 100),
        "records": metrics_collector.get_recent_metrics(limit=min(limit, 100))
    }


@router.get("/metrics/summary")
async def get_metrics_summary():
    """
    Returns aggregate performance summary (p50, p95, p99, TTFT, retrieval avg).
    """
    return metrics_collector.get_summary()
