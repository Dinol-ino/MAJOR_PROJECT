# pyrefly: ignore [missing-import]
import os
import sys
import time
import platform
import shutil
import logging
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class HardwareProfile:
    cpu_cores: int
    cpu_name: str
    ram_total_gb: float
    ram_available_gb: float
    gpu_available: bool
    gpu_name: Optional[str]
    gpu_vram_gb: Optional[float]
    gpu_backend: Optional[str]          # "cuda" | "rocm" | "metal" | None
    storage_free_gb: float
    platform_name: str                  # "windows" | "linux" | "darwin"
    supports_avx2: bool

class HardwareDetector:
    _cached_profile: Optional[HardwareProfile] = None
    _cached_time: float = 0.0

    @classmethod
    def detect(cls, force_refresh: bool = False, cache_ttl: int = 300) -> HardwareProfile:
        now = time.time()
        if not force_refresh and cls._cached_profile is not None and (now - cls._cached_time) < cache_ttl:
            return cls._cached_profile

        profile = cls._perform_detection()
        cls._cached_profile = profile
        cls._cached_time = now
        return profile

    @classmethod
    def _perform_detection(cls) -> HardwareProfile:
        # 1. CPU
        try:
            import psutil
            cpu_cores = psutil.cpu_count(logical=False) or os.cpu_count() or 1
        except Exception:
            cpu_cores = os.cpu_count() or 1

        cpu_name = platform.processor() or platform.machine() or "Unknown CPU"

        # 2. RAM
        try:
            import psutil
            mem = psutil.virtual_memory()
            ram_total_gb = round(mem.total / (1024 ** 3), 2)
            ram_available_gb = round(mem.available / (1024 ** 3), 2)
        except Exception:
            ram_total_gb = 8.0
            ram_available_gb = 4.0

        # 3. GPU / VRAM / Backend
        gpu_available = False
        gpu_name = None
        gpu_vram_gb = None
        gpu_backend = None

        # Try torch first
        try:
            import torch
            if torch.cuda.is_available():
                gpu_available = True
                gpu_name = torch.cuda.get_device_name(0)
                vram_bytes = torch.cuda.get_device_properties(0).total_memory
                gpu_vram_gb = round(vram_bytes / (1024 ** 3), 2)
                gpu_backend = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                gpu_available = True
                gpu_name = "Apple Silicon Metal"
                gpu_vram_gb = ram_total_gb  # Unified memory
                gpu_backend = "metal"
        except Exception as e:
            logger.debug(f"Torch GPU detection bypassed: {e}")

        # Fallback to nvidia-smi if torch didn't detect CUDA
        if not gpu_available:
            try:
                import subprocess
                res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if res.returncode == 0 and res.stdout.strip():
                    line = res.stdout.strip().split("\n")[0]
                    parts = line.split(",")
                    if len(parts) >= 2:
                        gpu_name = parts[0].strip()
                        gpu_vram_gb = round(float(parts[1].strip()) / 1024.0, 2)
                        gpu_available = True
                        gpu_backend = "cuda"
            except Exception as e:
                logger.debug(f"nvidia-smi detection bypassed: {e}")

        # 4. Storage Free
        try:
            target_path = os.getcwd()
            total, used, free = shutil.disk_usage(target_path)
            storage_free_gb = round(free / (1024 ** 3), 2)
        except Exception:
            storage_free_gb = 10.0

        # 5. OS & AVX2
        platform_name = platform.system().lower()
        supports_avx2 = True  # Modern x86_64 / arm64 default assumption

        return HardwareProfile(
            cpu_cores=cpu_cores,
            cpu_name=cpu_name,
            ram_total_gb=ram_total_gb,
            ram_available_gb=ram_available_gb,
            gpu_available=gpu_available,
            gpu_name=gpu_name,
            gpu_vram_gb=gpu_vram_gb,
            gpu_backend=gpu_backend,
            storage_free_gb=storage_free_gb,
            platform_name=platform_name,
            supports_avx2=supports_avx2
        )
