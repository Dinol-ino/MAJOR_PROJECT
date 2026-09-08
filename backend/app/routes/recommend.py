import logging
from typing import Optional, Dict
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from app.schemas import RecommendRequest, RecommendResponse, RecommendedModel, RecommendOverrideRequest
from app.system.hardware_detector import HardwareDetector, HardwareProfile
from app.system.model_registry import ModelRegistry
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["recommend"])
registry = ModelRegistry()

# In-memory per-session or global override store
_manual_overrides: Dict[str, str] = {}


def _build_recommendation_response(
    hw: HardwareProfile,
    session_id: Optional[str] = None
) -> RecommendResponse:
    recs = registry.recommended_for(hw)
    if not recs:
        recs = [m for m in registry.all_models() if m.tier in ("minimum", "standard")] or registry.all_models()

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

    active_override = None
    if session_id and session_id in _manual_overrides:
        active_override = _manual_overrides[session_id]
    elif "default" in _manual_overrides:
        active_override = _manual_overrides["default"]

    if active_override:
        active_model = active_override
        source = "manually_selected"
        override_applied = True
    else:
        active_model = recommended_list[0].model_id if recommended_list else settings.DEFAULT_MODEL
        source = "recommended"
        override_applied = False

    return RecommendResponse(
        recommended=recommended_list,
        detected_hardware=asdict(hw),
        active_model_id=active_model,
        selection_source=source,
        tie_break_rule="VRAM governs over RAM when discrete GPU is present (Tier 1+ threshold: >=6GB VRAM)",
        override_applied=override_applied
    )


@router.get("/recommend", response_model=RecommendResponse)
async def get_recommendations(session_id: Optional[str] = None):
    """
    Returns hardware-matched model recommendations with deterministic tie-break rules:
    - VRAM governs over RAM when a discrete GPU is detected.
    - Exposes whether the active model is 'recommended' or 'manually_selected'.
    """
    hw = HardwareDetector.detect()
    return _build_recommendation_response(hw, session_id=session_id)


@router.post("/recommend", response_model=RecommendResponse)
async def recommend_endpoint(request: RecommendRequest):
    """
    Evaluates recommendations against physical hardware or explicit simulation parameters.
    """
    hw = HardwareDetector.detect()

    if request.ram_gb is not None:
        hw.ram_available_gb = request.ram_gb
    if request.vram_gb is not None:
        hw.gpu_vram_gb = request.vram_gb
        hw.gpu_available = request.vram_gb > 0

    return _build_recommendation_response(hw)


@router.post("/recommend/override", response_model=RecommendResponse)
async def set_recommendation_override(request: RecommendOverrideRequest):
    """
    Stores a manual model selection override that persists across hardware telemetry polls.
    """
    model_entry = registry.get(request.model_id)
    if not model_entry:
        # Check if matching by ollama_tag or display name
        all_m = registry.all_models()
        matched = next((m for m in all_m if m.model_id == request.model_id or m.ollama_tag == request.model_id), None)
        if not matched:
            raise HTTPException(status_code=404, detail=f"Model '{request.model_id}' not found in registry catalog")
        target_id = matched.model_id
    else:
        target_id = model_entry.model_id

    key = request.session_id or "default"
    _manual_overrides[key] = target_id
    logger.info(f"Set manual model recommendation override: key='{key}' -> model='{target_id}' (Reason: {request.reason})")

    # Emit ModelLifecycleChanged (Module 9 §9.2 Event 5)
    try:
        from app.events import ModelLifecycleChanged, emit_model_lifecycle_changed
        emit_model_lifecycle_changed(ModelLifecycleChanged(
            event_type="override",
            model_name=target_id,
            source="user_override",
            session_id=request.session_id,
            status="active"
        ))
    except Exception as err:
        logger.warning(f"Error emitting ModelLifecycleChanged: {err}")

    hw = HardwareDetector.detect()
    return _build_recommendation_response(hw, session_id=request.session_id)


@router.post("/recommend/reset", response_model=RecommendResponse)
async def reset_recommendation_override(session_id: Optional[str] = None):
    """
    Resets manual model selection back to the hardware-determined recommendation.
    """
    key = session_id or "default"
    _manual_overrides.pop(key, None)
    logger.info(f"Reset manual model recommendation override for key='{key}' back to hardware recommendation")

    # Emit ModelLifecycleChanged (Module 9 §9.2 Event 5)
    try:
        from app.events import ModelLifecycleChanged, emit_model_lifecycle_changed
        emit_model_lifecycle_changed(ModelLifecycleChanged(
            event_type="reset",
            model_name="default_recommendation",
            source="user_reset",
            session_id=session_id,
            status="active"
        ))
    except Exception as err:
        logger.warning(f"Error emitting ModelLifecycleChanged: {err}")

    hw = HardwareDetector.detect()
    return _build_recommendation_response(hw, session_id=session_id)
