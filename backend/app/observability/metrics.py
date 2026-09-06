import time
import psutil
import logging
from collections import deque
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.config import settings
from app.observability.correlation import get_correlation_id
from app.observability.redaction import observability_redactor
from app.db.engine import get_sync_session
from app.db.models import RequestMetricsRecord

logger = logging.getLogger(__name__)


class StageMetric(BaseModel):
    stage_name: str
    duration_ms: float
    status: str = "success"
    details: Dict[str, Any] = Field(default_factory=dict)


class RequestMetric(BaseModel):
    """
    Comprehensive Per-Request Observability Record (Phase 11).
    Correlated by unique request_id.
    """
    request_id: str = Field(default_factory=get_correlation_id)
    session_id: Optional[str] = "default_session"
    endpoint: str = "/chat"
    total_duration_ms: float = 0.0
    api_overhead_ms: float = 0.0
    time_to_first_token_ms: Optional[float] = None
    generation_time_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    retrieval_breakdown: Dict[str, float] = Field(default_factory=lambda: {"bm25_ms": 0.0, "dense_ms": 0.0, "pageindex_ms": 0.0})
    embedding_latency_ms: float = 0.0
    database_latency_ms: float = 0.0
    mcp_latency_ms: float = 0.0
    tool_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hits: Dict[str, int] = Field(default_factory=lambda: {"L1": 0, "L2": 0, "L3": 0})
    cache_misses: Dict[str, int] = Field(default_factory=lambda: {"L1": 0, "L2": 0, "L3": 0})
    model_tier: str = "TIER_0_CPU_FLOOR"
    model_name: str = "gemma2:2b"
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    vram_mb: float = 0.0
    security_blocked: bool = False
    security_reason: Optional[str] = None
    circuit_breaker_tripped: bool = False
    stages: List[StageMetric] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class MetricsCollector:
    """
    In-Process Telemetry & Metrics Collector (Phase 11).
    Maintains a high-speed bounded in-memory buffer and synchronizes with the database.
    """

    def __init__(self, buffer_size: int = 1000):
        self.buffer_size = buffer_size
        self._buffer: deque = deque(maxlen=buffer_size)
        self._by_request_id: Dict[str, RequestMetric] = {}

    def record_request_metric(self, metric: RequestMetric) -> None:
        """
        Records a completed request metric, sanitizes it via Redactor,
        and saves to memory buffer and DB.
        """
        # Capture current host resource consumption if not provided
        if metric.cpu_percent == 0.0:
            try:
                proc = psutil.Process()
                metric.cpu_percent = psutil.cpu_percent(interval=None)
                metric.memory_mb = proc.memory_info().rss / (1024 * 1024)
            except Exception:
                pass

        # Sanitize any residual sensitive text
        sanitized_dict = observability_redactor.sanitize_telemetry_payload(metric.model_dump())

        # Update in-memory ring buffer
        self._buffer.append(metric)
        self._by_request_id[metric.request_id] = metric
        if len(self._by_request_id) > self.buffer_size:
            # Pop oldest
            oldest = list(self._by_request_id.keys())[0]
            self._by_request_id.pop(oldest, None)

        # Persist to database
        try:
            with get_sync_session() as db:
                rec = RequestMetricsRecord(
                    request_id=metric.request_id,
                    session_id=metric.session_id,
                    endpoint=metric.endpoint,
                    total_duration_ms=metric.total_duration_ms,
                    ttft_ms=metric.time_to_first_token_ms,
                    retrieval_ms=metric.retrieval_latency_ms,
                    mcp_ms=metric.mcp_latency_ms,
                    tokens_in=metric.input_tokens,
                    tokens_out=metric.output_tokens,
                    model_tier=metric.model_tier,
                    security_blocked=1 if metric.security_blocked else 0,
                    metrics_json=sanitized_dict
                )
                db.add(rec)
        except Exception as exc:
            logger.warning(f"Failed to persist request metric to DB: {exc}")

    def get_trace(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Returns full execution trace and stage breakdown for a specific correlation ID."""
        if request_id in self._by_request_id:
            return self._by_request_id[request_id].model_dump()

        # Check DB
        try:
            with get_sync_session() as db:
                rec = db.query(RequestMetricsRecord).filter_by(request_id=request_id).first()
                if rec:
                    return rec.to_dict()
        except Exception as exc:
            logger.warning(f"Error querying trace from DB: {exc}")

        return None

    def get_recent_metrics(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent metrics from in-memory ring buffer."""
        items = list(self._buffer)[-limit:]
        return [item.model_dump() for item in reversed(items)]

    def get_summary(self) -> Dict[str, Any]:
        """
        Computes aggregate metrics: p50/p95/p99 latency, average TTFT,
        retrieval breakdown, token throughput, and cache hit rates.
        """
        items = list(self._buffer)
        total_reqs = len(items)
        if total_reqs == 0:
            return {
                "total_requests": 0,
                "p50_total_ms": 0.0,
                "p95_total_ms": 0.0,
                "p99_total_ms": 0.0,
                "avg_ttft_ms": 0.0,
                "avg_retrieval_ms": 0.0,
                "avg_tokens_per_sec": 0.0,
                "cache_hit_rate": 0.0,
                "security_block_rate": 0.0,
            }

        total_latencies = sorted([m.total_duration_ms for m in items])
        ttfts = [m.time_to_first_token_ms for m in items if m.time_to_first_token_ms is not None]
        retrieval_latencies = [m.retrieval_latency_ms for m in items]
        sec_blocks = sum(1 for m in items if m.security_blocked)

        p50 = total_latencies[int(total_reqs * 0.50)] if total_reqs else 0.0
        p95 = total_latencies[min(int(total_reqs * 0.95), total_reqs - 1)] if total_reqs else 0.0
        p99 = total_latencies[min(int(total_reqs * 0.99), total_reqs - 1)] if total_reqs else 0.0

        avg_ttft = sum(ttfts) / len(ttfts) if ttfts else 0.0
        avg_retrieval = sum(retrieval_latencies) / len(retrieval_latencies) if retrieval_latencies else 0.0

        # Cache calculations
        total_hits = sum(sum(m.cache_hits.values()) for m in items)
        total_misses = sum(sum(m.cache_misses.values()) for m in items)
        total_lookups = total_hits + total_misses
        cache_hit_rate = (total_hits / total_lookups) if total_lookups > 0 else 0.0

        return {
            "total_requests": total_reqs,
            "p50_total_ms": round(p50, 2),
            "p95_total_ms": round(p95, 2),
            "p99_total_ms": round(p99, 2),
            "avg_ttft_ms": round(avg_ttft, 2),
            "avg_retrieval_ms": round(avg_retrieval, 2),
            "cache_hit_rate": round(cache_hit_rate, 4),
            "security_block_rate": round(sec_blocks / total_reqs, 4),
            "active_buffer_size": len(self._buffer),
        }


metrics_collector = MetricsCollector()
