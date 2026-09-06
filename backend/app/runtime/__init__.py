"""
LLM Runtime & Model Routing Package (Phase 05).
"""

from app.runtime.base import LLMRuntime
from app.runtime.factory import RuntimeFactory
from app.runtime.router import model_router, ModelRouter
from app.runtime.manager import runtime_manager, ModelLifecycleManager
from app.runtime.hardware_detect import detect_hardware, get_current_tier
from app.runtime.streaming import format_sse_event, stream_token_generator
from app.runtime.token_budget_manager import TokenBudgetManager
from app.runtime.citation_builder import CitationBuilder
from app.runtime.context_builder import ContextBuilder
from app.runtime.hallucination_detector import HallucinationDetector
from app.runtime.confidence_scorer import ConfidenceScorer
from app.runtime.response_formatter import ResponseFormatter

__all__ = [
    "LLMRuntime",
    "RuntimeFactory",
    "model_router",
    "ModelRouter",
    "runtime_manager",
    "ModelLifecycleManager",
    "detect_hardware",
    "get_current_tier",
    "format_sse_event",
    "stream_token_generator",
    "TokenBudgetManager",
    "CitationBuilder",
    "ContextBuilder",
    "HallucinationDetector",
    "ConfidenceScorer",
    "ResponseFormatter",
]
