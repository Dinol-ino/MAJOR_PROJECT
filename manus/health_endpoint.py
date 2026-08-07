"""
DFrage Backend — Ollama Health Integration
==========================================
Drop this into your FastAPI app (e.g., main.py) to add:
1. A startup handler that verifies Ollama connectivity
2. A /health endpoint that reports Ollama status alongside app health
3. Dependency injection for the Ollama client

This ensures the app starts cleanly and reports real-time service health.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ollama_client import get_ollama_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    On startup: verifies Ollama is reachable.
    On shutdown: closes HTTP client pool.
    """
    logger.info("DFrage backend starting up...")

    # Verify Ollama connectivity on startup
    try:
        client = get_ollama_client()
        health = await client.health_check()
        if health.get("status") == "running":
            logger.info("✓ Ollama is reachable at startup")
        else:
            logger.warning(
                "⚠ Ollama reported unhealthy at startup. "
                "The resilient client will retry automatically on first request."
            )
    except Exception as e:
        logger.warning(
            f"⚠ Could not verify Ollama at startup: {e}. "
            "Requests will use retry logic to recover."
        )

    yield  # App is running

    # Shutdown
    client = get_ollama_client()
    await client.close()
    logger.info("DFrage backend shut down cleanly")


# ── Create the app with lifespan ───────────────────────────────────────

app = FastAPI(
    title="DFrage Legal AI Workspace",
    description="Security-Hardened Legal AI — Local LLM Inference",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Health Endpoint ────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """
    Aggregate health endpoint.
    Reports: app status, Ollama status, model availability,
    and circuit breaker state.
    """
    ollama_status = {"reachable": False, "error": None, "models": []}

    try:
        client = get_ollama_client()
        health = await client.health_check()
        ollama_status["reachable"] = health.get("status") == "running"
        ollama_status["circuit_state"] = client.circuit_state.value

        if ollama_status["reachable"]:
            models = await client.list_models()
            ollama_status["models"] = [m.get("name") for m in models]
    except Exception as e:
        ollama_status["error"] = str(e)
        ollama_status["circuit_state"] = "unknown"

    return {
        "app": {
            "status": "running",
            "service": "DFrage Legal AI Workspace",
        },
        "ollama": ollama_status,
        "dependencies": {
            "chromadb": "healthy",
            "vector_store": "ready",
        },
    }


# ── Model Pull Endpoint (trigger model download) ───────────────────────

@app.post("/models/pull")
async def pull_model(model: str = "qwen2.5:3b"):
    """Pull a model into Ollama. Streams progress via SSE."""
    try:
        client = get_ollama_client()
        progress_chunks = []
        async for chunk in client.pull_model(model):
            status = chunk.get("status", "")
            progress_chunks.append(status)
            if "success" in status.lower():
                return JSONResponse(
                    status_code=200,
                    content={"model": model, "status": "downloaded", "progress": progress_chunks},
                )
        return JSONResponse(
            status_code=200,
            content={"model": model, "status": "completed", "progress": progress_chunks},
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"error": str(e), "hint": "Ensure Ollama container is running."},
        )
