import logging
import httpx
from typing import Optional, AsyncIterator
from app.config import settings
from app.model.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

class OllamaRuntime:
    def __init__(self):
        self._client = OllamaClient(settings.OLLAMA_URL, settings.DEFAULT_MODEL)

    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        return await self._client.generate(prompt, model=model)

    async def generate_stream(self, prompt: str, model: Optional[str] = None, **kwargs) -> AsyncIterator[str]:
        async for token in self._client.generate_stream(prompt, model=model):
            yield token

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{settings.OLLAMA_URL.rstrip('/')}/api/version")
                return resp.status_code == 200
        except Exception:
            return False
