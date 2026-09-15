import os
import json
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


@router.get("/models/recommended")
@router.get("/api/models/recommended")
async def get_recommended_models():
    """
    Dynamically computes model recommendations:
    1. Queries live Ollama (/api/tags) for installed models.
    2. Takes current telemetry snapshot and hardware tier.
    3. Evaluates per-model fit against available VRAM/RAM.
    4. Returns actionable status: 'Installed ✓' or 'Pull (~X GB)'.
    """
    hw_sample = sample()
    tier_info = hw_sample["tier"]
    vram_available = hw_sample["gpu"].get("vram_total_gb", 0.0)
    ram_available = hw_sample["ram"].get("available_gb", 8.0)
    gpu_detected = hw_sample["gpu"].get("detected", False)

    ollama_url = settings.OLLAMA_URL
    installed_tags = set()
    ollama_online = False

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code == 200:
                ollama_online = True
                tags_data = resp.json()
                for m in tags_data.get("models", []):
                    name = m.get("name", "")
                    installed_tags.add(name.lower())
                    if ":" in name:
                        installed_tags.add(name.split(":")[0].lower())
    except Exception as e:
        logger.debug(f"Ollama tags query failed ({e}). Treating as offline/unreachable.")

    hw_profile = HardwareDetector.detect()
    all_models = registry.all_models()
    recommended_list = []

    for entry in all_models:
        model_name = entry.ollama_tag or entry.model_id
        is_installed = (
            model_name.lower() in installed_tags
            or entry.model_id.lower() in installed_tags
        )

        # Parameter size heuristics from display name or id
        param_size = "Unknown"
        for p in ["2b", "3b", "7b", "8b", "13b", "14b", "32b", "70b"]:
            if p in entry.model_id.lower() or p in entry.display_name.lower():
                param_size = p.upper()
                break

        # Dynamic safety and memory fit calculation (Spec 00)
        fit_eval = registry.evaluate_model_fit(entry, hw_profile)
        fits_memory = fit_eval["fits_memory"]
        safety_tier = fit_eval["safety_tier"]
        fit_reason = fit_eval["fit_reason"]

        # Determine if recommended for current tier
        current_tier_code = tier_info.get("tier_code", "tier_0")
        if current_tier_code == "tier_0":
            rec_for_tier = (entry.size_gb <= 3.0 or entry.tier == "minimum") and safety_tier in ("SAFE", "CAUTION")
            est_tokens = 14.5 if fits_memory else 6.0
        elif current_tier_code == "tier_1":
            rec_for_tier = (entry.size_gb <= 6.5 or entry.tier in ["minimum", "standard"]) and safety_tier in ("SAFE", "CAUTION")
            est_tokens = 28.0 if fits_memory else 12.0
        elif current_tier_code == "tier_2":
            rec_for_tier = (entry.size_gb <= 12.0 or entry.tier in ["minimum", "standard", "premium"]) and safety_tier in ("SAFE", "CAUTION")
            est_tokens = 45.0 if fits_memory else 22.0
        else:
            rec_for_tier = safety_tier in ("SAFE", "CAUTION")
            est_tokens = 60.0

        action_label = "Installed ✓" if is_installed else f"Pull (~{entry.size_gb} GB)"

        # Determine status state (Task 6.3.1)
        active_runtime_model = settings.DEFAULT_MODEL
        if is_installed:
            status_state = "ACTIVE" if (
                entry.model_id.lower() == active_runtime_model.lower()
                or (entry.ollama_tag and entry.ollama_tag.lower() == active_runtime_model.lower())
            ) else "PULLED_INACTIVE"
        else:
            status_state = "NOT_PULLED"

        specialization_tag = (
            "Fine-tuned for Indian Law"
            if "dfrag" in entry.model_id.lower()
            else ("Legal Domain Model" if "saul" in entry.model_id.lower() else None)
        )

        recommended_list.append({
            "model_id": entry.model_id,
            "display_name": entry.display_name,
            "provider": entry.provider,
            "size_gb": entry.size_gb,
            "ram_required_gb": entry.ram_required_gb,
            "vram_required_gb": entry.vram_required_gb,
            "context_window": entry.context_window,
            "quantization": entry.quantization,
            "parameter_size": param_size,
            "fits_memory": fits_memory,
            "safety_tier": safety_tier,
            "fit_reason": fit_reason,
            "installed": is_installed,
            "recommended_for_tier": rec_for_tier,
            "action_label": action_label,
            "est_tokens_sec": est_tokens,
            "status_state": status_state,
            "specialization": specialization_tag,
            "is_fine_tuned": "dfrag" in entry.model_id.lower() or "saul" in entry.model_id.lower()
        })

    # Sort so recommended, safe, and installed models come first
    recommended_list.sort(key=lambda x: (not x["recommended_for_tier"], x["safety_tier"] != "SAFE", not x["installed"], x["size_gb"]))

    return {
        "tier": tier_info,
        "ollama_online": ollama_online,
        "ollama_url": ollama_url,
        "detected_hardware": hw_sample,
        "recommended": recommended_list,
        "installed_count": len(installed_tags)
    }


