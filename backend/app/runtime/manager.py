import time
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncIterator
import httpx

from app.config import settings
from app.runtime.hardware_detect import detect_hardware, get_current_tier
from app.runtime.router import model_router, fallback_router
from app.runtime.factory import RuntimeFactory
from app.runtime.circuit_breaker import circuit_breaker, FailureKind
from app.runtime.cloud_runtime import CloudRuntime
from app.config.api_vault import api_vault
from app.memory.audit_memory import audit_memory

logger = logging.getLogger(__name__)


class ModelLifecycleManager:
    """
    Unified LLM Runtime & Model Lifecycle Manager (Phase 05 & Spec 02).
    Responsible for:
    - Config-driven model routing per task.
    - Automatic hardware tier evaluation.
    - Circuit breaker failure classification and recovery.
    - Seamless Cloud Fallback promotion (Grok / Z.ai).
    - Startup floor model warmup (Tier 0).
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
        Executes text generation with automatic OOM recovery & cloud fallback:
        1. Checks circuit breaker state for target model.
        2. If circuit is open, promotes directly to CloudRuntime (Grok / Z.ai).
        3. Attempts local generation.
        4. On local failure, classifies error, trips breaker, and promotes to CloudRuntime.
        """
        route_info = self.get_routed_model_for_task(task_type, text_length=text_length)
        target_model = preferred_model or route_info.get("model_name", self._active_model)

        # 1. Proactive circuit breaker check
        routing = fallback_router.route_request(target_model)
        if routing.use_cloud and routing.provider:
            logger.info(f"Proactive cloud promotion: {routing.reason}")
            cloud_runtime = CloudRuntime(provider=routing.provider)
            answer = await cloud_runtime.generate(prompt, model=routing.model)
            return {
                "answer": answer,
                "model_used": routing.model,
                "tier": "cloud",
                "fallback_occurred": True,
                "provider": routing.provider,
                "runtime_switched": routing.runtime_switched_event,
                "status": "cloud_success"
            }

        self._active_model = target_model
        self._last_used_at = time.time()

        # 2. Local execution
        try:
            answer = await self._runtime.generate(prompt, model=target_model)
            circuit_breaker.record_success(target_model)
            return {
                "answer": answer,
                "model_used": target_model,
                "tier": route_info.get("tier", "unknown"),
                "fallback_occurred": False,
                "status": "success"
            }
        except Exception as exc:
            error_msg = str(exc)
            kind = fallback_router.classify_failure(exc)
            new_state = circuit_breaker.record_failure(target_model, kind=kind, reason=error_msg)
            logger.warning(
                f"Generation failure with model '{target_model}' (kind={kind.value}, circuit={new_state.value}): {error_msg}."
            )

            # Record fallback event in L6 Audit Memory
            try:
                audit_memory.append_event(
                    action="model_oom_fallback",
                    layer="runtime_manager",
                    injection_score=0.0,
                    validation_pass_fail="fallback",
                    model_tier_used=f"{target_model}_failed_{kind.value}"
                )
            except Exception as audit_err:
                logger.warning(f"Audit logging error during fallback: {audit_err}")

            # 3. Check if cloud fallback is possible (Grok / Z.ai)
            cloud_prov = fallback_router.resolve_cloud_provider()
            if settings.cloud_fallback.enabled and settings.cloud_fallback.auto_fallback and cloud_prov:
                cloud_model = (
                    settings.cloud_fallback.grok_model
                    if cloud_prov == "grok"
                    else settings.cloud_fallback.zai_model
                )
                logger.info(f"Promoting request to CloudRuntime ({cloud_prov.title()}) after local failure.")
                try:
                    cloud_rt = CloudRuntime(provider=cloud_prov)
                    cloud_answer = await cloud_rt.generate(prompt, model=cloud_model)
                    return {
                        "answer": cloud_answer,
                        "model_used": cloud_model,
                        "tier": "cloud",
                        "fallback_occurred": True,
                        "provider": cloud_prov,
                        "notice": f"Local model ({target_model}) encountered {kind.value}. Seamlessly continued via {cloud_prov.title()} API.",
                        "runtime_switched": {
                            "from": "local",
                            "to": "cloud",
                            "provider": cloud_prov,
                            "model": cloud_model
                        },
                        "status": "cloud_fallback_success"
                    }
                except Exception as cloud_exc:
                    logger.error(f"Cloud fallback to {cloud_prov} also failed: {cloud_exc}")

            # 4. Fallback to secondary local model if cloud not configured
            fallback_model = settings.model.fallback_model
            if fallback_model and fallback_model.lower() != target_model.lower():
                try:
                    fallback_answer = await self._runtime.generate(prompt, model=fallback_model)
                    circuit_breaker.record_success(fallback_model)
                    return {
                        "answer": fallback_answer,
                        "model_used": fallback_model,
                        "tier": "minimum",
                        "fallback_occurred": True,
                        "notice": f"Primary model ({target_model}) encountered resource limits. Successfully generated answer using fallback model ({fallback_model}).",
                        "status": "degraded_success"
                    }
                except Exception as final_exc:
                    logger.error(f"Secondary local fallback model failed: {final_exc}")

            raise RuntimeError(
                f"Model execution failed for '{target_model}' ({kind.value}). "
                f"Configure Grok API or Z.ai in settings for automatic cloud fallback."
            )

    async def generate_stream_with_routing(
        self,
        prompt: str,
        task_type: str = "legal_reasoning",
        preferred_model: Optional[str] = None,
        text_length: int = 0
    ) -> AsyncIterator[str]:
        """Streams generated tokens using routed model with circuit breaker protection."""
        route_info = self.get_routed_model_for_task(task_type, text_length=text_length)
        target_model = preferred_model or route_info.get("model_name", self._active_model)

        routing = fallback_router.route_request(target_model)
        if routing.use_cloud and routing.provider:
            logger.info(f"Streaming via CloudRuntime ({routing.provider.title()}) due to circuit breaker.")
            cloud_rt = CloudRuntime(provider=routing.provider)
            async for token in cloud_rt.generate_stream(prompt, model=routing.model):
                yield token
            return

        self._active_model = target_model
        self._last_used_at = time.time()

        try:
            async for token in self._runtime.generate_stream(prompt, model=target_model):
                yield token
            circuit_breaker.record_success(target_model)
        except Exception as exc:
            kind = fallback_router.classify_failure(exc)
            circuit_breaker.record_failure(target_model, kind=kind, reason=str(exc))
            logger.warning(f"Streaming error on '{target_model}' ({kind.value}): {exc}")

            # Promote stream to cloud if configured
            cloud_prov = fallback_router.resolve_cloud_provider()
            if settings.cloud_fallback.enabled and settings.cloud_fallback.auto_fallback and cloud_prov:
                cloud_model = (
                    settings.cloud_fallback.grok_model
                    if cloud_prov == "grok"
                    else settings.cloud_fallback.zai_model
                )
                logger.info(f"Promoting token stream to CloudRuntime ({cloud_prov.title()}).")
                cloud_rt = CloudRuntime(provider=cloud_prov)
                async for token in cloud_rt.generate_stream(prompt, model=cloud_model):
                    yield token
            else:
                raise

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
            await self._runtime.generate("Warmup test.", model=floor_model)
            self._is_warmed_up = True
            logger.info(f"Tier 0 floor model ({floor_model}) warmed up successfully.")
            return True
        except Exception as exc:
            logger.debug(f"Floor model warmup deferred (Ollama may be initializing): {exc}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Returns transparency status of the active runtime, detected hardware, circuit breakers, and cloud fallback."""
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
            "circuit_breakers": circuit_breaker.get_status(),
            "cloud_fallback": api_vault.get_status(),
        }


runtime_manager = ModelLifecycleManager()
