import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.provisioning_service import ModelProvisioningService, ProvisioningJob, get_provisioning_service
from app.system.hardware_detector import HardwareProfile, HardwareDetector
from app.system.model_registry import ModelRegistry, ModelEntry

client = TestClient(app)


def test_provision_service_initialization(tmp_path):
    db_file = str(tmp_path / "test_provisioning.db")
    service = ModelProvisioningService(db_path=db_file)
    assert os.path.exists(db_file)
    assert service.list_jobs() == []


def test_hardware_recommendation_for_8gb_pc():
    profile = HardwareProfile(
        cpu_cores=6,
        cpu_name="AMD Ryzen 5 5600H",
        ram_total_gb=8.0,
        ram_available_gb=5.2,
        gpu_available=False,
        gpu_name=None,
        gpu_vram_gb=None,
        gpu_backend=None,
        storage_free_gb=120.0,
        platform_name="windows",
        supports_avx2=True
    )
    registry = ModelRegistry()
    recommended = registry.recommended_for(profile, safe_only=True)
    assert len(recommended) > 0
    # Top recommended for 8GB RAM must be lightweight 2B-3B
    top = recommended[0]
    assert top.ram_required_gb <= 5.2
    assert top.size_gb <= 3.0


def test_storage_check_refusal(tmp_path):
    db_file = str(tmp_path / "test_storage.db")
    service = ModelProvisioningService(db_path=db_file)

    large_entry = ModelEntry(
        model_id="huge:70b",
        display_name="Huge 70B",
        provider="ollama",
        size_gb=40.0,
        ram_required_gb=64.0,
        context_window=8192,
        quantization="q4_k_m",
        tier="premium"
    )

    with patch("shutil.disk_usage", return_value=MagicMock(free=10 * (1024 ** 3))):
        ok, msg = service._check_storage(large_entry)
        assert ok is False
        assert "Insufficient storage" in msg


def test_idempotency_guard(tmp_path):
    import asyncio
    db_file = str(tmp_path / "test_idempotent.db")
    service = ModelProvisioningService(db_path=db_file)

    # Put a job in running/downloading state
    active_job = ProvisioningJob(job_id="job-active-123", model_id="qwen2.5:3b", status="downloading", percent=45.0)
    service._persist_job(active_job)

    # Calling provision on same model must return the active job, not spawn a new one
    res = asyncio.run(service.provision(model_id="qwen2.5:3b", auto=False))
    assert res["job_id"] == "job-active-123"
    assert res.get("already_active") is True
    assert res["status"] == "downloading"


def test_job_cancellation(tmp_path):
    db_file = str(tmp_path / "test_cancel.db")
    service = ModelProvisioningService(db_path=db_file)

    job = ProvisioningJob(job_id="job-cancel-456", model_id="qwen2.5:3b", status="downloading", percent=20.0)
    service._persist_job(job)

    cancelled = service.cancel_job("job-cancel-456")
    assert cancelled is True

    updated = service.get_job("job-cancel-456")
    assert updated["status"] == "cancelled"
    assert "Cancelled by user" in updated["message"]


def test_restart_job_recovery(tmp_path):
    db_file = str(tmp_path / "test_recovery.db")
    # First instance creates an uncompleted job
    service1 = ModelProvisioningService(db_path=db_file)
    interrupted_job = ProvisioningJob(job_id="job-interrupted-789", model_id="qwen2.5:3b", status="downloading", percent=60.0)
    service1._persist_job(interrupted_job)

    # Second instance simulates backend server rebooting
    service2 = ModelProvisioningService(db_path=db_file)
    recovered = service2.get_job("job-interrupted-789")
    assert recovered is not None
    assert recovered["status"] == "failed"
    assert "Interrupted by system restart" in recovered["message"]


def test_provisioning_api_endpoints():
    # 1. Start provisioning. Preflight is stubbed so the test does not depend on the RAM/disk of
    #    whichever machine runs it (a small CI runner would legitimately refuse the download);
    #    the refusal itself is covered by test_preflight_refuses_a_model_that_does_not_fit.
    with patch("app.services.provisioning_service.ModelProvisioningService.preflight",
               return_value={"ok": True, "message": "ok", "fit": {}}), \
            patch("app.services.provisioning_service.ModelProvisioningService._run_provisioning", new_callable=AsyncMock):
        resp = client.post("/api/models/provision", json={"model_id": "qwen2.5:3b", "auto": True})
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        job_id = data["job_id"]

        # 2. Get active job
        active_resp = client.get("/api/models/provision/active")
        assert active_resp.status_code == 200
        active_data = active_resp.json()
        assert active_data.get("job_id") == job_id or active_data.get("status") is not None

        # 3. Poll specific job
        poll_resp = client.get(f"/api/models/provision/{job_id}")
        assert poll_resp.status_code == 200
        assert poll_resp.json()["job_id"] == job_id

        # 4. Cancel job
        cancel_resp = client.post(f"/api/models/provision/{job_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"


def _hw(ram_avail_gb, free_gb=200.0):
    return HardwareProfile(cpu_cores=8, cpu_name="test-cpu", ram_total_gb=ram_avail_gb + 2,
                           ram_available_gb=ram_avail_gb, gpu_available=False, gpu_name=None,
                           gpu_vram_gb=None, gpu_backend=None, storage_free_gb=free_gb,
                           platform_name="linux", supports_avx2=True)


def test_preflight_refuses_a_model_that_does_not_fit(tmp_path):
    svc = ModelProvisioningService(db_path=str(tmp_path / "p.db"))
    with patch.object(svc.hw_detector, "detect", return_value=_hw(1.0)):
        res = svc.preflight("qwen2.5:3b")
    assert res["ok"] is False and "too large" in res["message"]


def test_preflight_accepts_a_model_that_fits_when_storage_is_sufficient(tmp_path):
    svc = ModelProvisioningService(db_path=str(tmp_path / "p.db"))
    with patch.object(svc.hw_detector, "detect", return_value=_hw(32.0)), \
            patch.object(svc, "_check_storage", return_value=(True, "ok")):
        res = svc.preflight("qwen2.5:3b")
    assert res["ok"] is True


def test_preflight_refuses_when_disk_is_too_small(tmp_path):
    svc = ModelProvisioningService(db_path=str(tmp_path / "p.db"))
    with patch.object(svc.hw_detector, "detect", return_value=_hw(32.0)), \
            patch("app.services.telemetry.models_disk_path", return_value=str(tmp_path)), \
            patch("shutil.disk_usage", return_value=(100 * 1024**3, 99 * 1024**3, 1 * 1024**3)):
        res = svc.preflight("qwen2.5:3b")
    assert res["ok"] is False and "Insufficient storage" in res["message"]


def test_generation_requests_keep_the_model_resident():
    """Every generate call must carry keep_alive, or Ollama unloads the model after 5 idle minutes."""
    import asyncio
    import httpx
    from app.config import settings
    from app.model.ollama_client import OllamaClient

    seen = {}

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"response": "ok", "eval_count": 1, "eval_duration": 1_000_000}

    async def fake_post(self, url, json=None, **kw):
        seen.update(json or {})
        return _Resp()

    with patch.object(httpx.AsyncClient, "post", fake_post):
        client_ = OllamaClient()
        asyncio.run(client_.generate("hi", model="qwen2.5:3b"))
    assert seen.get("keep_alive") == settings.model.keep_alive and seen["keep_alive"]