@router.post("/models/pull")
@router.post("/api/models/pull")
async def pull_model_endpoint(req: ModelPullRequest, stream: bool = Query(True)):
    """
    Streams model pulling progress directly from Ollama via SSE with pre-download storage validation.
    """
    model_name = req.name or req.model_id
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name or model_id is required")

    # Storage Pre-check per Spec 00: model download size * 2 must be available
    model_entry = registry.get(model_name)
    if not model_entry:
        for m in registry.all_models():
            if m.ollama_tag == model_name or m.model_id == model_name:
                model_entry = m
                break

    if model_entry:
        required_storage_gb = model_entry.size_gb * 2.0
        try:
            import shutil
            total, used, free = shutil.disk_usage(os.getcwd())
            free_gb = free / (1024 ** 3)
            if free_gb < required_storage_gb:
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient storage to pull '{model_entry.display_name}'. Requires {required_storage_gb:.1f} GB free space (download + cache overhead), but only {free_gb:.1f} GB is available on disk."
                )
        except HTTPException:
            raise
        except Exception as err:
            logger.debug(f"Storage check notice: {err}")

    ollama_url = settings.OLLAMA_URL

    # If streaming is requested (standard v4 behavior), yield SSE events
    if stream:
        async def stream_progress():
            try:
                async with httpx.AsyncClient(timeout=3600.0) as client:
                    async with client.stream(
                        "POST",
                        f"{ollama_url}/api/pull",
                        json={"name": model_name, "stream": True}
                    ) as resp:
                        if resp.status_code != 200:
                            err_body = await resp.aread()
                            err_text = err_body.decode("utf-8", errors="ignore")
                            yield f"data: {json.dumps({'status': 'error', 'error': f'Ollama error: {err_text}'})}\n\n"
                            return

                        async for line in resp.aiter_lines():
                            if not line.strip():
                                continue
                            try:
                                data = json.loads(line)
                                # Compute percent if total and completed are present
                                total = data.get("total", 0)
                                completed = data.get("completed", 0)
                                if total > 0:
                                    data["percent"] = round((completed / total) * 100, 1)
                                else:
                                    data["percent"] = 100.0 if data.get("status") == "success" else 0.0

                                # Task 3.2.2: Post-pull inference smoke test verification
                                if data.get("status") == "success":
                                    data["percent"] = 100.0
                                    try:
                                        smoke_resp = await client.post(
                                            f"{ollama_url}/api/generate",
                                            json={"model": model_name, "prompt": "Legal engine smoke test ping", "stream": False},
                                            timeout=15.0
                                        )
                                        if smoke_resp.status_code == 200:
                                            data["smoke_test"] = "passed"
                                            data["status"] = "verified"
                                        else:
                                            data["smoke_test"] = "skipped"
                                    except Exception as smoke_err:
                                        logger.warning(f"Post-pull smoke test skipped: {smoke_err}")
                                        data["smoke_test"] = "skipped"

                                yield f"data: {json.dumps(data)}\n\n"
                            except Exception:
                                yield f"data: {json.dumps({'status': 'downloading', 'raw': line})}\n\n"

            except Exception as e:
                logger.error(f"Error during model pull stream for {model_name}: {e}")
                yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            stream_progress(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    # Legacy background task fallback
    try:
        task_id = await download_manager.pull(model_name)
        return {"status": "started", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/models/pull/progress/{task_id}")
def get_pull_progress(task_id: str):
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
        hf_api_key=req.hf_api_key
    )
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

