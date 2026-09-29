"""
Active local model state (single source of truth for "which model answers").

- Installed models come from the live runtime (Ollama /api/tags), never from the registry.
- The active model is persisted in the existing `system_settings` table so it survives
  backend / Docker restarts.
- Activation = verify installed -> compatibility check -> warm-up load -> health check -> persist.
- There is no silent fallback: if the active model is unavailable the caller is told so.
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_ACTIVE_MODEL_KEY = "runtime.active_model"


def normalize_tag(name: Optional[str]) -> str:
    tag = (name or "").strip().lower()
    if tag and ":" not in tag:
        tag = f"{tag}:latest"
    return tag


class ModelNotAvailable(Exception):
    """Raised when a requested model cannot be used; message is safe to show to users."""

    def __init__(self, message: str, code: str = "model_unavailable"):
        super().__init__(message)
        self.code = code


class ModelStateService:
    def __init__(self) -> None:
        self._tags_cache: Optional[Dict[str, Any]] = None
        self._tags_cache_at: float = 0.0
        self._tags_lock = asyncio.Lock()
        self._activation_lock = asyncio.Lock()
        self._active_cache: Optional[str] = None
        self._active_loaded = False
        self._last_activation: Dict[str, Any] = {}

    # ------------------------------------------------------------------ installed
    async def list_installed(self, force: bool = False) -> Dict[str, Any]:
        """Live list of models present in the local runtime (cached briefly to avoid request storms)."""
        now = time.monotonic()
        if not force and self._tags_cache and now - self._tags_cache_at < settings.model.tags_cache_seconds:
            return self._tags_cache
        async with self._tags_lock:
            now = time.monotonic()
            if not force and self._tags_cache and now - self._tags_cache_at < settings.model.tags_cache_seconds:
                return self._tags_cache
            result: Dict[str, Any] = {"online": False, "models": [], "checked_at": datetime.utcnow().isoformat() + "Z"}
            try:
                async with httpx.AsyncClient(timeout=settings.model.probe_timeout_seconds) as client:
                    resp = await client.get(f"{settings.OLLAMA_URL.rstrip('/')}/api/tags")
                    if resp.status_code == 200:
                        result["online"] = True
                        for m in resp.json().get("models", []) or []:
                            details = m.get("details") or {}
                            result["models"].append({
                                "name": m.get("name") or m.get("model"),
                                "size_bytes": m.get("size"),
                                "digest": m.get("digest"),
                                "modified_at": m.get("modified_at"),
                                "family": details.get("family"),
                                "parameter_size": details.get("parameter_size"),
                                "quantization": details.get("quantization_level"),
                                "format": details.get("format"),
                            })
                    else:
                        result["error"] = f"runtime responded HTTP {resp.status_code}"
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                result["error"] = f"runtime unreachable ({type(exc).__name__})"
            self._tags_cache = result
            self._tags_cache_at = time.monotonic()
            return result

    def invalidate(self) -> None:
        self._tags_cache = None

    async def is_installed(self, model: str) -> Optional[bool]:
        """True/False when the runtime answered; None when the runtime is unreachable."""
        tags = await self.list_installed()
        if not tags["online"]:
            return None
        wanted = normalize_tag(model)
        return any(normalize_tag(m["name"]) == wanted for m in tags["models"])

    # ------------------------------------------------------------------ active
    def _load_persisted(self) -> Optional[str]:
        try:
            from app.db.engine import get_sync_session
            from app.db.models import SystemSetting

            with get_sync_session() as session:
                rec = session.query(SystemSetting).filter_by(key=_ACTIVE_MODEL_KEY).first()
                return rec.encrypted_value if rec and rec.encrypted_value else None
        except Exception as exc:
            logger.warning("Could not load persisted active model: %s", type(exc).__name__)
            return None

    def _persist(self, model: str) -> None:
        from app.db.engine import get_sync_session
        from app.db.models import SystemSetting

        with get_sync_session() as session:
            rec = session.query(SystemSetting).filter_by(key=_ACTIVE_MODEL_KEY).first()
            if rec:
                rec.encrypted_value = model  # model tags are not secret; column name is historical
                rec.updated_at = datetime.utcnow()
            else:
                session.add(SystemSetting(key=_ACTIVE_MODEL_KEY, encrypted_value=model))

    def persisted_active_model(self) -> Optional[str]:
        if not self._active_loaded:
            self._active_cache = self._load_persisted()
            self._active_loaded = True
        return self._active_cache

    async def get_active(self) -> Dict[str, Any]:
        """Resolves the active model and whether it is really usable right now."""
        persisted = self.persisted_active_model()
        tags = await self.list_installed()
        installed_names = {normalize_tag(m["name"]) for m in tags["models"]}
        candidate, source = (persisted, "user_selected") if persisted else (settings.DEFAULT_MODEL or None, "configured_default")
        available = bool(candidate) and tags["online"] and normalize_tag(candidate) in installed_names
        if not persisted and candidate and tags["online"] and not available:
            # A configured default that is not installed is not an active model.
            candidate, source = None, "none"
        return {
            "model": candidate,
            "source": source,
            "available": available,
            "runtime_online": tags["online"],
            "last_activation": self._last_activation or None,
        }

    async def resolve_for_request(self, requested: Optional[str]) -> str:
        """Model that will answer this request. Raises ModelNotAvailable instead of substituting."""
        if requested:
            installed = await self.is_installed(requested)
            if installed is False:
                raise ModelNotAvailable(
                    f"The selected model '{requested}' is not installed locally. Choose an installed model "
                    "or download it from Hardware & Models.",
                    code="model_not_installed",
                )
            return requested
        active = await self.get_active()
        if active["model"]:
            return active["model"]
        raise ModelNotAvailable(
            "No local model is active. Open Hardware & Models to download or activate one.",
            code="no_active_model",
        )

    async def activate(self, model: str) -> Dict[str, Any]:
        """Verify -> compatibility -> warm-up -> health -> persist. Serialized; never auto-downloads."""
        model = (model or "").strip()
        if not model:
            raise ModelNotAvailable("A model name is required.", code="invalid_model")

        async with self._activation_lock:
            t0 = time.perf_counter()
            tags = await self.list_installed(force=True)
            if not tags["online"]:
                raise ModelNotAvailable("The local model runtime (Ollama) is not reachable.", code="runtime_offline")
            match = next((m for m in tags["models"] if normalize_tag(m["name"]) == normalize_tag(model)), None)
            if not match:
                raise ModelNotAvailable(f"'{model}' is not installed locally.", code="model_not_installed")

            compatibility = self._compatibility(model)
            if compatibility.get("safety_tier") == "UNSUPPORTED":
                raise ModelNotAvailable(
                    f"'{model}' exceeds this machine's safe memory limits: {compatibility.get('fit_reason')}",
                    code="incompatible_hardware",
                )

            warm = await self._warm_up(match["name"])
            if not warm["ok"]:
                raise ModelNotAvailable(f"'{model}' could not be loaded: {warm['error']}", code="warmup_failed")

            self._persist(match["name"])
            self._active_cache = match["name"]
            self._active_loaded = True
            self._last_activation = {
                "model": match["name"],
                "activated_at": datetime.utcnow().isoformat() + "Z",
                "load_ms": warm.get("load_ms"),
                "activation_ms": round((time.perf_counter() - t0) * 1000, 1),
            }
            try:
                from app.defense.audit_log import AuditLogger

                AuditLogger().log(action=f"model_activated:{match['name']}", layer="runtime")
            except Exception:
                pass
            return {"status": "active", **self._last_activation, "compatibility": compatibility}

    @staticmethod
    def _compatibility(model: str) -> Dict[str, Any]:
        """Registry-based fit evaluation when the model has registry metadata; 'unknown' otherwise."""
        try:
            from app.system.hardware_detector import HardwareDetector
            from app.system.model_registry import ModelRegistry

            registry = ModelRegistry()
            entry = registry.get(model) or next(
                (m for m in registry.all_models() if normalize_tag(m.ollama_tag) == normalize_tag(model)), None
            )
            if not entry:
                return {"safety_tier": "UNKNOWN", "fit_reason": "No registry metadata; runtime load test decides."}
            return registry.evaluate_model_fit(entry, HardwareDetector.detect())
        except Exception as exc:
            return {"safety_tier": "UNKNOWN", "fit_reason": f"fit check unavailable ({type(exc).__name__})"}

    @staticmethod
    async def _warm_up(model: str) -> Dict[str, Any]:
        """Asks the runtime to load the model into memory (empty prompt => load only) and reports load time."""
        timeout = httpx.Timeout(
            connect=settings.model.connect_timeout_seconds,
            read=settings.model.warmup_timeout_seconds,
            write=10.0,
            pool=5.0,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_URL.rstrip('/')}/api/generate",
                    json={"model": model, "prompt": "", "stream": False},
                )
            if resp.status_code != 200:
                body = resp.text[:200].lower()
                if "memory" in body:
                    return {"ok": False, "error": "insufficient memory to load the model"}
                return {"ok": False, "error": f"runtime returned HTTP {resp.status_code}"}
            data = resp.json()
            load_ns = data.get("load_duration")
            return {"ok": True, "load_ms": round(load_ns / 1e6, 1) if isinstance(load_ns, (int, float)) else None}
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            return {"ok": False, "error": f"runtime unreachable ({type(exc).__name__})"}


model_state = ModelStateService()
