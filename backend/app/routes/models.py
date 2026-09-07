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
from app.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])
registry = ModelRegistry()
download_manager = ModelDownloadManager(registry)


class ModelPullRequest(BaseModel):
    name: Optional[str] = None
    model_id: Optional[str] = None


class SwitchRuntimeRequest(BaseModel):
    runtime_name: str


class HardwareOverrideRequest(BaseModel):
    claimed_vram_gb: Optional[float] = None
    claimed_ram_gb: Optional[float] = None


@router.get("/system/hardware")
def get_hardware_info():
    profile = HardwareDetector.detect()
    tier_info = HardwareDetector.get_auto_selected_tier(profile)
    res = asdict(profile)
    res["hardware_tier"] = tier_info.get("tier_name", "minimum")
    res["tier_name"] = tier_info.get("tier_name", "minimum")
    return res


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

    ollama_url = getattr(settings, "ollama_url", "http://127.0.0.1:11434")
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

        # Compute memory fit
        if gpu_detected and entry.vram_required_gb:
            fits_memory = vram_available >= entry.vram_required_gb
        else:
            fits_memory = ram_available >= (entry.ram_required_gb * 0.8)

        # Determine if recommended for current tier
        current_tier_code = tier_info.get("tier_code", "tier_0")
        if current_tier_code == "tier_0":
            rec_for_tier = entry.size_gb <= 3.0 or entry.tier == "minimum"
            est_tokens = 14.5 if fits_memory else 6.0
        elif current_tier_code == "tier_1":
            rec_for_tier = entry.size_gb <= 5.5 or entry.tier in ["minimum", "standard"]
            est_tokens = 28.0 if fits_memory else 12.0
        elif current_tier_code == "tier_2":
            rec_for_tier = entry.size_gb <= 12.0 or entry.tier in ["minimum", "standard", "premium"]
            est_tokens = 45.0 if fits_memory else 22.0
        else:
            rec_for_tier = True
            est_tokens = 60.0

        action_label = "Installed ✓" if is_installed else f"Pull (~{entry.size_gb} GB)"

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
            "installed": is_installed,
            "recommended_for_tier": rec_for_tier,
            "action_label": action_label,
            "est_tokens_sec": est_tokens
        })

    # Sort so recommended and installed models come first
    recommended_list.sort(key=lambda x: (not x["recommended_for_tier"], not x["installed"], x["size_gb"]))

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
    Streams model pulling progress directly from Ollama via SSE.
    """
    model_name = req.name or req.model_id
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name or model_id is required")

    ollama_url = getattr(settings, "ollama_url", "http://127.0.0.1:11434")

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
    success = RuntimeManager.switch(req.runtime_name)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to switch runtime to {req.runtime_name}")
    return {"status": "ok", "active_runtime": req.runtime_name}
