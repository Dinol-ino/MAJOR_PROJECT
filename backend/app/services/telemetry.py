import os
import sys
import time
import json
import asyncio
import platform
import psutil
from typing import Dict, Any, Optional

try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
except (ImportError, Exception):
    NVML_AVAILABLE = False


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
    """Fast non-blocking GPU sample using NVML or torch. Returns CPU mode if not available."""
    if NVML_AVAILABLE:
        try:
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name_bytes = pynvml.nvmlDeviceGetName(handle)
                name = name_bytes.decode("utf-8") if isinstance(name_bytes, bytes) else str(name_bytes)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                total_mb = int(mem.total // (1024**2))
                used_mb = int(mem.used // (1024**2))
                total_gb = round(total_mb / 1024, 1)
                used_gb = round(used_mb / 1024, 1)
                return {
                    "detected": True,
                    "name": name,
                    "vram_total_mb": total_mb,
                    "vram_used_mb": used_mb,
                    "vram_total_gb": total_gb,
                    "vram_used_gb": used_gb,
                    "util_percent": int(util.gpu),
                    "cuda": True,
                    "mode": "cuda"
                }
        except Exception:
            pass

    # Secondary fast check via torch if available
    try:
        import torch
        if torch.cuda.is_available():
            device_idx = 0
            name = torch.cuda.get_device_name(device_idx)
            total_bytes = torch.cuda.get_device_properties(device_idx).total_memory
            total_mb = int(total_bytes // (1024**2))
            total_gb = round(total_mb / 1024, 1)
            used_bytes = torch.cuda.memory_allocated(device_idx)
            used_mb = int(used_bytes // (1024**2))
            used_gb = round(used_mb / 1024, 1)
            return {
                "detected": True,
                "name": name,
                "vram_total_mb": total_mb,
                "vram_used_mb": used_mb,
                "vram_total_gb": total_gb,
                "vram_used_gb": used_gb,
                "util_percent": 0,
                "cuda": True,
                "mode": "cuda"
            }
    except Exception:
        pass

    return {
        "detected": False,
        "name": "No Dedicated GPU (CPU Only)",
        "vram_total_mb": 0,
        "vram_used_mb": 0,
        "vram_total_gb": 0.0,
        "vram_used_gb": 0.0,
        "util_percent": 0,
        "cuda": False,
        "mode": "cpu"
    }


def compute_hardware_tier(gpu_data: Dict[str, Any], ram_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes deterministic tier (Tier 0 to Tier 3) and descriptive reason:
    Tier 0: No GPU OR vram < 6 GB -> <= 3B models, 4-bit, ctx <= 4k
    Tier 1: VRAM 6-11 GB -> 7-8B Q4 models
    Tier 2: VRAM 12-23 GB -> 13-14B models
    Tier 3: VRAM >= 24 GB -> 32B+ / quantized 70B
    """
    vram_gb = gpu_data.get("vram_total_gb", 0.0)
    ram_gb = ram_data.get("total_gb", 8.0)
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
    try:
        root_path = "C:\\" if sys.platform == "win32" else "/"
        disk_free_gb = round(psutil.disk_usage(root_path).free / (1024**3), 1)
        disk_total_gb = round(psutil.disk_usage(root_path).total / (1024**3), 1)
    except Exception:
        disk_free_gb = 50.0
        disk_total_gb = 500.0

    gpu_info = _gpu_sample()
    ram_info = {
        "total_gb": ram_total_gb,
        "available_gb": ram_available_gb,
        "used_percent": ram_used_percent
    }
    tier_info = compute_hardware_tier(gpu_info, ram_info)

    return {
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
        "ts": time.time()
    }


async def telemetry_event_generator(interval_seconds: float = 2.0):
    """Asynchronously generates SSE data chunks every interval."""
    while True:
        try:
            data = sample()
            yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            break
        except Exception as e:
            err_data = {"error": str(e), "ts": time.time()}
            yield f"data: {json.dumps(err_data)}\n\n"
        await asyncio.sleep(interval_seconds)
