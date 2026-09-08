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
    """
    Atomic hardware summary returning all three probes (winreg CPU, psutil RAM, NVML/CUDA GPU)
    with a probed_at timestamp and independent probe fallback states (Task 6.1.1).
    """
    s = sample()
    cpu = s.get("cpu", {})
    ram = s.get("ram", {})
    gpu = s.get("gpu", {})
    tier = s.get("tier", {})
    
    gpu_detected = bool(gpu and gpu.get("detected"))
    gpu_name = gpu.get("name") if gpu else "No Dedicated GPU"
    gpu_vram = gpu.get("vram_total_gb", 0.0) if gpu else 0.0
    gpu_reason = None if gpu_detected else (gpu.get("reason") or "No dedicated NVIDIA/CUDA device detected")

    return {
        "probed_at": s.get("probed_at") or s.get("ts"),
        "cpu_cores": cpu.get("cores_physical", 1),
        "cpu_threads": cpu.get("cores_logical", 1),
        "cpu_name": cpu.get("name", "Multi-Core Processor"),
        "cpu_arch": cpu.get("arch", "x86_64"),
        "ram_total_gb": ram.get("total_gb", 8.0),
        "ram_available_gb": ram.get("available_gb", 4.0),
        "gpu_available": gpu_detected,
        "gpu_name": gpu_name,
        "gpu_vram_gb": gpu_vram,
        "hardware_tier": tier.get("tier_code", "tier_0"),
        "tier_name": tier.get("tier_label", "Tier 0 (Lightweight)"),
        "tier_reason": tier.get("reason", ""),
        "max_recommended_model": tier.get("max_model", "3B (Q4)"),
        "cpu": cpu,
        "ram": ram,
        "gpu": gpu if gpu_detected else None,
        "gpu_reason": gpu_reason,
    }
