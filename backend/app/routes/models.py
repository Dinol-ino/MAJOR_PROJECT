import os
import json
import asyncio
import httpx
import logging
from dataclasses import asdict
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.system.hardware_detector import HardwareDetector
from app.system.model_registry import ModelRegistry
from app.system.model_download_manager import ModelDownloadManager
from app.runtime.runtime_manager import RuntimeManager
from app.services.telemetry import sample
from app.services.provisioning_service import get_provisioning_service
from app.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])
from .hardware import router as hardware_router
router.include_router(hardware_router)

registry = ModelRegistry()
download_manager = ModelDownloadManager(registry)


class ModelPullRequest(BaseModel):
    name: Optional[str] = None
    model_id: Optional[str] = None


class SwitchRuntimeRequest(BaseModel):
    runtime_name: str


class ProvisionModelRequest(BaseModel):
    model_id: Optional[str] = None
    auto: bool = True
    hf_api_key: Optional[str] = None
    activate: bool = False


class HardwareOverrideRequest(BaseModel):
    claimed_vram_gb: Optional[float] = None
    claimed_ram_gb: Optional[float] = None


@router.get("/system/hardware")
def get_hardware_info():
    from app.routes.hardware import get_system_hardware
    return get_system_hardware()


@router.get("/models/auto-select")
def get_auto_selected_model_tier():
    profile = HardwareDetector.detect()
    tier_info = HardwareDetector.get_auto_selected_tier(profile)
    return {
        "hardware": asdict(profile),
        "tier_selection": tier_info
    }


@router.post("/models/override")
def validate_hardware_override(req: HardwareOverrideRequest):
    res = HardwareDetector.validate_override(
        claimed_vram_gb=req.claimed_vram_gb,
        claimed_ram_gb=req.claimed_ram_gb
    )
    return res


@router.get("/models/catalog")
def get_model_catalog():
    models = registry.all_models()
    return [asdict(m) for m in models]


def _registry_entry_for(tag: str):
    from app.runtime.model_state import normalize_tag
    entry = registry.get(tag)
    if entry:
        return entry
    for m in registry.all_models():
        if normalize_tag(m.ollama_tag) == normalize_tag(tag) or normalize_tag(m.model_id) == normalize_tag(tag):
            return m
    return None


@router.get("/models/installed")
async def get_installed_models():
    """Models actually present in the local runtime (source for the top model selector)."""
    from app.runtime.model_state import model_state
    tags = await model_state.list_installed()
    active = await model_state.get_active()
    hw = await asyncio.to_thread(HardwareDetector.detect)
    models = []
    for m in tags["models"]:
        entry = _registry_entry_for(m["name"] or "")
        fit = registry.evaluate_model_fit(entry, hw) if entry else None
        models.append({
            **m,
            "display_name": entry.display_name if entry else m["name"],
            "context_window": entry.context_window if entry else None,
            "in_registry": entry is not None,
            "safety_tier": fit["safety_tier"] if fit else "UNKNOWN",
            "fit_reason": fit["fit_reason"] if fit else "No registry metadata for this model.",
            "is_active": bool(active["model"]) and m["name"] == active["model"],
        })
    return {
        "runtime_online": tags["online"],
        "runtime_error": tags.get("error"),
        "checked_at": tags["checked_at"],
        "active_model": active["model"] if active["available"] else None,
        "models": models,
    }


@router.get("/models/active")
async def get_active_model():
    from app.runtime.model_state import model_state
    return await model_state.get_active()


class ActivateModelRequest(BaseModel):
    model: str


@router.post("/models/activate")
async def activate_model(req: ActivateModelRequest):
    """Validate -> warm -> health check -> persist. The conversation is unaffected by a switch."""
    from app.runtime.model_state import model_state, ModelNotAvailable
    try:
        return await model_state.activate(req.model)
    except ModelNotAvailable as exc:
        status = 503 if exc.code == "runtime_offline" else 409
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})


@router.get("/models/recommended")
@router.get("/api/models/recommended")
async def get_recommended_models():
    """
    Hardware-aware recommendations computed from the registry + detected resources + live runtime state.
    Probes run off the event loop; nothing here is estimated or hardcoded per model.
    """
    from app.runtime.model_state import model_state, normalize_tag
    hw_sample = await asyncio.to_thread(sample)
    hw_profile = await asyncio.to_thread(HardwareDetector.detect)
    tags = await model_state.list_installed()
    active = await model_state.get_active()
    installed = {normalize_tag(m["name"]) for m in tags["models"]}
    tier_info = hw_sample["tier"]

    recommended_list = []
    for entry in registry.all_models():
        tag = entry.ollama_tag or entry.model_id
        is_installed = normalize_tag(tag) in installed or normalize_tag(entry.model_id) in installed
        fit_eval = registry.evaluate_model_fit(entry, hw_profile)
        safety_tier = fit_eval["safety_tier"]
        is_active = bool(active["model"]) and normalize_tag(active["model"]) in (normalize_tag(tag), normalize_tag(entry.model_id))
        status_state = "ACTIVE" if (is_installed and is_active) else ("PULLED_INACTIVE" if is_installed else "NOT_PULLED")
        recommended_list.append({
            "model_id": entry.model_id,
            "ollama_tag": tag,
            "display_name": entry.display_name,
            "provider": entry.provider,
            "size_gb": entry.size_gb,
            "ram_required_gb": entry.ram_required_gb,
            "vram_required_gb": entry.vram_required_gb,
            "context_window": entry.context_window,
            "quantization": entry.quantization,
            "parameter_size": entry.parameter_size,
            "license": entry.license,
            "source": entry.source,
            "fits_memory": fit_eval["fits_memory"],
            "fits_storage": fit_eval["fits_storage"],
            "storage_required_gb": fit_eval.get("storage_required_gb"),
            "safety_tier": safety_tier,
            "fit_reason": fit_eval["fit_reason"],
            "installed": is_installed,
            # Recommended = fits this machine's memory AND storage policy; the smallest such model sorts first.
            "recommended_for_tier": safety_tier == "SAFE" and fit_eval["fits_storage"],
            "downloadable": (not is_installed) and safety_tier != "UNSUPPORTED" and fit_eval["fits_storage"],
            "action_label": "Installed" if is_installed else f"Download (~{entry.size_gb} GB)",
            "status_state": status_state,
        })

    recommended_list.sort(key=lambda x: (not x["recommended_for_tier"], x["safety_tier"] != "SAFE", not x["installed"], x["size_gb"]))

    return {
        "tier": tier_info,
        "ollama_online": tags["online"],
        "detected_hardware": hw_sample,
        "active_model": active["model"] if active["available"] else None,
        "recommended": recommended_list,
        "installed_count": len(tags["models"]),
    }


