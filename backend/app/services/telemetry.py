import os
import sys
import time
import json
import asyncio
import platform
import psutil
from typing import Dict, Any, Optional

def cpu_name() -> str:
    """Resolve clean CPU brand name via winreg on Windows or /proc/cpuinfo on Linux."""
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            cleaned = " ".join(str(val).split()).strip()
            if cleaned:
                return cleaned
        elif sys.platform.startswith("linux"):
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("model name"):
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                return " ".join(parts[1].split()).strip()
    except Exception:
        pass

    # Fallback to platform
    proc = platform.processor()
    if proc:
        return " ".join(proc.split()).strip()
    return f"{platform.machine()} Processor"


def _gpu_sample() -> Dict[str, Any]:
    """Non-blocking GPU view from the shared probe (never imports torch, never blocks a request)."""
    from app.system.gpu_probe import get_gpu_info
    info = get_gpu_info(block=False)
    total_mb = int(info.get("vram_total_mb") or 0)
    return {
        "detected": bool(info.get("detected")),
        "name": info.get("name") or ("Probing..." if info.get("status") == "probing" else "No dedicated GPU"),
        "vram_total_mb": total_mb,
        "vram_total_gb": round(total_mb / 1024, 1),
        "vram_reliable": bool(info.get("vram_reliable")),
        "backend": info.get("backend"),
        "cuda": info.get("backend") == "cuda",
        "mode": info.get("backend") or "cpu",
        "source": info.get("source"),
        "status": info.get("status"),
        "reason": info.get("reason"),
        "probed_at": info.get("probed_at"),
    }


def compute_hardware_tier(gpu_data: Dict[str, Any], ram_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes deterministic tier (Tier 0 to Tier 3) and descriptive reason:
    Tier 0: No GPU OR vram < 6 GB -> <= 3B models, 4-bit, ctx <= 4k
    Tier 1: VRAM 6-11 GB -> 7-8B Q4 models
    Tier 2: VRAM 12-23 GB -> 13-14B models
    Tier 3: VRAM >= 24 GB -> 32B+ / quantized 70B
    """
    # Unreliable VRAM (e.g. Windows WMI) is not used for tiering.
    vram_gb = gpu_data.get("vram_total_gb", 0.0) if gpu_data.get("vram_reliable", True) else 0.0
    ram_gb = ram_data.get("total_gb", 0.0)
    gpu_detected = gpu_data.get("detected", False)
    gpu_name = gpu_data.get("name", "Unknown GPU")

    if not gpu_detected or vram_gb < 6.0:
        tier_code = "tier_0"
        tier_label = "Tier 0 (Lightweight)"
        max_model = "3B (Q4)"
        if not gpu_detected:
            reason = f"Tier 0 — No CUDA GPU detected, {ram_gb} GB RAM available for CPU inference"
        else:
            reason = f"Tier 0 — {gpu_name} ({vram_gb} GB VRAM < 6 GB threshold), {ram_gb} GB RAM"
        recommended_category = "compact"
    elif 6.0 <= vram_gb < 12.0:
        tier_code = "tier_1"
        tier_label = "Tier 1 (Standard Legal)"
        max_model = "7B–8B (Q4)"
        reason = f"Tier 1 — {gpu_name} ({vram_gb} GB VRAM), standard legal domain models supported"
        recommended_category = "standard"
    elif 12.0 <= vram_gb < 24.0:
        tier_code = "tier_2"
        tier_label = "Tier 2 (High Performance)"
        max_model = "13B–14B (Q4/Q8)"
        reason = f"Tier 2 — {gpu_name} ({vram_gb} GB VRAM), large-context legal reasoning supported"
        recommended_category = "performance"
    else:
        tier_code = "tier_3"
        tier_label = "Tier 3 (Enterprise / Ultra)"
        max_model = "32B+ / 70B Quantized"
        reason = f"Tier 3 — {gpu_name} ({vram_gb} GB VRAM), full legal model suite supported"
        recommended_category = "enterprise"

    return {
        "tier_code": tier_code,
        "tier_label": tier_label,
        "reason": reason,
        "max_model": max_model,
        "recommended_category": recommended_category,
        "vram_gb": vram_gb,
        "ram_gb": ram_gb
    }


_cached_disk_info: Optional[tuple] = None
_cached_disk_time: float = 0.0


def _get_disk_usage() -> tuple:
    """Free/total space where models are stored (MODELS_DISK_PATH), cached 5 s. None when unmeasurable."""
    global _cached_disk_info, _cached_disk_time
    now = time.time()
    if _cached_disk_info is not None and (now - _cached_disk_time) < 5.0:
        return _cached_disk_info
    try:
        usage = psutil.disk_usage(os.getenv("MODELS_DISK_PATH", os.getcwd()))
        _cached_disk_info = (round(usage.free / (1024**3), 1), round(usage.total / (1024**3), 1))
    except Exception:
        _cached_disk_info = (None, None)
    _cached_disk_time = now
    return _cached_disk_info


_cached_cpu_name: Optional[str] = None

def sample() -> Dict[str, Any]:
    """Single telemetry snapshot. Must return in <50ms even without GPU."""
    global _cached_cpu_name
    if _cached_cpu_name is None:
        _cached_cpu_name = cpu_name()

    # CPU metrics (interval=None is instantaneous and non-blocking)
    cpu_load = psutil.cpu_percent(interval=None)
    phys_cores = psutil.cpu_count(logical=False) or 1
    log_cores = psutil.cpu_count(logical=True) or phys_cores

    # Memory metrics
    vm = psutil.virtual_memory()
    ram_total_gb = round(vm.total / (1024**3), 1)
    ram_available_gb = round(vm.available / (1024**3), 1)
    ram_used_percent = vm.percent

    # Disk metrics (safe root check across OS)
    disk_free_gb, disk_total_gb = _get_disk_usage()

    gpu_info = _gpu_sample()
    ram_info = {
        "total_gb": ram_total_gb,
        "available_gb": ram_available_gb,
        "used_percent": ram_used_percent
    }
    tier_info = compute_hardware_tier(gpu_info, ram_info)

    return {
        "status": "ok",
        "cpu": {
            "name": _cached_cpu_name,
            "load_percent": round(cpu_load, 1),
            "cores_physical": phys_cores,
            "cores_logical": log_cores,
            "arch": platform.machine() or "x86_64"
        },
        "ram": ram_info,
        "gpu": gpu_info,
        "disk": {
            "free_gb": disk_free_gb,
            "total_gb": disk_total_gb
        },
        "tier": tier_info,
        "ts": time.time(),
        "probed_at": time.time(),
    }


async def telemetry_event_generator(interval_seconds: float = 2.0, max_seconds: float = 600.0, request=None):
    """SSE snapshots. Bounded lifetime (the client reconnects) and stops when the client disconnects."""
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        if request is not None and await request.is_disconnected():
            return
        try:
            data = await asyncio.to_thread(sample)
            yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            return
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'error': type(e).__name__, 'ts': time.time()})}\n\n"
        await asyncio.sleep(interval_seconds)
