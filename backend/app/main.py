# Suppress ChromaDB telemetry warnings before any imports
import os
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("CHROMA_TELEMETRY", "false")

# pyrefly: ignore [missing-import]
from contextlib import asynccontextmanager
import logging
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat, upload, recommend, audit, models, memory, cache, runtime, mcp, research, diagnostics, statutes, auth, vaults, conversations, settings as settings_routes, hardware
from app.observability.correlation import CorrelationMiddleware
from app.config import settings
from app.system.hardware_detector import HardwareDetector
from app.system.model_registry import ModelRegistry

from app.db.health import check_db_health
from app.db.engine import init_db_schema

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Non-blocking background hardware detection warmup
    HardwareDetector.detect()
    ModelRegistry()
    try:
        await init_db_schema()
    except Exception as exc:
        logger.warning(f"Database schema initialization deferred: {exc}")
    logger.info("DFrag Enterprise API service & Stage 5 Runtime initialized.")
    yield

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

app = FastAPI(
    title="Defensive RAG (DFrag) Enterprise API",
    version="2.0.0",
    description="A multi-tier secure, agentic Retrieval-Augmented Generation pipeline for sensitive Indian Legal Research",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Correlation Tracking Middleware (Phase 11)
app.add_middleware(CorrelationMiddleware)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register routes
app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(recommend.router)
app.include_router(audit.router)
app.include_router(models.router)
app.include_router(memory.router)
app.include_router(cache.router)
app.include_router(runtime.router)
app.include_router(mcp.router)
app.include_router(research.router)
app.include_router(diagnostics.router)
app.include_router(statutes.router)
app.include_router(auth.router)
app.include_router(vaults.router)
app.include_router(conversations.router)
app.include_router(settings_routes.router)
app.include_router(hardware.router)

@app.get("/")
def read_root():
    return {"message": "DFrag API is running"}

@app.get("/health")
async def health_check():
    ollama_ok = False
    ollama_version = None
    installed_models = []
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(f"{settings.OLLAMA_URL.rstrip('/')}/api/version")
            if res.status_code == 200:
                ollama_ok = True
                ollama_version = res.json().get("version")

            tags_res = await client.get(f"{settings.OLLAMA_URL.rstrip('/')}/api/tags")
            if tags_res.status_code == 200:
                installed_models = [m.get("name") for m in tags_res.json().get("models", [])]
    except Exception:
        ollama_ok = False

    db_status = await check_db_health()

    return {
        "status": "healthy" if db_status["status"] != "offline" else "degraded",
        "runtime": settings.MODEL_RUNTIME,
        "database": db_status,
        "ollama": {
            "status": "running" if ollama_ok else "offline",
            "version": ollama_version,
            "installed_models": installed_models,
        },
    }

@app.get("/health/db")
async def db_health_check():
    return await check_db_health()