@router.post("/models/pull")
@router.post("/api/models/pull")
async def pull_model_endpoint(req: ModelPullRequest, stream: bool = Query(True)):
    """
    Backwards-compatible entry point. Delegates to the single idempotent provisioning pipeline
    (storage/RAM checks, bounded retries, verification, one download at a time).
    """
    model_name = req.name or req.model_id
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name or model_id is required")
    service = get_provisioning_service()
    started = await service.provision(model_id=model_name, auto=False)
    if not started.get("job_id"):
        raise HTTPException(status_code=409, detail=started.get("message", "Provisioning rejected"))
    if not stream:
        return {"status": "started", "task_id": started["job_id"], "job_id": started["job_id"]}
    return StreamingResponse(
        service.stream_job_progress(started["job_id"]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/models/pull/progress/{task_id}")
def get_pull_progress(task_id: str):
    job = get_provisioning_service().get_job(task_id)
    if job:
        return job
    progress = download_manager.get_progress(task_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Task ID not found")
    return progress


@router.get("/runtime/health")
async def get_runtime_health():
    return await RuntimeManager.health()


@router.post("/runtime/switch")
def switch_runtime(req: SwitchRuntimeRequest):
    if req.runtime_name.lower() == "mock":
        in_test = bool(os.environ.get("PYTEST_CURRENT_TEST")) or os.environ.get("TESTING") == "1"
        if not in_test:
            raise HTTPException(
                status_code=403,
                detail="MockRuntime is restricted to automated test/CI environments and cannot be selected in live runtime."
            )
    success = RuntimeManager.switch(req.runtime_name)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to switch runtime to {req.runtime_name}")
    return {"status": "ok", "active_runtime": req.runtime_name}


# ==============================================================================
# One-Click Local Model Provisioning Endpoints
# ==============================================================================

@router.post("/models/provision")
@router.post("/api/models/provision")
async def start_provisioning(req: ProvisionModelRequest):
    """
    Triggers idempotent one-click local model provisioning:
    - Verifies hardware profile & memory headroom.
    - Validates local disk storage availability.
    - Connects to Ollama runtime.
    - Downloads/pulls model with live progress streaming.
    - Verifies integrity & executes post-pull ping health check.
    - Returns job ID for SSE progress tracking.
    """
    service = get_provisioning_service()
    res = await service.provision(
        model_id=req.model_id,
        auto=req.auto,
        hf_api_key=req.hf_api_key,
        activate=req.activate,
    )
    if res.get("status") == "rejected":
        raise HTTPException(status_code=409, detail=res.get("message"))
    return res


@router.get("/models/provision/active")
@router.get("/api/models/provision/active")
def get_active_provisioning():
    """Gets the active or latest provisioning job status."""
    service = get_provisioning_service()
    job = service.get_active_job()
    return job or {"status": "none", "message": "No active provisioning job"}


@router.get("/models/provision/{job_id}")
@router.get("/api/models/provision/{job_id}")
def get_provisioning_status(job_id: str):
    """Polls a specific provisioning job's current status and metrics."""
    service = get_provisioning_service()
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Provisioning job not found")
    return job


@router.get("/models/provision/{job_id}/stream")
@router.get("/api/models/provision/{job_id}/stream")
async def stream_provisioning_progress(job_id: str):
    """Server-Sent Events stream for live model provisioning progress."""
    service = get_provisioning_service()
    return StreamingResponse(
        service.stream_job_progress(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/models/provision/{job_id}/cancel")
@router.post("/api/models/provision/{job_id}/cancel")
def cancel_provisioning(job_id: str):
    """Safely cancels an active provisioning download."""
    service = get_provisioning_service()
    cancelled = service.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled (already finished or not found)")
    return {"status": "cancelled", "job_id": job_id}


@router.get("/models/hf/search")
@router.get("/api/models/hf/search")
async def search_hf_models(query: str = Query("legal gguf", min_length=2)):
    """Queries Hugging Face model hub for GGUF legal models using the configured HF token."""
    service = get_provisioning_service()
    return await service.search_hf_models(query=query)

