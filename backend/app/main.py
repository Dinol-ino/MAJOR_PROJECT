# Suppress ChromaDB telemetry warnings before any imports
import os
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("CHROMA_TELEMETRY", "false")

# pyrefly: ignore [missing-import]
from contextlib import asynccontextmanager
import asyncio
import logging
import time
from fastapi import Depends, FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat, upload, recommend, audit, models, memory, runtime, mcp, research, diagnostics, statutes, auth, vaults, conversations
from app.observability.correlation import CorrelationMiddleware
from app.config import settings
from app.system.hardware_detector import HardwareDetector
from app.system.model_registry import ModelRegistry

from app.db.health import check_db_health
from app.db.engine import init_db_schema
from app.runtime.manager import runtime_manager

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

    # Background auto-pull & warmup of the Tier 0 floor model (no terminal needed).
    async def _background_warmup():
        try:
            await runtime_manager.warmup_floor_model()
        except Exception as exc:
            logger.warning(f"Background model auto-pull/warmup deferred: {exc}")

    app.state.warmup_task = asyncio.create_task(_background_warmup())
    logger.info("DFrag Enterprise API service & Stage 5 Runtime initialized. Floor model auto-pull/warmup scheduled in background.")
    yield
    app.state.warmup_task.cancel()

from app.security.rate_limit import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

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

# Setup CORS (explicit allow-list from settings; wildcard never combined with credentials)
_origins = settings.ALLOWED_ORIGINS
if "*" in _origins and not settings.security.allow_credentials:
    _origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register routes (consolidated modular routers)
# All business routers enforce authentication via get_current_user.
from app.routes.auth import get_current_user

PROTECTED = [Depends(get_current_user)]

app.include_router(chat.router, dependencies=PROTECTED)
app.include_router(upload.router, dependencies=PROTECTED)
app.include_router(recommend.router, dependencies=PROTECTED)
app.include_router(audit.router, dependencies=PROTECTED)
app.include_router(models.router, dependencies=PROTECTED)       # Includes hardware & telemetry routes
app.include_router(memory.router, dependencies=PROTECTED)
app.include_router(runtime.router, dependencies=PROTECTED)
app.include_router(mcp.router, dependencies=PROTECTED)
app.include_router(research.router, dependencies=PROTECTED)
app.include_router(diagnostics.router, dependencies=PROTECTED)  # Includes cache metrics & control routes
app.include_router(statutes.router, dependencies=PROTECTED)
app.include_router(auth.router)         # Public: register/login/me & settings
app.include_router(vaults.router, dependencies=PROTECTED)
app.include_router(conversations.router, dependencies=PROTECTED)

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
        "model_warmup": {
            "warmed_up": runtime_manager.is_warmed_up,
            "auto_pull_on_startup": settings.model.auto_pull_on_startup,
        },
        "ollama": {
            "status": "running" if ollama_ok else "offline",
            "version": ollama_version,
            "installed_models": installed_models,
        },
    }

@app.get("/health/db")
async def db_health_check():
    return await check_db_health()

