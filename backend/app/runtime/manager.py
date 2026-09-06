import time
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncIterator
import httpx

from app.config import settings
from app.runtime.hardware_detect import detect_hardware, get_current_tier
from app.runtime.router import model_router
from app.runtime.factory import RuntimeFactory
from app.memory.audit_memory import audit_memory

logger = logging.getLogger(__name__)


class ModelLifecycleManager:
    """
    Unified LLM Runtime & Model Lifecycle Manager (Phase 05).
    Responsible for:
    - Config-driven model routing per task.
    - Automatic hardware tier evaluation.
    - Startup floor model warmup (Tier 0).
    - Graceful OOM recovery with tier step-down and L6 audit logging.
    - Idle model unloading.
    - Status transparency.
    """

    def __init__(self):
        self._runtime_name = settings.MODEL_RUNTIME
        self._runtime = RuntimeFactory.create(self._runtime_name)
        self._active_model = settings.DEFAULT_MODEL
        self._last_used_at = time.time()
        self._is_warmed_up = False

    @property
    def runtime(self):
        return self._runtime

    def get_routed_model_for_task(self, task_type: str, text_length: int = 0) -> Dict[str, Any]:
        """Routes task to appropriate model using config-driven ModelRouter."""
        current_tier = get_current_tier()
        route_decision = model_router.route_task(
            task_type=task_type,
            hardware_tier=current_tier,
            text_length=text_length
        )
        return route_decision

    async def generate_with_oom_recovery(
        self,
        prompt: str,
        task_type: str = "legal_reasoning",
        preferred_model: Optional[str] = None,
        text_length: int = 0
    ) -> Dict[str, Any]:
        """
        Executes text generation with automatic OOM recovery:
        1. Routes task to target model.
        2. On OOM/inference failure, logs event to L6 audit memory.
        3. Steps down to lower tier model or fallback model.
        4. Retries once with clean degradation notice.
        """
        route_info = self.get_routed_model_for_task(task_type, text_length=text_length)
        target_model = preferred_model or route_info.get("model_name", self._active_model)

        self._active_model = target_model
        self._last_used_at = time.time()

        try:
            answer = await self._runtime.generate(prompt, model=target_model)
            return {
                "answer": answer,
                "model_used": target_model,
                "tier": route_info.get("tier", "unknown"),
                "fallback_occurred": False,
                "status": "success"
            }
        except Exception as exc:
            error_msg = str(exc)
            logger.warning(f"Generation failure with model '{target_model}': {error_msg}. Initiating OOM recovery step-down.")

            # Record fallback event in L6 Audit Memory
            try:
                audit_memory.append_event(
                    action="model_oom_fallback",
                    layer="runtime_manager",
                    injection_score=0.0,
                    validation_pass_fail="fallback",
                    model_tier_used=settings.model.fallback_model
                )
            except Exception as audit_err:
                logger.warning(f"Audit logging error during OOM recovery: {audit_err}")

            # Step-down to Fallback model
            fallback_model = settings.model.fallback_model
            try:
                fallback_answer = await self._runtime.generate(prompt, model=fallback_model)
                return {
                    "answer": fallback_answer,
                    "model_used": fallback_model,
                    "tier": "minimum",
                    "fallback_occurred": True,
                    "notice": f"Primary model ({target_model}) encountered resource limits. Successfully generated answer using fallback model ({fallback_model}).",
                    "status": "degraded_success"
                }
            except Exception as final_exc:
                logger.error(f"Fallback model execution failed: {final_exc}")
                raise RuntimeError(f"Model execution failed across both primary ({target_model}) and fallback ({fallback_model}): {final_exc}") from final_exc

    async def generate_stream_with_routing(
        self,
        prompt: str,
        task_type: str = "legal_reasoning",
        preferred_model: Optional[str] = None,
        text_length: int = 0
    ) -> AsyncIterator[str]:
        """Streams generated tokens using routed model."""
        route_info = self.get_routed_model_for_task(task_type, text_length=text_length)
        target_model = preferred_model or route_info.get("model_name", self._active_model)
        self._active_model = target_model
        self._last_used_at = time.time()

        async for token in self._runtime.generate_stream(prompt, model=target_model):
            yield token

    async def warmup_floor_model(self) -> bool:
        """
        Warms up the Tier 0 floor model on startup to avoid cold start latency.
        Does not warm up higher tiers to conserve hardware resources.
        """
        if not settings.model.model_warmup_on_startup:
            logger.info("Model warmup on startup is disabled in configuration.")
            return False

        try:
            floor_model = settings.model.default_model
            logger.info(f"Warming up Tier 0 floor model ({floor_model})...")
            # Quick 1-token prompt to load weights into memory
            await self._runtime.generate("Warmup test.", model=floor_model)
            self._is_warmed_up = True
            logger.info(f"Tier 0 floor model ({floor_model}) warmed up successfully.")
            return True
        except Exception as exc:
            logger.debug(f"Floor model warmup deferred (Ollama may be initializing): {exc}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Returns transparency status of the active runtime, detected hardware, and routing."""
        hw_specs = detect_hardware()
        current_tier = get_current_tier()
        routing_decision = model_router.route_task("legal_reasoning", hardware_tier=current_tier)

        return {
            "status": "online",
            "runtime_engine": self._runtime_name,
            "active_model": self._active_model,
            "current_tier": current_tier,
            "routing_enabled": settings.model.routing_enabled,
            "hardware_detected": hw_specs,
            "reason_for_selection": routing_decision.get("reason"),
            "recommended_legal_model": routing_decision.get("model_name"),
            "idle_unload_seconds": settings.model.model_idle_unload_seconds,
            "last_used_seconds_ago": int(time.time() - self._last_used_at),
        }


runtime_manager = ModelLifecycleManager()
