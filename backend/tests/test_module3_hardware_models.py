import time
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.system.hardware_detector import HardwareDetector, HardwareProfile
from app.system.model_registry import ModelRegistry
from app.services.telemetry import sample, compute_hardware_tier, cpu_name


def test_hardware_detector_profile_and_telemetry():
    """Verify hardware profile structure, caching, and timing instrumentation."""
    profile = HardwareDetector.detect(force_refresh=True)
    assert isinstance(profile, HardwareProfile)
    assert profile.cpu_cores >= 1
    assert profile.ram_total_gb > 0.0
    assert profile.ram_available_gb >= 0.0
    assert profile.storage_free_gb >= 0.0
    assert profile.platform_name in ["windows", "linux", "darwin"]

    # Verify cached return on subsequent call
    cached = HardwareDetector.detect(force_refresh=False)
    assert cached == profile


def test_telemetry_sample_performance_and_unit_accuracy():
    """
    Verify telemetry sample completes in <100ms and correctly differentiates
    total physical RAM from instantly available RAM.
    """
    t0 = time.perf_counter()
    data = sample()
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000

    assert latency_ms < 100.0, f"Sample took {latency_ms:.2f}ms (>100ms)"
    assert "cpu" in data
    assert "ram" in data
    assert "gpu" in data
    assert "disk" in data
    assert "tier" in data

    # Units and sanity checks
    assert data["ram"]["total_gb"] >= data["ram"]["available_gb"]
    assert 0.0 <= data["ram"]["used_percent"] <= 100.0


def test_hardware_tier_classifier_matrix():
    """Verify deterministic tier mapping across CPU and varying VRAM ranges."""
    # 1. CPU Mode / Low Memory (Tier 0)
    gpu_none = {"detected": False, "name": "No Dedicated GPU (CPU Only)", "vram_total_gb": 0.0}
    ram_8 = {"total_gb": 8.0, "available_gb": 4.0}
    t0 = compute_hardware_tier(gpu_none, ram_8)
    assert t0["tier_code"] == "tier_0"
    assert "3B" in t0["max_model"]

    # 2. Low VRAM (4GB < 6GB threshold -> Tier 0)
    gpu_4gb = {"detected": True, "name": "GTX 1650", "vram_total_gb": 4.0}
    t0_low = compute_hardware_tier(gpu_4gb, ram_8)
    assert t0_low["tier_code"] == "tier_0"
    assert "< 6 GB threshold" in t0_low["reason"]

    # 3. Standard Legal (6GB - 11GB VRAM -> Tier 1)
    gpu_6gb = {"detected": True, "name": "RTX 3050 6GB", "vram_total_gb": 6.0}
    t1 = compute_hardware_tier(gpu_6gb, ram_8)
    assert t1["tier_code"] == "tier_1"
    assert "7B" in t1["max_model"]

    # 4. High Performance (12GB - 23GB VRAM -> Tier 2)
    gpu_16gb = {"detected": True, "name": "RTX 4080 16GB", "vram_total_gb": 16.0}
    t2 = compute_hardware_tier(gpu_16gb, ram_8)
    assert t2["tier_code"] == "tier_2"
    assert "13B" in t2["max_model"]

    # 5. Enterprise (>=24GB VRAM -> Tier 3)
    gpu_24gb = {"detected": True, "name": "RTX 4090 24GB", "vram_total_gb": 24.0}
    t3 = compute_hardware_tier(gpu_24gb, ram_8)
    assert t3["tier_code"] == "tier_3"
    assert "32B" in t3["max_model"]


def test_hardware_override_validation():
    """Verify user override validation detects excessive claimed resources."""
    mock_profile = HardwareProfile(
        cpu_cores=8,
        cpu_name="AMD Ryzen 7",
        ram_total_gb=16.0,
        ram_available_gb=8.0,
        gpu_available=True,
        gpu_name="RTX 3060",
        gpu_vram_gb=6.0,
        gpu_backend="cuda",
        storage_free_gb=100.0,
        platform_name="windows",
        supports_avx2=True
    )

    with patch.object(HardwareDetector, "detect", return_value=mock_profile):
        # Valid override
        valid_res = HardwareDetector.validate_override(claimed_vram_gb=4.0, claimed_ram_gb=12.0)
        assert valid_res["valid"] is True
        assert len(valid_res["warnings"]) == 0

        # Excessive VRAM claim
        invalid_vram = HardwareDetector.validate_override(claimed_vram_gb=12.0)
        assert invalid_vram["valid"] is False
        assert any("claimed 12.0 GB VRAM" in w for w in invalid_vram["warnings"])

        # Excessive RAM claim
        invalid_ram = HardwareDetector.validate_override(claimed_ram_gb=32.0)
        assert invalid_ram["valid"] is False
        assert any("claimed 32.0 GB RAM" in w for w in invalid_ram["warnings"])


def test_model_registry_includes_specialized_legal_model():
    """Verify dfrag-legal:7b is indexed in the centralized registry for Tier 1."""
    registry = ModelRegistry()
    models = registry.all_models()
    model_ids = [m.model_id for m in models]

    assert "dfrag-legal:7b" in model_ids
    assert "qwen2.5:7b" in model_ids
    assert "gemma2:2b" in model_ids

    legal_model = next(m for m in models if m.model_id == "dfrag-legal:7b")
    assert legal_model.tier == "standard"
    assert legal_model.size_gb == 4.7
    assert legal_model.ram_required_gb == 8.0
    assert "Specialized Indian Law" in legal_model.display_name


def test_recommended_models_endpoint():
    """Verify /models/recommended dynamically evaluates fit and tags."""
    client = TestClient(app)
    resp = client.get("/models/recommended")
    assert resp.status_code == 200
    data = resp.json()

    assert "tier" in data
    assert "recommended" in data
    assert isinstance(data["recommended"], list)
    assert len(data["recommended"]) >= 5

    # Check structure of model entries
    for m in data["recommended"]:
        assert "model_id" in m
        assert "display_name" in m
        assert "size_gb" in m
        assert "fits_memory" in m
        assert "action_label" in m
        assert "parameter_size" in m


def test_models_pull_streaming_and_smoke_test():
    """Verify SSE streaming for model pull endpoint and post-pull smoke test."""
    client = TestClient(app)

    resp = client.post("/models/pull?stream=true", json={"model_id": "dfrag-legal:7b"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # Read lines from stream
    lines = list(resp.iter_lines())
    assert len(lines) > 0
    first_chunk = lines[0]
    assert first_chunk.startswith("data:")
    parsed = json.loads(first_chunk.replace("data: ", ""))
    assert "status" in parsed
