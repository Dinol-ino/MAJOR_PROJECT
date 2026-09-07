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
    if target in ("cloud", "grok", "zai"):
        from app.runtime.cloud_runtime import CloudRuntime
        prov = "zai" if target == "zai" else ("grok" if target == "grok" else None)
        return CloudRuntime(provider=prov)

    return OllamaRuntime()


class RuntimeFactory:
    @staticmethod
    def create(runtime_name: str | None = None) -> LLMRuntime:
        return build_runtime(runtime_name)
