import json
import logging
import asyncio
# pyrefly: ignore [missing-import]
import httpx
from typing import Dict, Any, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaUnavailableError(RuntimeError):
    pass


class ModelNotInstalledError(OllamaUnavailableError):
    """The requested model is not present in the local runtime."""


class OllamaClient:
    def __init__(self, base_url: str | None = None, default_model: str | None = None):
        self.base_url = (base_url or settings.OLLAMA_URL).rstrip("/")
        self.default_model = default_model or settings.DEFAULT_MODEL
        self.fallback_model = settings.OLLAMA_FALLBACK_MODEL.strip()

    async def generate(self, prompt: str, model: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> str:
        text, _ = await self.generate_with_metrics(prompt, model=model, options=options)
        return text

    async def generate_with_metrics(
        self, prompt: str, model: Optional[str] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate text with OOM-aware retry and return Ollama's own timing/token counters:
        1. Try with configured GPU layers
        2. On CUDA/CPU OOM -> retry with num_gpu=0 (full CPU offload)
        3. On persistent OOM -> clear error about insufficient resources
        The requested model is never silently replaced by another model.
        """
        target_model = (model or self.default_model).strip()
        max_retries = max(1, int(getattr(settings.model, "generation_retries", 2)))
        initial_delay = 1.0

        for attempt in range(max_retries):
            try:
                return await self._call_ollama(prompt, target_model, options=options)
            except httpx.HTTPStatusError as exc:
                resp_body = exc.response.text if exc.response else ""

                # --- CUDA/CPU OOM Detection ---
                if exc.response.status_code == 500 and self._is_oom_error(resp_body):
                    logger.warning(
                        f"OOM detected on attempt {attempt + 1} for model '{target_model}'. "
                        f"Retrying with num_gpu=0 (CPU-only mode)."
                    )
                    try:
                        return await self._call_ollama(prompt, target_model, force_cpu=True, options=options)
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

                # --- Model Not Found (never silently substitute another model) ---
                if exc.response.status_code == 404:
                    raise ModelNotInstalledError(
                        f"Model '{target_model}' is not installed in the local runtime. "
                        "Download it from Hardware & Models, or select an installed model."
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
                if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
                    raise OllamaUnavailableError(
                        f"Ollama daemon is unreachable at {self.base_url}: {exc}"
                    ) from exc
                if attempt == max_retries - 1:
                    raise OllamaUnavailableError(
                        f"Ollama generation timed out at {self.base_url}."
                    ) from exc
                await asyncio.sleep(initial_delay * (2 ** attempt))

        raise OllamaUnavailableError(f"Failed to query model '{target_model}' after {max_retries} attempts.")

    async def generate_stream(self, prompt: str, model: Optional[str] = None, options: Optional[Dict[str, Any]] = None):
        target_model = (model or self.default_model).strip()
        gen_timeout = float(settings.model.generation_timeout_seconds)
        conn_timeout = float(settings.model.connect_timeout_seconds)
        timeout = httpx.Timeout(
            connect=conn_timeout,
            read=gen_timeout,
            write=30.0,
            pool=10.0,
        )
        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": True,
            "options": self._build_options(overrides=options),
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
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise ModelNotInstalledError(f"Model '{target_model}' is not installed in the local runtime.") from exc
            raise OllamaUnavailableError(f"Ollama streaming error (HTTP {exc.response.status_code if exc.response else '?'}).") from exc
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            raise OllamaUnavailableError(f"Ollama daemon is unreachable at {self.base_url}.") from exc

    async def _call_ollama(
        self, prompt: str, model: str, force_cpu: bool = False, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        gen_timeout = float(settings.model.generation_timeout_seconds)
        conn_timeout = float(settings.model.connect_timeout_seconds)
        timeout = httpx.Timeout(
            connect=conn_timeout,
            read=gen_timeout,
            write=30.0,
            pool=10.0,
        )
        built_options = self._build_options(force_cpu=force_cpu, overrides=options)
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": built_options,
        }
        url = f"{self.base_url}/api/generate"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
            answer = (body.get("response") or "").strip()
            if not answer:
                raise OllamaUnavailableError("Ollama returned an empty response.")
            return answer, self._extract_metrics(body, built_options)

    @staticmethod
    def _extract_metrics(body: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Ollama's own counters (durations are nanoseconds). Nothing here is estimated."""
        def _ms(key: str) -> Optional[float]:
            val = body.get(key)
            return round(val / 1e6, 2) if isinstance(val, (int, float)) else None

        eval_count = body.get("eval_count")
        eval_ms = _ms("eval_duration")
        tokens_per_sec = None
        if isinstance(eval_count, int) and eval_ms:
            tokens_per_sec = round(eval_count / (eval_ms / 1000.0), 2)
        num_predict = options.get("num_predict")
        return {
            "prompt_tokens": body.get("prompt_eval_count"),
            "generation_tokens": eval_count,
            "load_ms": _ms("load_duration"),
            "prompt_eval_ms": _ms("prompt_eval_duration"),
            "generation_ms": eval_ms,
            "total_ms": _ms("total_duration"),
            "tokens_per_sec": tokens_per_sec,
            "num_ctx": options.get("num_ctx"),
            "num_predict": num_predict,
            "done_reason": body.get("done_reason"),
            # True when the model stopped because the output budget ran out (not because the answer was complete).
            "hit_output_limit": body.get("done_reason") == "length"
            or (isinstance(eval_count, int) and isinstance(num_predict, int) and num_predict > 0 and eval_count >= num_predict),
        }

    def _build_options(self, force_cpu: bool = False, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build Ollama options: context/output budgets plus GPU layer control.

        OLLAMA_NUM_GPU_LAYERS < 0 (the default) lets Ollama decide GPU offload itself.
        """
        opts: Dict[str, Any] = {
            "num_ctx": settings.GENERATOR_CONTEXT_TOKENS,
            "num_predict": settings.GENERATOR_MAX_OUTPUT_TOKENS,
        }
        if overrides:
            for key in ("num_ctx", "num_predict", "temperature", "top_p", "seed"):
                if overrides.get(key) is not None:
                    opts[key] = overrides[key]
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
