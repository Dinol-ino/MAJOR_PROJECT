from dataclasses import asdict
from fastapi import APIRouter
from app.schemas import RecommendRequest, RecommendResponse, RecommendedModel
from app.system.hardware_detector import HardwareDetector, HardwareProfile
from app.system.model_registry import ModelRegistry

router = APIRouter(tags=["recommend"])
registry = ModelRegistry()

@router.post("/recommend", response_model=RecommendResponse)
async def recommend_endpoint(request: RecommendRequest):
    # Detect real hardware or use user overrides
    hw = HardwareDetector.detect()

    if request.ram_gb is not None:
        hw.ram_available_gb = request.ram_gb
    if request.vram_gb is not None:
        hw.gpu_vram_gb = request.vram_gb
        hw.gpu_available = request.vram_gb > 0

    recs = registry.recommended_for(hw)

    recommended_list = [
        RecommendedModel(
            model_id=m.model_id,
            display_name=m.display_name,
            provider=m.provider,
            size_gb=m.size_gb,
            ram_required_gb=m.ram_required_gb,
            context_window=m.context_window,
            tier=m.tier,
            ollama_tag=m.ollama_tag
        )
        for m in recs
    ]

    return RecommendResponse(
        recommended=recommended_list,
        detected_hardware=asdict(hw)
    )
