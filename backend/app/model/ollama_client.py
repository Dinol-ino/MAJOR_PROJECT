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
        Generate text response with OOM-aware retry:
        1. Try with configured GPU layers
        2. On CUDA/CPU OOM → retry with num_gpu=0 (full CPU offload)
        3. On persistent OOM → clear error about insufficient resources
        """
        target_model = (model or self.default_model).strip().lower()
        max_retries = 3
        initial_delay = 2.0

        for attempt in range(max_retries):
            try:
                return await self._call_ollama(prompt, target_model)
            except httpx.HTTPStatusError as exc:
                resp_body = exc.response.text if exc.response else ""

                # --- CUDA/CPU OOM Detection ---
                if exc.response.status_code == 500 and self._is_oom_error(resp_body):
                    logger.warning(
                        f"OOM detected on attempt {attempt + 1} for model '{target_model}'. "
                        f"Retrying with num_gpu=0 (CPU-only mode)."
                    )
                    try:
                        return await self._call_ollama(prompt, target_model, force_cpu=True)
                    except httpx.HTTPStatusError as cpu_exc:
                        cpu_body = cpu_exc.response.text if cpu_exc.response else ""
                        if self._is_oom_error(cpu_body):
                            raise OllamaUnavailableError(
                                f"Insufficient system memory to load model '{target_model}'. "
                                f"Both GPU and CPU memory exhausted. "
                                f"Close other applications to free RAM, or use a smaller model."
                            ) from cpu_exc
                        raise
                    except (httpx.RequestError, httpx.TimeoutException) as cpu_exc:
                        logger.error(f"CPU fallback also failed with connection error: {cpu_exc}")
                        raise OllamaUnavailableError(
                            f"Ollama unreachable during CPU fallback for model '{target_model}'."
                        ) from cpu_exc

                # --- Model Not Found ---
                if exc.response.status_code == 404:
                    if self.fallback_model and target_model != self.fallback_model.lower():
                        try:
                            return await self._call_ollama(prompt, self.fallback_model.lower())
                        except Exception:
                            pass
                    raise OllamaUnavailableError(
                        f"Model '{target_model}' is not pulled in Ollama yet. Click 'Auto-Pull' in Hardware Specs panel."
                    ) from exc

                # --- Server Errors (non-OOM) ---
                if exc.response.status_code in (500, 502, 503, 504):
                    logger.warning(f"Ollama server HTTP {exc.response.status_code} on attempt {attempt + 1}. Retrying...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(initial_delay * (2 ** attempt))
                        continue

                if attempt == max_retries - 1:
                    raise OllamaUnavailableError(f"Ollama server HTTP {exc.response.status_code} error.") from exc

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning(f"Ollama generate attempt {attempt + 1} failed: {exc}")
                if attempt == max_retries - 1:
                    raise OllamaUnavailableError(
                        f"Ollama generation timed out at {self.base_url}. Model initialization in container required more time."
                    ) from exc
                await asyncio.sleep(initial_delay * (2 ** attempt))

        raise OllamaUnavailableError(f"Failed to query model '{target_model}' after {max_retries} attempts.")

    async def generate_stream(self, prompt: str, model: Optional[str] = None):
        target_model = (model or self.default_model).strip().lower()
        timeout = httpx.Timeout(
            connect=30.0,
            read=300.0,
            write=30.0,
            pool=30.0,
        )
        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": True,
            "options": self._build_options(),
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

    async def _call_ollama(self, prompt: str, model: str, force_cpu: bool = False) -> str:
        timeout = httpx.Timeout(
            connect=30.0,
            read=300.0,
            write=30.0,
            pool=30.0,
        )
        options = self._build_options(force_cpu=force_cpu)
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        url = f"{self.base_url}/api/generate"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            answer = response.json().get("response", "").strip()
            if not answer:
                raise OllamaUnavailableError("Ollama returned an empty response.")
            return answer

    def _build_options(self, force_cpu: bool = False) -> Dict[str, Any]:
        """Build Ollama options dict with GPU layer control."""
        opts: Dict[str, Any] = {
            "num_ctx": settings.GENERATOR_CONTEXT_TOKENS,
            "num_predict": settings.GENERATOR_MAX_OUTPUT_TOKENS,
        }
        if force_cpu:
            opts["num_gpu"] = 0
        elif settings.OLLAMA_NUM_GPU_LAYERS >= 0:
            opts["num_gpu"] = settings.OLLAMA_NUM_GPU_LAYERS
        return opts

    @staticmethod
    def _is_oom_error(response_text: str) -> bool:
        """Detect CUDA or CPU out-of-memory errors in Ollama response body."""
        oom_markers = [
            "out of memory",
            "cudaMalloc failed",
            "failed to allocate",
            "alloc_tensor_range",
            "ggml_backend_cpu_buffer_type_alloc_buffer",
            "unable to allocate",
        ]
        lower_text = response_text.lower()
        return any(marker.lower() in lower_text for marker in oom_markers)
