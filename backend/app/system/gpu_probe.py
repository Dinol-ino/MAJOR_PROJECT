"""
Single GPU probe shared by live telemetry and the model-fit HardwareDetector.

- Never imports torch (seconds of import time and hundreds of MB of RAM just to ask about a GPU).
- Every external probe has a hard timeout; results are cached; the probe runs off the request path.
- Values that cannot be measured are reported as unknown, not guessed.
"""
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT = float(os.getenv("GPU_PROBE_TIMEOUT_SECONDS", "3"))
_CACHE_TTL = float(os.getenv("GPU_PROBE_CACHE_SECONDS", "300"))

_lock = threading.Lock()
_cached: Optional[Dict[str, Any]] = None
_cached_at: float = 0.0
_probe_thread: Optional[threading.Thread] = None


def _no_gpu(reason: str, source: str = "none") -> Dict[str, Any]:
    return {
        "detected": False, "name": None, "vram_total_mb": 0, "backend": None,
        "source": source, "vram_reliable": True, "status": "not_detected", "reason": reason,
    }


def _probe_nvml() -> Optional[Dict[str, Any]]:
    try:
        import pynvml  # optional dependency
    except ImportError:
        return None
    try:
        pynvml.nvmlInit()
        if pynvml.nvmlDeviceGetCount() < 1:
            return None
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        name = name.decode("utf-8") if isinstance(name, bytes) else str(name)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return {"detected": True, "name": name, "vram_total_mb": int(mem.total // (1024 ** 2)), "backend": "cuda",
                "source": "nvml", "vram_reliable": True, "status": "detected", "reason": None}
    except Exception as exc:
        logger.debug("NVML probe failed: %s", type(exc).__name__)
        return None
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass


def _probe_nvidia_smi() -> Optional[Dict[str, Any]]:
    candidates = ["nvidia-smi"]
    if sys.platform == "win32":
        candidates += [r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"]
    for cmd in candidates:
        if not (shutil.which(cmd) or os.path.isfile(cmd)):
            continue
        try:
            res = subprocess.run(
                [cmd, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=_PROBE_TIMEOUT,
            )
            if res.returncode == 0 and res.stdout.strip():
                name, total = [p.strip() for p in res.stdout.strip().splitlines()[0].split(",")[:2]]
                return {"detected": True, "name": name, "vram_total_mb": int(float(total)), "backend": "cuda",
                        "source": "nvidia-smi", "vram_reliable": True, "status": "detected", "reason": None}
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            logger.debug("nvidia-smi probe failed: %s", type(exc).__name__)
    return None


def _probe_apple_silicon() -> Optional[Dict[str, Any]]:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        return None
    return {"detected": True, "name": "Apple Silicon (unified memory)", "vram_total_mb": 0, "backend": "metal",
            "source": "platform", "vram_reliable": False, "status": "detected",
            "reason": "Unified memory: GPU budget is shared with system RAM."}


def _probe_windows_wmi() -> Optional[Dict[str, Any]]:
    if sys.platform != "win32":
        return None
    try:
        cmd = ("Get-CimInstance Win32_VideoController | Where-Object { $_.Name -like '*NVIDIA*' -or $_.Name -like '*Radeon*' } "
               "| Select-Object -First 1 Name, AdapterRAM | ConvertTo-Json")
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=_PROBE_TIMEOUT)
        if res.returncode != 0 or not res.stdout.strip():
            return None
        data = json.loads(res.stdout.strip())
        name = data.get("Name")
        raw = data.get("AdapterRAM") or 0
        # AdapterRAM is a 32-bit field (caps at 4 GB) and 0 on many drivers: never trusted for model fit.
        return {"detected": True, "name": name, "vram_total_mb": int(raw // (1024 ** 2)) if raw else 0,
                "backend": "cuda" if "nvidia" in (name or "").lower() else "unknown",
                "source": "wmi", "vram_reliable": False, "status": "detected",
                "reason": "VRAM reported by Windows WMI is unreliable; install NVIDIA drivers with nvidia-smi for an exact value."}
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        logger.debug("WMI probe failed: %s", type(exc).__name__)
        return None


def _run_probe() -> Dict[str, Any]:
    t0 = time.perf_counter()
    result = None
    for probe in (_probe_nvml, _probe_nvidia_smi, _probe_apple_silicon, _probe_windows_wmi):
        try:
            result = probe()
        except Exception as exc:  # a failing probe must never take the others down
            logger.debug("GPU probe %s crashed: %s", probe.__name__, type(exc).__name__)
            result = None
        if result:
            break
    result = result or _no_gpu("No dedicated GPU found by NVML, nvidia-smi or the OS.")
    result["probe_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    result["probed_at"] = time.time()
    return result


def refresh_in_background() -> None:
    """Starts one background probe if none is running (bounded: at most one probe thread)."""
    global _probe_thread
    with _lock:
        if _probe_thread and _probe_thread.is_alive():
            return

        def _worker():
            global _cached, _cached_at
            data = _run_probe()
            with _lock:
                _cached, _cached_at = data, time.time()

        _probe_thread = threading.Thread(target=_worker, name="gpu-probe", daemon=True)
        _probe_thread.start()


def get_gpu_info(block: bool = False, timeout: Optional[float] = None) -> Dict[str, Any]:
    """
    Cached GPU info. Non-blocking by default: returns status "probing" while the first probe runs.
    `block=True` waits (bounded) for a result — used by model-fit decisions that must not guess.
    """
    with _lock:
        cached, age = _cached, time.time() - _cached_at
    if cached is not None and age < _CACHE_TTL:
        return dict(cached)
    refresh_in_background()
    if block:
        thread = _probe_thread
        if thread:
            thread.join(timeout if timeout is not None else _PROBE_TIMEOUT * 3 + 1)
        with _lock:
            if _cached is not None:
                return dict(_cached)
    if cached is not None:
        return dict(cached)  # stale but real; refresh is under way
    return {"detected": False, "name": None, "vram_total_mb": 0, "backend": None, "source": None,
            "vram_reliable": False, "status": "probing", "reason": "GPU probe in progress"}
