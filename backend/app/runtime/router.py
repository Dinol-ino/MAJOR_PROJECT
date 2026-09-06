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
