import os
import json
import time
import uuid
import asyncio
import sqlite3
import logging
import httpx
import shutil
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.system.hardware_detector import HardwareDetector, HardwareProfile
from app.system.model_registry import ModelRegistry, ModelEntry
from app.system.model_download_manager import ModelDownloadManager
from app.config.settings import settings

logger = logging.getLogger(__name__)


def _normalize_ollama_tag(name: str) -> str:
    """Lowercased tag with implicit ':latest' so 'qwen2.5:3b' != 'qwen2.5:7b'."""
    tag = (name or "").strip().lower()
    if tag and ":" not in tag:
        tag = f"{tag}:latest"
    return tag


def _ollama_tags_match(wanted: str, reported: str) -> bool:
    return _normalize_ollama_tag(wanted) == _normalize_ollama_tag(reported)


_ACTIVE_STATUSES = ("pending", "checking", "compatibility_check", "runtime_missing",
                    "downloading", "verifying", "starting_model", "health_check")
# Bounded resources: one multi-GB download at a time by default, bounded job history.
_MAX_CONCURRENT_JOBS = max(1, int(os.getenv("MODEL_PULL_MAX_CONCURRENT", "1")))
_MAX_JOB_HISTORY = max(10, int(os.getenv("MODEL_PULL_JOB_HISTORY", "50")))
_PERSIST_INTERVAL_SECONDS = 1.0


class ProvisioningJob:
    def __init__(self, job_id: str, model_id: str, status: str = "pending",
                 percent: float = 0.0, message: str = "", error: Optional[str] = None):
        self.job_id = job_id
        self.model_id = model_id
        self.status = status
        self.percent = percent
        self.message = message
        self.error = error
        self.created_at = datetime.utcnow().isoformat()
        self.completed_at: Optional[str] = None
        self.retries = 0
        self.bytes_completed: Optional[int] = None
        self.bytes_total: Optional[int] = None
        self.speed_mbps: Optional[float] = None
        self._last_saved = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "model_id": self.model_id,
            "status": self.status,
            "percent": self.percent,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "retries": self.retries,
            "bytes_completed": self.bytes_completed,
            "bytes_total": self.bytes_total,
            "speed_mbps": self.speed_mbps,
        }


