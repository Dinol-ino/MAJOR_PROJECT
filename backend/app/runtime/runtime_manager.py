import logging
from typing import Optional, Dict, Any
from app.config import settings
from app.runtime.base import LLMRuntime
from app.runtime.factory import build_runtime

logger = logging.getLogger(__name__)

class RuntimeManager:
    _instance: Optional[LLMRuntime] = None
    _active_name: str = settings.MODEL_RUNTIME

    @classmethod
    def get(cls) -> LLMRuntime:
        if cls._instance is None:
            cls._instance = build_runtime(cls._active_name)
        return cls._instance

    @classmethod
    def switch(cls, runtime_name: str) -> bool:
        try:
            new_runtime = build_runtime(runtime_name)
            cls._instance = new_runtime
            cls._active_name = runtime_name
            settings.MODEL_RUNTIME = runtime_name
            logger.info(f"Switched active runtime to {runtime_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to switch runtime to {runtime_name}: {e}")
            return False

    @classmethod
    async def health(cls) -> Dict[str, Any]:
        runtime = cls.get()
        is_healthy = await runtime.health_check()
        return {
            "runtime": cls._active_name,
            "model": settings.DEFAULT_MODEL,
            "healthy": is_healthy
        }
