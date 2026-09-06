import time
import asyncio
import logging
from typing import Dict, Any
from sqlalchemy import text
from app.db.engine import get_async_engine, get_sync_engine

logger = logging.getLogger(__name__)


async def _run_probe(engine) -> tuple:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        return result.scalar()


async def check_db_health() -> Dict[str, Any]:
    """
    Checks database reachability, measures roundtrip latency, and inspects pool status.
    Returns structured health telemetry with bounded timeout protection.
    """
    start = time.perf_counter()
    status = "healthy"
    latency_ms = None
    error_msg = None
    pool_stats = {}

    try:
        engine = get_async_engine()
        val = await asyncio.wait_for(_run_probe(engine), timeout=2.5)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        if val != 1:
            status = "degraded"

        # Inspect pool stats
        pool = engine.pool
        pool_stats = {
            "size": getattr(pool, "size", lambda: None)(),
            "checked_in": getattr(pool, "checkedin", lambda: None)(),
            "checked_out": getattr(pool, "checkedout", lambda: None)(),
            "overflow": getattr(pool, "overflow", lambda: None)(),
        }
    except Exception as exc:
        status = "offline"
        error_msg = str(exc)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.debug(f"Database health check offline: {exc}")

    return {
        "status": status,
        "latency_ms": latency_ms,
        "pool": pool_stats,
        "error": error_msg,
    }
