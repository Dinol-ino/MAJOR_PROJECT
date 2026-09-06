from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.system.hardware_detector import HardwareDetector
from app.system.model_registry import ModelRegistry
from app.system.model_download_manager import ModelDownloadManager
from app.runtime.runtime_manager import RuntimeManager

router = APIRouter(tags=["models"])
registry = ModelRegistry()
download_manager = ModelDownloadManager(registry)

class PullRequest(BaseModel):
    model_id: str

class SwitchRuntimeRequest(BaseModel):
    runtime_name: str

class HardwareOverrideRequest(BaseModel):
    claimed_vram_gb: Optional[float] = None
    claimed_ram_gb: Optional[float] = None

@router.get("/system/hardware")
def get_hardware_info():
    profile = HardwareDetector.detect()
    return asdict(profile)

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

@router.post("/models/pull")
async def pull_model_endpoint(req: PullRequest):
    try:
        task_id = await download_manager.pull(req.model_id)
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

