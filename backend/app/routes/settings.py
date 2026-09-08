import time
import logging
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
import httpx

from app.config import settings
from app.config.api_vault import api_vault, ProviderType
from app.runtime.cloud_runtime import CloudRuntime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class FallbackSettingsUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    auto_fallback: Optional[bool] = None
    active_provider: Optional[Literal["grok", "zai"]] = None
    grok_key: Optional[str] = None
    zai_key: Optional[str] = None


class FallbackTestRequest(BaseModel):
    provider: Literal["grok", "zai"]
    key: Optional[str] = None  # Optional key to test; if omitted, tests saved vault key


@router.get("/fallback")
def get_fallback_settings():
    """
    Returns current cloud fallback configuration with masked API keys.
    Zero plaintext credentials leaked.
    """
    return api_vault.get_status()


@router.post("/fallback")
def update_fallback_settings(req: FallbackSettingsUpdateRequest):
    """
    Updates cloud fallback settings and encrypts new API keys into the vault.
    """
    try:
        api_vault.update_settings(
            enabled=req.enabled,
            auto_fallback=req.auto_fallback,
            active_provider=req.active_provider
        )

        if req.grok_key is not None:
            if req.grok_key.strip():
                api_vault.set_from_ui("grok", req.grok_key.strip())
            else:
                api_vault.delete("grok")

        if req.zai_key is not None:
            if req.zai_key.strip():
                api_vault.set_from_ui("zai", req.zai_key.strip())
            else:
                api_vault.delete("zai")

        return {
            "status": "success",
            "message": "Fallback settings updated successfully.",
            "settings": api_vault.get_status()
        }
    except Exception as exc:
        logger.error(f"Failed to update fallback settings: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/fallback/test")
async def test_fallback_key(req: FallbackTestRequest):
    """
    Tests connectivity and authentication against Grok API or Z.ai endpoint.
    Masks credential in all outputs.
    """
    provider = req.provider.lower()
    test_key = req.key.strip() if req.key else api_vault.get(provider)

    if not test_key:
        raise HTTPException(
            status_code=400,
            detail=f"No API key provided or configured for '{provider}'."
        )

    if provider == "grok":
        base_url = settings.cloud_fallback.grok_api_base.rstrip("/")
        model = settings.cloud_fallback.grok_model
    elif provider == "zai":
        base_url = settings.cloud_fallback.zai_api_base.rstrip("/")
        model = settings.cloud_fallback.zai_model
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider '{provider}'.")

    endpoint = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {test_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 2,
        "temperature": 0.0,
        "stream": False
    }

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            latency_ms = round((time.time() - start_time) * 1000, 1)

            if resp.status_code == 200:
                return {
                    "success": True,
                    "provider": provider,
                    "model": model,
                    "latency_ms": latency_ms,
                    "masked_key": api_vault.mask(test_key),
                    "message": f"Successfully connected to {provider.title()} API ({latency_ms}ms)."
                }
            else:
                err_text = resp.text[:200]
                return {
                    "success": False,
                    "provider": provider,
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "error": f"Provider returned HTTP {resp.status_code}: {err_text}"
                }
    except Exception as exc:
        latency_ms = round((time.time() - start_time) * 1000, 1)
        return {
            "success": False,
            "provider": provider,
            "latency_ms": latency_ms,
            "error": f"Connection failed: {str(exc)}"
        }
