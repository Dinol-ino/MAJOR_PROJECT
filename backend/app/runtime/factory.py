import logging
from app.config import settings
from app.runtime.base import LLMRuntime
from app.runtime.ollama_runtime import OllamaRuntime
from app.runtime.llamacpp_runtime import LlamaCppRuntime
from app.runtime.mock_runtime import MockRuntime

logger = logging.getLogger(__name__)

def build_runtime(runtime_name: str | None = None) -> LLMRuntime:
    target = (runtime_name or settings.MODEL_RUNTIME).lower()

    if target == "mock":
        return MockRuntime()

    if target == "llamacpp":
        if settings.LLAMACPP_MODEL_PATH:
            return LlamaCppRuntime(settings.LLAMACPP_MODEL_PATH)
        logger.warning("LLAMACPP_MODEL_PATH empty. Falling back to OllamaRuntime.")

    if target == "transformers":
        # Fallback to OllamaRuntime if transformers is selected but model loading delegates to Ollama
        logger.info("Using OllamaRuntime as backend driver for Transformers architecture.")
        return OllamaRuntime()

    return OllamaRuntime()
