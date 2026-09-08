import os
import yaml
import logging
from typing import Dict, Any, Optional
from app.config import settings
from app.runtime.hardware_detect import get_current_tier

logger = logging.getLogger(__name__)


class ModelRouter:
    """
    Config-driven Model Router (Phase 05).
    Routes each application task to the cheapest capable model tier based on task complexity
    and detected system hardware.
    Zero hardcoded model names in calling code.
    """

    def __init__(self, registry_path: Optional[str] = None):
        self.registry_path = registry_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "model_registry.yaml"
        )
        self._registry_data = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to load model registry YAML: {e}")
        return {}

    @property
    def routing_enabled(self) -> bool:
        return settings.model.routing_enabled

    def route_task(
        self,
        task_type: str,
        hardware_tier: Optional[str] = None,
        text_length: int = 0
    ) -> Dict[str, Any]:
        """
        Routes a given task to the appropriate model or deterministic pipeline.
        Returns:
            Dict[str, Any]: {
                "model_name": str,
                "tier": str,
                "task_type": str,
                "method": "llm" | "deterministic",
                "reason": str
            }
        """
        # If routing is disabled via config, bypass and use fallback model
        if not self.routing_enabled:
            return {
                "model_name": settings.model.fallback_model,
                "tier": "fallback",
                "task_type": task_type,
                "method": "llm",
                "reason": "Model routing disabled via configuration. Using fixed fallback model."
            }

        task_routes = self._registry_data.get("task_routes", {})
        route_config = task_routes.get(task_type, {})
        current_tier = hardware_tier or get_current_tier()

        # 1. Deterministic Tasks (no LLM generation)
        if task_type == "security_classification":
            return {
                "model_name": "deterministic_input_guard",
                "tier": "deterministic",
                "task_type": task_type,
                "method": "deterministic",
                "reason": "Security classification uses deterministic rules & risk scoring without LLM generation."
            }

        if task_type == "citation_verification":
            return {
                "model_name": "deterministic_citation_guard",
                "tier": "deterministic",
                "task_type": task_type,
                "method": "deterministic",
                "reason": "Citation verification uses deterministic statutory overlap and reference extraction."
            }

        # 2. Intent Routing & Query Reformulation (Tier 0 Minimum)
        if task_type in ["intent_routing", "query_reformulation"]:
            preferred = route_config.get("preferred_model", settings.model.default_model)
            return {
                "model_name": preferred,
                "tier": "minimum",
                "task_type": task_type,
                "method": "llm",
                "reason": f"Fast {task_type} routed to lightweight Tier 0 model ({preferred})."
            }

        # 3. Summarization (Complexity-aware)
        if task_type == "summarization":
            complexity_thresh = route_config.get("complexity_threshold_chars", 4000)
            preferred_models = route_config.get("preferred_models", {})
            if text_length > complexity_thresh and current_tier in ["standard", "premium"]:
                model_name = preferred_models.get("complex", "qwen2.5:7b")
                return {
                    "model_name": model_name,
                    "tier": "standard",
                    "task_type": task_type,
                    "method": "llm",
                    "reason": f"Complex document ({text_length} chars) routed to Standard Tier model ({model_name})."
                }
            else:
                model_name = preferred_models.get("short", settings.model.default_model)
                return {
                    "model_name": model_name,
                    "tier": "minimum",
                    "task_type": task_type,
                    "method": "llm",
                    "reason": f"Standard summary ({text_length} chars) routed to Tier 0 model ({model_name})."
                }

        # 4. Complex Legal Reasoning / Synthesis (Hardware-dependent)
        if task_type == "legal_reasoning":
            preferred_models = route_config.get("preferred_models", {})
            chosen_model = preferred_models.get(current_tier, settings.model.default_model)
            return {
                "model_name": chosen_model,
                "tier": current_tier,
                "task_type": task_type,
                "method": "llm",
                "reason": f"Legal reasoning synthesized on {current_tier.capitalize()} Tier model ({chosen_model}) for detected hardware."
            }

        # Default / Unspecified tasks
        return {
            "model_name": settings.model.default_model,
            "tier": current_tier,
            "task_type": task_type,
            "method": "llm",
            "reason": f"Standard routing to default model ({settings.model.default_model})."
        }


model_router = ModelRouter()


from dataclasses import dataclass
from app.runtime.circuit_breaker import circuit_breaker, FailureKind, CircuitBreakerState
from app.config.api_vault import api_vault


@dataclass
class RoutingDecision:
    use_cloud: bool
    provider: Optional[str] = None          # "grok" | "zai"
    model: str = ""                         # target model name
    reason: str = ""
    runtime_switched_event: Optional[Dict[str, Any]] = None


class FallbackRouter:
    """
    Spec 02 — Circuit-breaker Runtime Router with Cloud Fallback promotion.
    Automatically resolves whether to dispatch to local Ollama or promote to CloudRuntime
    (Grok API / Z.ai API only).
    """

    def classify_failure(self, exc: Exception) -> FailureKind:
        msg = str(exc).lower()
        if any(w in msg for w in ("connect", "unreachable", "refused", "connection refused", "not found")):
            return FailureKind.CONNECT_ERROR
        if any(w in msg for w in ("oom", "out of memory", "cuda", "timeout", "timed out", "alloc")):
            return FailureKind.OOM_TIMEOUT
        if "empty" in msg or "whitespace" in msg:
            return FailureKind.EMPTY_GENERATION
        return FailureKind.MALFORMED_OUTPUT

    def resolve_cloud_provider(self) -> Optional[str]:
        """Resolves which cloud provider has an available API key (active provider preferred)."""
        active = settings.cloud_fallback.active_provider.lower()
        if api_vault.is_configured(active):
            return active
        other = "zai" if active == "grok" else "grok"
        if api_vault.is_configured(other):
            return other
        return None

    def route_request(self, target_model: Optional[str] = None) -> RoutingDecision:
        """
        Determines whether the request can proceed locally or must promote to cloud.
        """
        model_name = target_model or settings.model.default_model
        breaker_state = circuit_breaker.get_state(model_name)

        if breaker_state == CircuitBreakerState.OPEN:
            if settings.cloud_fallback.enabled and settings.cloud_fallback.auto_fallback:
                cloud_prov = self.resolve_cloud_provider()
                if cloud_prov:
                    cloud_model = (
                        settings.cloud_fallback.grok_model
                        if cloud_prov == "grok"
                        else settings.cloud_fallback.zai_model
                    )
                    return RoutingDecision(
                        use_cloud=True,
                        provider=cloud_prov,
                        model=cloud_model,
                        reason=f"Circuit breaker for local model '{model_name}' is OPEN. Promoted to Cloud ({cloud_prov.title()}).",
                        runtime_switched_event={
                            "from": "local",
                            "to": "cloud",
                            "provider": cloud_prov,
                            "model": cloud_model,
                            "reason": f"Circuit breaker OPEN for {model_name}"
                        }
                    )

        return RoutingDecision(
            use_cloud=False,
            provider=None,
            model=model_name,
            reason=f"Local execution with {model_name} (Circuit state: {breaker_state.value})."
        )


fallback_router = FallbackRouter()
