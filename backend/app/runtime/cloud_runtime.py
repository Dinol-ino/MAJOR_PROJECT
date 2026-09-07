import json
import logging
from typing import Optional, AsyncIterator, Dict, Any
import httpx

from app.config import settings
from app.config.api_vault import api_vault, ProviderType

logger = logging.getLogger(__name__)


class CloudRuntimeError(Exception):
    """Raised when cloud fallback fails or is misconfigured."""
    pass


class CloudRuntime:
    """
    Spec 02 — Cloud API Fallback Runtime.
    Provides local-agnostic cloud LLM execution for Grok (xAI) and Z.ai APIs only.
    Uses OpenAI-compatible SSE streaming with httpx without heavy proprietary SDKs.
    """

    def __init__(self, provider: Optional[ProviderType] = None):
        self.provider = (provider or settings.cloud_fallback.active_provider).lower()
        if self.provider not in ("grok", "zai"):
            self.provider = "grok"

    def _resolve_config(self, model: Optional[str] = None) -> tuple[str, str, str]:
        """
        Returns (endpoint_url, api_key, resolved_model).
        """
        api_key = api_vault.get(self.provider)
        if not api_key:
            raise CloudRuntimeError(
                f"Cloud fallback cannot proceed: No API key configured for provider '{self.provider}'."
            )

        if self.provider == "grok":
            base_url = settings.cloud_fallback.grok_api_base.rstrip("/")
            endpoint = f"{base_url}/chat/completions"
            resolved_model = model or settings.cloud_fallback.grok_model
        elif self.provider == "zai":
            base_url = settings.cloud_fallback.zai_api_base.rstrip("/")
            endpoint = f"{base_url}/chat/completions"
            resolved_model = model or settings.cloud_fallback.zai_model
        else:
            raise CloudRuntimeError(f"Unsupported cloud provider: {self.provider}")

        return endpoint, api_key, resolved_model

    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """
        Generate complete text response from Grok or Z.ai.
        """
        endpoint, api_key, resolved_model = self._resolve_config(model)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": kwargs.get("temperature", 0.2),
            "max_tokens": kwargs.get("max_tokens", settings.model.max_output_tokens),
            "stream": False
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(endpoint, headers=headers, json=payload)
            except Exception as e:
                logger.error(f"Cloud runtime network error ({self.provider}): {e}")
                raise CloudRuntimeError(f"Failed to connect to cloud provider '{self.provider}': {str(e)}")

            if response.status_code != 200:
                err_text = response.text[:300]
                logger.error(f"Cloud provider '{self.provider}' returned HTTP {response.status_code}: {err_text}")
                raise CloudRuntimeError(
                    f"Cloud provider '{self.provider}' returned HTTP {response.status_code}: {err_text}"
                )

            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
                return content or ""
            except (KeyError, IndexError) as e:
                raise CloudRuntimeError(f"Malformed response structure from cloud provider '{self.provider}': {data}")

    async def generate_stream(self, prompt: str, model: Optional[str] = None, **kwargs) -> AsyncIterator[str]:
        """
        Stream generated tokens incrementally from Grok or Z.ai via OpenAI-compatible SSE.
        """
        endpoint, api_key, resolved_model = self._resolve_config(model)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": kwargs.get("temperature", 0.2),
            "max_tokens": kwargs.get("max_tokens", settings.model.max_output_tokens),
            "stream": True
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        err_snippet = err_body.decode("utf-8", errors="ignore")[:300]
                        raise CloudRuntimeError(
                            f"Cloud provider '{self.provider}' streaming returned HTTP {response.status_code}: {err_snippet}"
                        )

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            data_str = line[len("data:"):].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                token = delta.get("content")
                                if token:
                                    yield token
                            except Exception:
                                continue
            except Exception as e:
                if isinstance(e, CloudRuntimeError):
                    raise
                logger.error(f"Streaming failure with cloud provider '{self.provider}': {e}")
                raise CloudRuntimeError(f"Streaming connection to '{self.provider}' failed: {str(e)}")

    async def health_check(self) -> bool:
        """
        Verifies provider credential configuration and network reachability.
        """
        key = api_vault.get(self.provider)
        if not key:
            return False
        
        # Test endpoint connectivity with a minimal probe
        try:
            endpoint, api_key, resolved_model = self._resolve_config()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            # Fast ping or minimal 1-token test
            payload = {
                "model": resolved_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "stream": False
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(endpoint, headers=headers, json=payload)
                return res.status_code == 200
        except Exception as e:
            logger.debug(f"Cloud health check for {self.provider} returned False: {e}")
            return False
