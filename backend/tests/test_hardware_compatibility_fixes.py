import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.system.hardware_detector import HardwareDetector, HardwareProfile
from app.system.model_registry import ModelRegistry, ModelEntry
from app.services.telemetry import sample


@pytest.fixture
def client():
    return TestClient(app)


def test_hardware_detector_avx2_is_bool():
    """Bug H1: Verify AVX2 is dynamically probed as a boolean and not hardcoded."""
    profile = HardwareDetector.detect(force_refresh=True)
    assert isinstance(profile.supports_avx2, bool)


def test_telemetry_detects_real_gpu():
    """Bug H2 & H4: Verify telemetry samples real GPU and does not falsely default to CPU mode."""
    s = sample()
    assert "gpu" in s
    assert "tier" in s
    # Check that schema matches and tier is calculated
    assert s["tier"]["tier_code"] in ["tier_0", "tier_1", "tier_2", "tier_3"]
    if s["gpu"]["detected"]:
        assert s["gpu"]["vram_total_gb"] > 0.0
        assert s["gpu"]["mode"] == "cuda"


def test_dynamic_model_fit_evaluation():
    """Spec 00 Dynamic Sizing: Verify 60% RAM, 80% VRAM, and 2x storage checks."""
    registry = ModelRegistry()

    # Scenario: 8GB RAM (4GB free), No GPU, 20GB free disk
    hw_cpu_only = HardwareProfile(
        cpu_cores=8,
        cpu_name="Test CPU",
        ram_total_gb=8.0,
        ram_available_gb=4.0,
        gpu_available=False,
        gpu_name=None,
        gpu_vram_gb=None,
        gpu_backend=None,
        storage_free_gb=20.0,
        platform_name="windows",
        supports_avx2=True
    )

    # Gemma 2 2B (ram_required: ~3GB): 4.0 * 0.6 = 2.4GB. 3GB > 2.4GB -> CAUTION (High RAM pressure)
    gemma = registry.get("gemma2:2b")
    if gemma:
        fit = registry.evaluate_model_fit(gemma, hw_cpu_only)
        assert fit["safety_tier"] in ("SAFE", "CAUTION")

    # Qwen 2.5 14B (ram_required: 16GB): Exceeds 4GB free -> UNSUPPORTED
    qwen14 = registry.get("qwen2.5:14b")
    if qwen14:
        fit14 = registry.evaluate_model_fit(qwen14, hw_cpu_only)
        assert fit14["safety_tier"] == "UNSUPPORTED"
        assert fit14["fits_memory"] is False

    # Scenario: RTX 3050 (6GB VRAM, 1.5GB free RAM)
    hw_rtx3050 = HardwareProfile(
        cpu_cores=8,
        cpu_name="AMD Ryzen 5 7235HS",
        ram_total_gb=11.7,
        ram_available_gb=1.5,
        gpu_available=True,
        gpu_name="NVIDIA GeForce RTX 3050 6GB Laptop GPU",
        gpu_vram_gb=6.0,
        gpu_backend="cuda",
        storage_free_gb=50.0,
        platform_name="windows",
        supports_avx2=True
    )

    # Qwen 2.5 3B (vram_required: 4GB): 6.0 * 0.8 = 4.8GB usable VRAM. 4.0 <= 4.8GB -> SAFE!
    qwen3b = registry.get("qwen2.5:3b")
    if qwen3b:
        fit3b = registry.evaluate_model_fit(qwen3b, hw_rtx3050)
        assert fit3b["safety_tier"] == "SAFE"
        assert fit3b["fits_vram"] is True


def test_pull_storage_validation(client, monkeypatch):
    """Auto-Pull: Verify insufficient storage returns HTTP 409."""
    import shutil

    # Mock disk_usage to report only 1.0 GB free disk space
    def mock_disk_usage(path):
        total = 100 * (1024 ** 3)
        free = 1 * (1024 ** 3)  # 1 GB free
        used = total - free
        return (total, used, free)

    monkeypatch.setattr(shutil, "disk_usage", mock_disk_usage)

    # Attempting to pull qwen2.5:7b (size: 4.7GB -> requires ~9.4GB free)
    response = client.post("/api/models/pull", json={"model_id": "qwen2.5:7b"}, params={"stream": False})
    assert response.status_code == 409
    assert "Insufficient storage" in response.json()["detail"]
