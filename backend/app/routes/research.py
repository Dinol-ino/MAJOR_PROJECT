import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.orchestrator.cancellation import cancellation_manager
from app.orchestrator.state_machine import research_orchestrator, OrchestrationResult
from app.orchestrator.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research", tags=["research"])


class ResearchQueryRequest(BaseModel):
    query: str
    session_id: str
    user_id: Optional[str] = "default_user"
    model: Optional[str] = None
    shield_on: Optional[bool] = True
    request_id: Optional[str] = None


class CancelResponse(BaseModel):
    status: str
    request_id: str
    cancelled: bool
    reason: Optional[str] = None


@router.post("/cancel/{request_id}", response_model=CancelResponse)
async def cancel_research(request_id: str, reason: Optional[str] = "User requested cancellation"):
    """
    Explicit cancellation endpoint (Phase 09).
    Immediately cancels in-flight state machine execution, tool dispatches, and marks session as cancelled.
    """
    success = cancellation_manager.cancel(request_id, reason=reason)
    return CancelResponse(
        status="ok",
        request_id=request_id,
        cancelled=success,
        reason=reason
    )


@router.post("/query", response_model=OrchestrationResult)
async def execute_research_query(req: ResearchQueryRequest):
    """
    Executes a bounded multi-step research query through the Research State Machine.
    """
    try:
        result = await research_orchestrator.execute(
            query=req.query,
            session_id=req.session_id,
            user_id=req.user_id or "default_user",
            model=req.model,
            shield_on=req.shield_on if req.shield_on is not None else True,
            request_id=req.request_id
        )
        return result
    except Exception as exc:
        logger.error(f"Research query execution failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status():
    """
    Returns the real-time status of all step-type circuit breakers.
    """
    return {
        "circuit_breakers": circuit_breaker.get_all_status()
    }


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(step_type: Optional[str] = None):
    """
    Resets circuit breaker state for a specific step type or all steps.
    """
    circuit_breaker.reset(step_type=step_type)
    return {"status": "ok", "reset_step": step_type or "all"}


@router.get("/mode")
async def get_system_network_mode():
    """
    Returns the active system network mode and allowlisted legal sources (Phase 10).
    """
    from app.network.mode_enforcer import mode_enforcer
    return {
        "mode": mode_enforcer.get_mode(),
        "is_offline": mode_enforcer.is_offline(),
        "is_online": mode_enforcer.is_online(),
        "allowlisted_sources": mode_enforcer.load_allowlist().get("allowed_domains", [])
    }


class ModeUpdateRequest(BaseModel):
    mode: str
    reason: Optional[str] = "User requested mode update"


@router.post("/mode")
async def update_system_network_mode(req: ModeUpdateRequest):
    """
    Explicitly changes the system network mode ('OFFLINE' or 'ONLINE').
    """
    from app.network.mode_enforcer import mode_enforcer
    try:
        updated = mode_enforcer.set_mode(req.mode, reason=req.reason or "API update")
        return {
            "status": "ok",
            "mode": updated,
            "message": f"Network mode explicitly set to {updated}."
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/pipeline")
async def run_research_pipeline(req: ResearchQueryRequest):
    """
    Executes the 10-step bounded online/offline legal research pipeline (Phase 10).
    """
    from app.research.pipeline import research_pipeline
    res = await research_pipeline.execute_research(
        query=req.query,
        session_id=req.session_id,
        user_id=req.user_id or "default_user",
        model=req.model
    )
    return res.model_dump()
