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

    @classmethod
    def _resolve_tier_model(cls, tier_level: int, fallback_id: str, prefer_minimum: bool = False) -> str:
        try:
            from app.system.model_registry import ModelRegistry
            registry = ModelRegistry()
            tier_tag = "premium" if tier_level == 2 else ("standard" if tier_level == 1 else "minimum")
            candidates = [m for m in registry.all_models() if m.tier == tier_tag]
            if candidates:
                if prefer_minimum:
                    candidates.sort(key=lambda m: m.size_gb)
                    return candidates[0].model_id
                else:
                    candidates.sort(key=lambda m: m.size_gb)
                    return candidates[-1].model_id
        except Exception as exc:
            logger.debug(f"Could not dynamically query ModelRegistry for tier {tier_level}: {exc}")
        return fallback_id

    @classmethod
    def get_auto_selected_tier(cls, profile: Optional[HardwareProfile] = None) -> dict:
        """
        Maps detected hardware profile to model tier with realistic memory budgets:
        - CUDA overhead: ~1 GB for driver + KV cache + fragmentation
        - Effective VRAM = total VRAM - 1.0 GB overhead
        - Tier 0 Floor (2B): < 6 GB effective (gemma2:2b at 1.6 GB fits in ~3 GB effective)
        - Tier 0 (3B): 6-8 GB effective
        - Tier 1 (7-8B): 8-16 GB effective
        - Tier 2 (13-15B): > 16 GB effective
        """
        p = profile or cls.detect()

        # Calculate effective usable memory with realistic overhead
        cuda_overhead_gb = 1.0  # driver + KV cache + fragmentation
        if p.gpu_available and p.gpu_vram_gb:
            effective_vram = max(0, p.gpu_vram_gb - cuda_overhead_gb)
        else:
            effective_vram = 0

        # For CPU-only mode, effective memory is available RAM minus ~1 GB OS headroom
        effective_ram = max(0, p.ram_available_gb - 1.0)

        # Use whichever is larger
        usable_memory = max(effective_vram, effective_ram)

        # Determine if GPU offload should be disabled (force CPU mode)
        force_cpu = False
        if p.gpu_available and p.gpu_vram_gb and p.gpu_vram_gb < 6.0:
            # GPU exists but is too small for any model — force CPU-only
            force_cpu = True

        if usable_memory >= 16.0:
            tier = 2
            tier_name = "Tier 2 (High Performance)"
            default_model = cls._resolve_tier_model(2, "qwen2.5:14b")
            upgrade_opt_in = True
        elif usable_memory >= 8.0:
            tier = 1
            tier_name = "Tier 1 (Standard Legal)"
            default_model = cls._resolve_tier_model(1, "qwen2.5:7b")
            upgrade_opt_in = True
        elif usable_memory >= 3.0:
            tier = 0
            tier_name = "Tier 0 (Standard Floor)"
            default_model = cls._resolve_tier_model(0, "qwen2.5:3b")
            upgrade_opt_in = False
        else:
            tier = 0
            tier_name = "Tier 0 (Minimum Floor)"
            default_model = cls._resolve_tier_model(0, "gemma2:2b", prefer_minimum=True)
            upgrade_opt_in = False
            force_cpu = True  # Not enough memory for GPU mode at all

        return {
            "tier": tier,
            "tier_name": tier_name,
            "default_model": default_model,
            "usable_memory_gb": round(usable_memory, 2),
            "upgrade_opt_in": upgrade_opt_in,
            "force_cpu": force_cpu,
            "effective_vram_gb": round(effective_vram, 2),
            "effective_ram_gb": round(effective_ram, 2),
        }

    @classmethod
    def validate_override(cls, claimed_vram_gb: Optional[float] = None, claimed_ram_gb: Optional[float] = None) -> dict:
        """
        Validates user-typed form values against detected physical reality.
        Emits warnings if user claims resources exceeding detected hardware.
        """
        profile = cls.detect()
        warnings = []

        if claimed_vram_gb is not None and profile.gpu_vram_gb:
            if claimed_vram_gb > profile.gpu_vram_gb:
                msg = f"User override claimed {claimed_vram_gb} GB VRAM, but only {profile.gpu_vram_gb} GB was detected."
                logger.warning(msg)
                warnings.append(msg)

        if claimed_ram_gb is not None:
            if claimed_ram_gb > profile.ram_total_gb:
                msg = f"User override claimed {claimed_ram_gb} GB RAM, but only {profile.ram_total_gb} GB physical RAM was detected."
                logger.warning(msg)
                warnings.append(msg)

        return {
            "valid": len(warnings) == 0,
            "warnings": warnings,
            "detected_profile": asdict(profile)
        }

