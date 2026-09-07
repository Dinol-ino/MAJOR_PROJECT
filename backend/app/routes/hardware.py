from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.telemetry import sample, telemetry_event_generator

router = APIRouter(tags=["hardware", "telemetry"])


@router.get("/telemetry/stream")
@router.get("/api/telemetry/stream")
async def get_telemetry_stream():
    """Real-time SSE stream delivering system telemetry snapshots every 2 seconds."""
    return StreamingResponse(
        telemetry_event_generator(interval_seconds=2.0),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/telemetry/sample")
@router.get("/api/telemetry/sample")
def get_telemetry_sample():
    """Instantaneous single telemetry snapshot (<50ms)."""
    return sample()


@router.get("/system/hardware")
def get_system_hardware():
    """Backward-compatible fast hardware summary."""
    s = sample()
    cpu = s["cpu"]
    ram = s["ram"]
    gpu = s["gpu"]
    tier = s["tier"]
    return {
        "cpu_cores": cpu["cores_physical"],
        "cpu_threads": cpu["cores_logical"],
        "cpu_name": cpu["name"],
        "cpu_arch": cpu["arch"],
        "ram_total_gb": ram["total_gb"],
        "ram_available_gb": ram["available_gb"],
        "gpu_available": gpu["detected"],
        "gpu_name": gpu["name"],
        "gpu_vram_gb": gpu.get("vram_total_gb", 0.0),
        "hardware_tier": tier["tier_code"],
        "tier_name": tier["tier_label"],
        "tier_reason": tier["reason"],
        "max_recommended_model": tier["max_model"]
    }
