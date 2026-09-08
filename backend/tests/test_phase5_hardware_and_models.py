import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.telemetry import (
    cpu_name,
    sample,
    compute_hardware_tier,
    _gpu_sample
)


def test_cpu_name_resolution():
    name = cpu_name()
    assert isinstance(name, str)
    assert len(name.strip()) > 0
    assert "\n" not in name


def test_telemetry_sample_speed_and_schema():
    # Performance contract: sample() must complete in <50ms (or under 100ms on heavily loaded CI)
    t0 = time.perf_counter()
    data = sample()
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000

    assert latency_ms < 100.0, f"Sample took too long: {latency_ms:.2f}ms"

    # Verify CPU section
    assert "cpu" in data
    assert "name" in data["cpu"]
    assert "load_percent" in data["cpu"]
    assert data["cpu"]["cores_physical"] >= 1
    assert data["cpu"]["cores_logical"] >= 1
    assert len(data["cpu"]["arch"]) > 0

    # Verify RAM section
    assert "ram" in data
    assert data["ram"]["total_gb"] > 0.0
    assert data["ram"]["available_gb"] >= 0.0
    assert 0 <= data["ram"]["used_percent"] <= 100

    # Verify GPU section
    assert "gpu" in data
    assert "detected" in data["gpu"]
    assert "name" in data["gpu"]

    # Verify Disk & Tier
    assert "disk" in data
    assert data["disk"]["free_gb"] >= 0.0
    assert "tier" in data
    assert "tier_code" in data["tier"]
    assert "tier_label" in data["tier"]
    assert "reason" in data["tier"]
    assert "max_model" in data["tier"]
    assert data["ts"] > 0


def test_hardware_tier_deterministic_mapping():
    # Scenario A: Tier 0 (No GPU, 8GB RAM)
    gpu_none = {"detected": False, "name": "No Dedicated GPU (CPU Only)", "vram_total_gb": 0.0}
    ram_8 = {"total_gb": 8.0, "available_gb": 4.0}
    t0_res = compute_hardware_tier(gpu_none, ram_8)
    assert t0_res["tier_code"] == "tier_0"
    assert "No CUDA GPU detected" in t0_res["reason"]
    assert "3B" in t0_res["max_model"]

    # Scenario B: Tier 0 (Small GPU, 4GB VRAM < 6GB threshold)
    gpu_4gb = {"detected": True, "name": "GTX 1650", "vram_total_gb": 4.0}
    t0_small = compute_hardware_tier(gpu_4gb, ram_8)
    assert t0_small["tier_code"] == "tier_0"
    assert "< 6 GB threshold" in t0_small["reason"]

    # Scenario C: Tier 1 (NVIDIA RTX 3060, 8GB VRAM)
    gpu_8gb = {"detected": True, "name": "NVIDIA GeForce RTX 3060", "vram_total_gb": 8.0}
    t1_res = compute_hardware_tier(gpu_8gb, ram_8)
    assert t1_res["tier_code"] == "tier_1"
    assert "7B" in t1_res["max_model"]

    # Scenario D: Tier 2 (NVIDIA RTX 4080, 16GB VRAM)
    gpu_16gb = {"detected": True, "name": "NVIDIA GeForce RTX 4080", "vram_total_gb": 16.0}
    t2_res = compute_hardware_tier(gpu_16gb, ram_8)
    assert t2_res["tier_code"] == "tier_2"
    assert "13B" in t2_res["max_model"]

    # Scenario E: Tier 3 (NVIDIA RTX 4090, 24GB VRAM)
    gpu_24gb = {"detected": True, "name": "NVIDIA GeForce RTX 4090", "vram_total_gb": 24.0}
    t3_res = compute_hardware_tier(gpu_24gb, ram_8)
    assert t3_res["tier_code"] == "tier_3"
    assert "32B" in t3_res["max_model"]


def test_telemetry_endpoints():
    client = TestClient(app)

    # 1. Test /telemetry/sample
    resp = client.get("/telemetry/sample")
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu" in data
    assert "tier" in data

    # 2. Test /system/hardware (legacy backward compat)
    resp_sys = client.get("/system/hardware")
    assert resp_sys.status_code == 200
    sys_data = resp_sys.json()
    assert "cpu_name" in sys_data
    assert "hardware_tier" in sys_data


def test_models_recommended_endpoint():
    client = TestClient(app)

    resp = client.get("/models/recommended")
    assert resp.status_code == 200
    data = resp.json()

    assert "tier" in data
    assert "recommended" in data
    assert isinstance(data["recommended"], list)
    assert len(data["recommended"]) > 0

    first_model = data["recommended"][0]
    assert "model_id" in first_model
    assert "display_name" in first_model
    assert "fits_memory" in first_model
    assert "installed" in first_model
    assert "action_label" in first_model
    assert "parameter_size" in first_model


def test_models_pull_endpoint_streaming():
    client = TestClient(app)

    resp = client.post("/models/pull?stream=true", json={"name": "gemma2:2b"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # Read first chunk
    content = next(resp.iter_lines())
    assert isinstance(content, str)
