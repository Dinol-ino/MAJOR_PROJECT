"""
Resilient Ollama Client for DFrage Legal AI Workspace
=====================================================
Production-grade client with exponential backoff, circuit breaker,
and health-aware routing. Replaces any naive single-attempt HTTP call
to Ollama in your backend.

Usage:
    client = OllamaClient(base_url="http://localhost:11434")
    response = await client.chat(model="qwen2.5:3b", messages=[...])
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failures detected, rejecting requests
    HALF_OPEN = "half_open"  # Testing recovery


class OllamaClient:
    """
    Production-ready Ollama client with:
    - Exponential backoff retry (max_retries attempts, capped delay)
    - Circuit breaker pattern (trips after failure_threshold consecutive failures)
    - Health-aware request routing
    - Graceful fallback with structured error reporting
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        max_retries: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 32.0,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        default_model: str = "qwen2.5:3b",
        request_timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.default_model = default_model
        self.request_timeout = request_timeout

        # Circuit breaker state
        self._circuit_state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._last_failure_time = 0.0

        # Client pool (reused connections)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=self.request_timeout,
                    write=10.0,
                    pool=10.0,
                ),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    # ── Circuit Breaker Logic ──────────────────────────────────────────

    @property
    def circuit_state(self) -> CircuitState:
        if self._circuit_state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._circuit_state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker → HALF_OPEN (testing recovery)")
        return self._circuit_state

    def _record_success(self):
        self._consecutive_failures = 0
        self._circuit_state = CircuitState.CLOSED

    def _record_failure(self):
        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        if self._consecutive_failures >= self.failure_threshold:
            self._circuit_state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker OPENED after {self._consecutive_failures} failures"
            )

    # ── Health Check ───────────────────────────────────────────────────

    async def health_check(self) -> dict[str, Any]:
        """
        GET /api/health — verify Ollama is alive.
        Returns: {"status": "running"} or raises.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/health")
            response.raise_for_status()
            self._record_success()
            return response.json()
        except Exception as e:
            self._record_failure()
            return {"status": "unhealthy", "error": str(e)}

    # ── Chat / Generate ────────────────────────────────────────────────

    async def chat(
        self,
        model: Optional[str] = None,
        messages: Optional[list[dict]] = None,
        prompt: Optional[str] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Main inference method with retry + circuit breaker.

        Supports both the /api/chat (messages) and /api/generate (prompt) endpoints.
        """
        if self.circuit_state == CircuitState.OPEN:
            raise RuntimeError(
                "Ollama circuit breaker is OPEN — service likely unavailable. "
                f"Retry after {self.recovery_timeout}s."
            )

        use_chat_api = messages is not None
        endpoint = "/api/chat" if use_chat_api else "/api/generate"
        url = f"{self.base_url}{endpoint}"

        model = model or self.default_model

        if use_chat_api:
            payload = {"model": model, "messages": messages, **kwargs}
        else:
            payload = {"model": model, "prompt": prompt or "", "stream": False, **kwargs}

        for attempt in range(self.max_retries):
            try:
                client = await self._get_client()
                response = await client.post(url, json=payload)
                response.raise_for_status()
                self._record_success()
                logger.info(f"Ollama {endpoint} succeeded on attempt {attempt + 1}")
                return response.json()

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                # Connection-level failure — likely Ollama down
                wait_time = min(self.initial_delay * (2 ** attempt), self.max_delay)
                logger.warning(
                    f"Ollama {endpoint} attempt {attempt + 1}/{self.max_retries} failed "
                    f"({type(e).__name__}). Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)
                self._record_failure()

            except httpx.HTTPStatusError as e:
                # Ollama responded but with an error (e.g., model not found)
                self._record_failure()
                if e.response.status_code == 404:
                    # Model not found — retry won't help, re-raise immediately
                    raise RuntimeError(
                        f"Model '{model}' not found in Ollama. "
                        f"Run: docker exec -it dfrage-ollama ollama pull {model}"
                    ) from e
                # Server error — retry might help
                wait_time = min(self.initial_delay * (2 ** attempt), self.max_delay)
                logger.warning(
                    f"Ollama returned {e.response.status_code} on attempt {attempt + 1}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)

            except Exception as e:
                self._record_failure()
                wait_time = min(self.initial_delay * (2 ** attempt), self.max_delay)
                logger.error(
                    f"Unexpected error on attempt {attempt + 1}: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)

        # All retries exhausted
        raise RuntimeError(
            f"Ollama unavailable at {self.base_url} after {self.max_retries} retries. "
            f"Ensure the container is running: docker ps | grep dfrage-ollama"
        )

    # ── Model Management ───────────────────────────────────────────────

    async def list_models(self) -> list[dict[str, Any]]:
        """GET /api/tags — list available models."""
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/api/tags")
        response.raise_for_status()
        return response.json().get("models", [])

    async def pull_model(self, model: str) -> AsyncIterator[dict]:
        """POST /api/pull — stream model download progress."""
        client = await self._get_client()
        async with client.stream(
            "POST",
            f"{self.base_url}/api/pull",
            json={"name": model, "stream": True},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    yield json.loads(line)

    # ── Cleanup ────────────────────────────────────────────────────────

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── Singleton instance for use across your FastAPI app ─────────────────

_ollama_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get or create the global Ollama client singleton."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client