class ModelProvisioningService:
    STATES = ["pending", "checking", "compatibility_check", "runtime_missing",
              "downloading", "verifying", "starting_model", "health_check", "ready", "failed", "cancelled"]

    def __init__(self, registry: Optional[ModelRegistry] = None,
                 hardware_detector: Optional[HardwareDetector] = None,
                 download_manager: Optional[ModelDownloadManager] = None,
                 db_path: Optional[str] = None):
        self.registry = registry or ModelRegistry()
        self.hw_detector = hardware_detector or HardwareDetector()
        self.download_manager = download_manager or ModelDownloadManager(self.registry)
        # PROVISIONING_DB_PATH lets Docker persist job history on the
        # sqlite-data named volume (/workspace/db). Falls back to the legacy
        # backend/provisioning.db location for native runs.
        default_db = os.path.join(os.path.dirname(__file__), "..", "..", "provisioning.db")
        self.db_path = db_path or os.getenv("PROVISIONING_DB_PATH", default_db)
        self._jobs: Dict[str, ProvisioningJob] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._init_db()
        self._load_jobs()

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS provisioning_jobs (
                    job_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    percent REAL DEFAULT 0.0,
                    message TEXT DEFAULT '',
                    error TEXT,
                    created_at TEXT,
                    completed_at TEXT
                )
            """)
            conn.commit()
            conn.close()
            logger.info(f"Provisioning DB initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to init provisioning DB: {e}")

    def _load_jobs(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT job_id, model_id, status, percent, message, error, created_at, completed_at "
                "FROM provisioning_jobs ORDER BY created_at DESC LIMIT ?", (_MAX_JOB_HISTORY,)
            )
            rows = list(reversed(cursor.fetchall()))
            for row in rows:
                job = ProvisioningJob(
                    job_id=row[0], model_id=row[1], status=row[2],
                    percent=row[3] or 0.0, message=row[4] or "", error=row[5]
                )
                job.created_at = row[6] or job.created_at
                job.completed_at = row[7]

                # If job was left in an active state when backend stopped, mark as failed/interrupted
                if job.status in ("pending", "checking", "compatibility_check", "runtime_missing",
                                  "downloading", "verifying", "starting_model", "health_check"):
                    job.status = "failed"
                    job.message = "Interrupted by system restart — ready to retry"
                    job.error = "Application restarted during provisioning"
                    job.completed_at = datetime.utcnow().isoformat()
                    self._save_job(job)

                self._jobs[job.job_id] = job
            conn.close()
            logger.info(f"Loaded {len(self._jobs)} provisioning jobs from DB")
        except Exception as e:
            logger.error(f"Failed to load provisioning jobs: {e}")

    def _save_job(self, job: ProvisioningJob):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO provisioning_jobs (job_id, model_id, status, percent, message, error, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (job.job_id, job.model_id, job.status, job.percent, job.message,
                  job.error, job.created_at, job.completed_at))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save job {job.job_id}: {e}")

    def _persist_job(self, job: ProvisioningJob, force: bool = False):
        """Keeps the in-memory view current; writes to disk at most once per second per job
        (progress lines arrive many times a second) unless the state change must be durable."""
        self._jobs[job.job_id] = job
        while len(self._jobs) > _MAX_JOB_HISTORY:
            oldest = next(iter(self._jobs))
            if self._jobs[oldest].status in _ACTIVE_STATUSES:
                break
            self._jobs.pop(oldest, None)
            self._tasks.pop(oldest, None)
        now = time.monotonic()
        if force or job.status not in ("downloading",) or now - job._last_saved >= _PERSIST_INTERVAL_SECONDS:
            job._last_saved = now
            self._save_job(job)

    def get_active_job(self) -> Optional[Dict[str, Any]]:
        """Returns the most relevant active or recently completed provisioning job."""
        for j in reversed(list(self._jobs.values())):
            if j.status in ("pending", "checking", "compatibility_check", "runtime_missing",
                            "downloading", "verifying", "starting_model", "health_check"):
                return j.to_dict()
        if self._jobs:
            return list(self._jobs.values())[-1].to_dict()
        return None

    async def provision(self, model_id: Optional[str] = None,
                        auto: bool = True,
                        hf_api_key: Optional[str] = None,
                        activate: bool = False) -> Dict[str, Any]:
        # Idempotency: If an active job for this model is already running, return it
        for existing_job in self._jobs.values():
            if existing_job.status in ("pending", "checking", "compatibility_check", "runtime_missing",
                                       "downloading", "verifying", "starting_model", "health_check"):
                if not model_id or existing_job.model_id == model_id:
                    return {
                        "job_id": existing_job.job_id,
                        "model_id": existing_job.model_id,
                        "status": existing_job.status,
                        "percent": existing_job.percent,
                        "message": f"Provisioning already in progress: {existing_job.message}",
                        "already_active": True
                    }

        if model_id:
            preflight = self.preflight(model_id)
            if not preflight["ok"]:
                return {"job_id": None, "status": "rejected", "message": preflight["message"], "already_active": False}

        active_count = sum(1 for j in self._jobs.values() if j.status in _ACTIVE_STATUSES)
        if active_count >= _MAX_CONCURRENT_JOBS:
            return {
                "job_id": None,
                "status": "rejected",
                "message": "Another model download is in progress. Wait for it to finish or cancel it first.",
                "already_active": False,
            }

        job_id = str(uuid.uuid4())
        job = ProvisioningJob(job_id=job_id, model_id=model_id or "", status="checking")
        self._persist_job(job, force=True)

        task = asyncio.create_task(self._run_provisioning(job, auto, hf_api_key, activate))
        self._tasks[job_id] = task
        return {"job_id": job_id, "status": "checking", "message": "Provisioning started"}

    def _resolve_entry(self, model_id: str) -> Optional[ModelEntry]:
        entry = self.registry.get(model_id)
        if entry:
            return entry
        for m in self.registry.all_models():
            if m.ollama_tag == model_id or m.model_id == model_id:
                return m
        return None

    def preflight(self, model_id: str) -> Dict[str, Any]:
        """Synchronous safety gate before any bytes are downloaded: trusted registry, memory fit, disk."""
        entry = self._resolve_entry(model_id)
        if not entry:
            return {"ok": False, "message": f"'{model_id}' is not in the trusted model registry; only registry models can be downloaded."}
        fit = self.registry.evaluate_model_fit(entry, self.hw_detector.detect())
        if fit["safety_tier"] == "UNSUPPORTED":
            return {"ok": False, "message": f"{entry.display_name} is too large for this machine: {fit['fit_reason']}"}
        storage_ok, storage_msg = self._check_storage(entry)
        if not storage_ok:
            return {"ok": False, "message": storage_msg}
        return {"ok": True, "message": "ok", "fit": fit}

    async def _run_provisioning(self, job: ProvisioningJob, auto: bool, hf_api_key: Optional[str], activate: bool = False):
        try:
            # Step 1: Hardware detection
            job.status = "checking"
            job.message = "Detecting hardware..."
            job.percent = 5.0
            self._persist_job(job)

            hw_profile = self.hw_detector.detect(force_refresh=True)
            logger.info(f"Hardware detected: {hw_profile.cpu_name}, {hw_profile.ram_total_gb}GB RAM, GPU={hw_profile.gpu_available}")

            # Step 2: Model selection
            job.status = "compatibility_check"
            job.message = "Selecting compatible model..."
            job.percent = 10.0
            self._persist_job(job)

            if auto and not job.model_id:
                tier_info = HardwareDetector.get_auto_selected_tier(hw_profile)
                recommended = self.registry.recommended_for(hw_profile, safe_only=True)
                if recommended:
                    selected = recommended[0]
                    job.model_id = selected.model_id
                    job.message = f"Auto-selected {selected.display_name} for {tier_info.get('tier_name', 'Tier 0')}"
                else:
                    job.status = "failed"
                    job.error = "No compatible models found for your hardware"
                    job.percent = 0.0
                    self._persist_job(job)
                    return
            else:
                entry = self.registry.get(job.model_id)
                if not entry:
                    for m in self.registry.all_models():
                        if m.ollama_tag == job.model_id or m.model_id == job.model_id:
                            entry = m
                            job.model_id = entry.model_id
                            break
                if not entry:
                    job.status = "failed"
                    job.error = f"Model '{job.model_id}' not found in registry"
                    self._persist_job(job)
                    return
                selected = entry

            entry = self.registry.get(job.model_id) or selected
            fit_eval = self.registry.evaluate_model_fit(entry, hw_profile)

            if fit_eval["safety_tier"] == "UNSUPPORTED":
                job.status = "failed"
                job.error = f"Model {entry.display_name} incompatible: {fit_eval['fit_reason']}"
                self._persist_job(job)
                return

            job.percent = 20.0
            job.message = f"Model compatible: {entry.display_name} ({fit_eval['fit_reason']})"
            self._persist_job(job)

            # Step 3: Idempotency check — is it already installed?
            job.status = "runtime_missing"
            job.message = "Checking if model is already installed..."
            job.percent = 25.0
            self._persist_job(job)

            installed = await self._check_installed(job.model_id)
            if installed:
                job.status = "verifying"
                job.message = "Model already installed — running health check..."
                job.percent = 70.0
                self._persist_job(job)
                health = await self._health_check(job.model_id)
                if health:
                    await self._maybe_activate(job, entry, activate)
                    job.status = "ready"
                    job.percent = 100.0
                    job.message = f"{entry.display_name} is already installed and healthy" + (" and active" if activate and not job.error else "")
                    job.completed_at = datetime.utcnow().isoformat()
                    self._persist_job(job, force=True)
                    return
                else:
                    job.message = "Model installed but unhealthy — re-pulling..."
                    job.percent = 25.0
                    self._persist_job(job)

            # Step 4: Storage validation
            job.status = "runtime_missing"
            job.message = "Validating storage..."
            job.percent = 30.0
            self._persist_job(job)

            storage_ok, storage_msg = self._check_storage(entry)
            if not storage_ok:
                job.status = "failed"
                job.error = storage_msg
                self._persist_job(job)
                return

            # Step 5: Pull model via Ollama
            job.status = "downloading"
            job.message = f"Downloading {entry.display_name}..."
            job.percent = 35.0
            self._persist_job(job)

            pull_ok = await self._pull_model(job, entry)
            if not pull_ok:
                job.status = "failed"
                job.error = f"Download failed for {entry.display_name}"
                self._persist_job(job)
                return

            # Step 6: Verify
            job.status = "verifying"
            job.message = "Verifying model integrity..."
            job.percent = 90.0
            self._persist_job(job)

            await asyncio.sleep(1.0)  # Brief pause for Ollama to index

            # Step 7: Health check
            job.status = "health_check"
            job.message = "Running health check..."
            job.percent = 95.0
            self._persist_job(job)

            health = await self._health_check(job.model_id)
            if not health:
                job.status = "failed"
                job.error = "Health check failed — model may not be functional"
                self._persist_job(job)
                return

            # Register with the runtime state and (optionally) make it the answering model.
            await self._maybe_activate(job, entry, activate)

            # Done
            job.status = "ready"
            job.percent = 100.0
            job.message = f"{entry.display_name} downloaded, verified and ready" + (" (active)" if activate and not job.error else "")
            job.completed_at = datetime.utcnow().isoformat()
            self._persist_job(job, force=True)

        except asyncio.CancelledError:
            job.status = "cancelled"
            job.message = "Provisioning cancelled by user"
            job.completed_at = datetime.utcnow().isoformat()
            self._persist_job(job)
        except Exception as e:
            logger.error(f"Provisioning error: {e}", exc_info=True)
            job.status = "failed"
            job.error = f"Unexpected provisioning error ({type(e).__name__})"
            job.message = "Provisioning failed. Check backend logs for details."
            self._persist_job(job, force=True)

    async def _check_installed(self, model_id: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.OLLAMA_URL}/api/tags")
                if resp.status_code == 200:
                    reported = [m.get("name", "") for m in resp.json().get("models", [])]
                    entry = self.registry.get(model_id)
                    candidates = [model_id]
                    if entry and entry.ollama_tag and entry.ollama_tag not in candidates:
                        candidates.append(entry.ollama_tag)
                    return any(
                        _ollama_tags_match(cand, name)
                        for cand in candidates
                        for name in reported
                    )
        except Exception as e:
            logger.debug(f"Idempotency check failed: {e}")
        return False

    def _check_storage(self, entry: ModelEntry) -> tuple[bool, str]:
        # Contract: required_gb = size_gb * 2.5 + 5.0 OS headroom.
        # The backend container cannot stat the ollama-models named volume
        # directly, so the host-disk free space visible here is used as proxy
        # (same Docker host disk backs both containers).
        try:
            usage = shutil.disk_usage(os.getenv("MODELS_DISK_PATH", os.getcwd()))
            free_bytes = getattr(usage, "free", None)
            if free_bytes is None:
                free_bytes = usage[2]
            free = free_bytes / (1024 ** 3)
            required = entry.size_gb * 2.5 + 5.0
            if free < required:
                return False, (
                    f"Insufficient storage: {free:.1f}GB free, need {required:.1f}GB "
                    f"to safely download {entry.display_name} (model + extraction + 5GB OS headroom). "
                    f"Free up space or stay on a smaller model."
                )
            return True, f"Storage OK: {free:.1f}GB free (requires {required:.1f}GB)"
        except Exception as e:
            # Cannot measure (e.g. path missing): do not block, but say so; the runtime reports disk-full itself.
            logger.warning("Storage check unavailable: %s", type(e).__name__)
            return True, "Storage check unavailable"

    async def _pull_model(self, job: ProvisioningJob, entry: ModelEntry) -> bool:
        """Streams an Ollama pull with bounded retries (Ollama resumes partial layers on retry)."""
        tag = entry.ollama_tag or entry.model_id
        max_attempts = max(1, int(os.getenv("MODEL_PULL_MAX_ATTEMPTS", "3")))
        backoff = float(os.getenv("MODEL_PULL_RETRY_BACKOFF_SECONDS", "5"))
        for attempt in range(1, max_attempts + 1):
            outcome = await self._pull_once(job, tag)
            if outcome == "success":
                if not await self._check_installed(tag):
                    logger.error("Pull stream finished but %s is not listed by the runtime", tag)
                    return False
                from app.runtime.model_state import model_state
                model_state.invalidate()
                return True
            if outcome == "fatal" or attempt == max_attempts:
                return False
            job.retries = attempt
            job.message = f"Network interruption; retrying download ({attempt}/{max_attempts - 1})..."
            self._persist_job(job, force=True)
            await asyncio.sleep(backoff * (2 ** (attempt - 1)))
        return False

    async def _pull_once(self, job: ProvisioningJob, tag: str) -> str:
        """Returns 'success', 'retryable' (network/5xx) or 'fatal' (4xx, e.g. unknown model)."""
        started = time.monotonic()
        try:
            timeout = httpx.Timeout(float(os.getenv("MODEL_PULL_TIMEOUT_SECONDS", "3600")), connect=settings.model.connect_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{settings.OLLAMA_URL}/api/pull",
                                         json={"name": tag, "stream": True}) as resp:
                    if resp.status_code != 200:
                        logger.error("Runtime pull failed: HTTP %s", resp.status_code)
                        return "fatal" if 400 <= resp.status_code < 500 else "retryable"
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except ValueError:
                            continue
                        if data.get("error"):
                            job.error = str(data["error"])[:300]
                            self._persist_job(job, force=True)
                            return "fatal"
                        status = data.get("status", "")
                        completed = data.get("completed", 0) or 0
                        total = data.get("total", 0) or 0
                        if total > 0:
                            job.percent = 35 + round((completed / total) * 55, 1)
                            elapsed = max(0.001, time.monotonic() - started)
                            job.bytes_completed = completed
                            job.bytes_total = total
                            job.speed_mbps = round((completed / elapsed) / (1024 * 1024), 2)
                        job.message = f"Pulling {tag}: {status}"
                        self._persist_job(job)
                        if status == "success":
                            return "success"
            logger.error("Runtime pull stream for %s ended without success status", tag)
            return "retryable"
        except asyncio.CancelledError:
            raise
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning("Pull attempt for %s interrupted: %s", tag, type(e).__name__)
            return "retryable"

    async def _maybe_activate(self, job: ProvisioningJob, entry: ModelEntry, activate: bool) -> None:
        if not activate:
            return
        from app.runtime.model_state import model_state, ModelNotAvailable
        job.status = "starting_model"
        job.message = "Loading model and activating..."
        self._persist_job(job, force=True)
        try:
            await model_state.activate(entry.ollama_tag or entry.model_id)
        except ModelNotAvailable as exc:
            job.error = f"Downloaded, but activation failed: {exc}"

    async def _health_check(self, model_id: str) -> bool:
        try:
            entry = self.registry.get(model_id)
            candidates = [model_id]
            if entry and entry.ollama_tag and entry.ollama_tag not in candidates:
                candidates.append(entry.ollama_tag)

            health_timeout = httpx.Timeout(settings.model.warmup_timeout_seconds, connect=settings.model.connect_timeout_seconds)
            async with httpx.AsyncClient(timeout=health_timeout) as client:
                for cand in candidates:
                    try:
                        resp = await client.post(
                            f"{settings.OLLAMA_URL}/api/generate",
                            json={"model": cand, "prompt": "ping", "stream": False, "options": {"num_predict": 1}},
                        )
                        if resp.status_code == 200:
                            return True
                    except Exception:
                        pass
                return False
        except Exception as e:
            logger.warning(f"Health check failed for {model_id}: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    def list_jobs(self) -> List[Dict[str, Any]]:
        return [j.to_dict() for j in self._jobs.values()]

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.status in ("pending", "checking", "compatibility_check", "runtime_missing",
                                   "downloading", "verifying", "starting_model", "health_check"):
            job.status = "cancelled"
            job.message = "Cancelled by user"
            job.completed_at = datetime.utcnow().isoformat()
            self._persist_job(job)

            # Abort active asyncio task if running
            task = self._tasks.get(job_id)
            if task and not task.done():
                task.cancel()
            return True
        return False

    async def stream_job_progress(self, job_id: str):
        """SSE progress: emits on change plus a periodic heartbeat, and always terminates."""
        last_payload = None
        last_sent = 0.0
        deadline = time.monotonic() + float(os.getenv("MODEL_PULL_TIMEOUT_SECONDS", "3600")) + 600
        while time.monotonic() < deadline:
            job = self._jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'job_id': job_id, 'status': 'not_found', 'error': 'Job not found'})}\n\n"
                return

            payload = json.dumps(job.to_dict())
            now = time.monotonic()
            if payload != last_payload or now - last_sent >= 10.0:
                yield f"data: {payload}\n\n"
                last_payload, last_sent = payload, now

            if job.status in ("ready", "failed", "cancelled"):
                return
            await asyncio.sleep(0.5)
        yield f"data: {json.dumps({'job_id': job_id, 'status': 'failed', 'error': 'Progress stream timed out'})}\n\n"

    async def search_hf_models(self, query: str = "legal gguf",
                               hf_api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search HuggingFace for GGUF model suggestions (read-only, no download)."""
        from app.network.mode_enforcer import mode_enforcer
        if mode_enforcer.is_offline():
            # OFFLINE means no outbound calls, including model-hub discovery.
            return []
        token = hf_api_key or getattr(settings, "HF_TOKEN", "") or os.getenv("HF_TOKEN", "")
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            from urllib.parse import quote_plus
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"https://huggingface.co/api/models?search={quote_plus(query[:100])}&limit=10"
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"HF search failed: HTTP {resp.status_code}")
                    return []

                results = []
                for item in resp.json():
                    filename = (item.get("filename") or "").lower()
                    if filename.endswith(".gguf") or "gguf" in item.get("tags", []):
                        results.append({
                            "model_id": item.get("id", ""),
                            "display_name": item.get("id", "").split("/")[-1],
                            "provider": "huggingface",
                            "size_gb": 0,
                            "ollama_tag": None,
                            "hf_repo": item.get("id", ""),
                            "gguf_filename": item.get("filename"),
                            "quantization": "gguf",
                            "tier": "standard"
                        })
                    elif filename.endswith(".safetensors") or "safetensors" in item.get("tags", []):
                        results.append({
                            "model_id": item.get("id", ""),
                            "display_name": item.get("id", "").split("/")[-1],
                            "provider": "huggingface",
                            "size_gb": 0,
                            "ollama_tag": None,
                            "hf_repo": item.get("id", ""),
                            "gguf_filename": None,
                            "quantization": "safetensors",
                            "tier": "standard"
                        })

                return results[:10]
        except Exception as e:
            logger.warning(f"HF search error: {e}")
            return []


_provisioning_service: Optional[ModelProvisioningService] = None


def get_provisioning_service() -> ModelProvisioningService:
    global _provisioning_service
    if _provisioning_service is None:
        _provisioning_service = ModelProvisioningService()
    return _provisioning_service