import json
import logging
import asyncio
import httpx
from typing import Dict, Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaUnavailableError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str | None = None, default_model: str | None = None):
        self.base_url = (base_url or settings.OLLAMA_URL).rstrip("/")
        self.default_model = default_model or settings.DEFAULT_MODEL
        self.fallback_model = settings.OLLAMA_FALLBACK_MODEL.strip()

    async def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Generate text response with generous timeouts and exponential backoff.
        """
        target_model = model or self.default_model
        max_retries = 2
        initial_delay = 1.0

        for attempt in range(max_retries):
            try:
                return await self._call_ollama(prompt, target_model)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    if self.fallback_model and target_model != self.fallback_model:
                        try:
                            return await self._call_ollama(prompt, self.fallback_model)
                        except Exception:
                            pass
                    raise OllamaUnavailableError(
                        f"Model '{target_model}' is not pulled in Ollama yet. Use the UI 'Auto-Pull' button or pull it via Ollama API."
                    ) from exc
                if attempt == max_retries - 1:
                    raise OllamaUnavailableError(f"Ollama server HTTP {exc.response.status_code} error.") from exc
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning(f"Ollama generate attempt {attempt + 1} timed out/failed: {exc}")
                if attempt == max_retries - 1:
                    raise OllamaUnavailableError(
                        f"Ollama generation timed out at {self.base_url}. High CPU load or model initialization in container."
                    ) from exc
                await asyncio.sleep(initial_delay * (2 ** attempt))

        raise OllamaUnavailableError(f"Failed to query model '{target_model}' after {max_retries} attempts.")

    async def generate_stream(self, prompt: str, model: Optional[str] = None):
        target_model = model or self.default_model
        timeout = httpx.Timeout(
            connect=30.0,
            read=180.0,
            write=30.0,
            pool=30.0,
        )
        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_ctx": settings.GENERATOR_CONTEXT_TOKENS,
                "num_predict": settings.GENERATOR_MAX_OUTPUT_TOKENS,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("response", "")
                                if token:
                                    yield token
                            except Exception:
                                pass
        except Exception:
            full_text = await self.generate(prompt, model=model)
            yield full_text

    async def _call_ollama(self, prompt: str, model: str) -> str:
        timeout = httpx.Timeout(
            connect=30.0,
            read=180.0,
            write=30.0,
            pool=30.0,
        )
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": settings.GENERATOR_CONTEXT_TOKENS,
                "num_predict": settings.GENERATOR_MAX_OUTPUT_TOKENS,
            },
        }
        url = f"{self.base_url}/api/generate"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            answer = response.json().get("response", "").strip()
            if not answer:
                raise OllamaUnavailableError("Ollama returned an empty response.")
            return answer
