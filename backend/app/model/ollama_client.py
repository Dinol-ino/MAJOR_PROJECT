import httpx
from typing import Dict, Any, Optional

class OllamaClient:
    def __init__(self, base_url: str, default_model: str):
        self.base_url = base_url
        self.default_model = default_model
        # Simple backup model
        self.fallback_model = "gemma2:2b"

    async def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Sends generation request to local Ollama.
        If default_model fails/times out, routes query to fallback_model.
        """
        target_model = model or self.default_model
        try:
            return await self._call_ollama(prompt, target_model)
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            # Fallback triggered if primary model fails
            if target_model != self.fallback_model:
                try:
                    return await self._call_ollama(prompt, self.fallback_model)
                except Exception:
                    raise exc
            raise exc

    async def _call_ollama(self, prompt: str, model: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
