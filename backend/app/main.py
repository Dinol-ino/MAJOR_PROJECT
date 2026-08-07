# pyrefly: ignore [missing-import]
from contextlib import asynccontextmanager
import logging
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat, upload, recommend, audit, models
from app.config import settings
from app.system.hardware_detector import HardwareDetector
from app.system.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Non-blocking background hardware detection warmup
    HardwareDetector.detect()
    ModelRegistry()
    logger.info("DFrag Enterprise API service & Stage 5 Runtime initialized.")
    yield

app = FastAPI(
    title="DFrag Enterprise API",
    description="Security-Hardened, Privacy-Preserving Legal AI Workspace API",
    lifespan=lifespan,
)

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

    return {
        "status": "healthy",
        "runtime": settings.MODEL_RUNTIME,
        "ollama": {
            "status": "running" if ollama_ok else "offline",
            "version": ollama_version,
            "installed_models": installed_models,
        },
    }
