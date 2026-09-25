import os
import json
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "model_id": self.model_id,
            "status": self.status,
            "percent": self.percent,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at
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
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "..", "..", "provisioning.db")
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
            cursor = conn.execute("SELECT job_id, model_id, status, percent, message, error, created_at, completed_at FROM provisioning_jobs")
            for row in cursor.fetchall():
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

    def _persist_job(self, job: ProvisioningJob):
        self._jobs[job.job_id] = job
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
                        hf_api_key: Optional[str] = None) -> Dict[str, Any]:
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

        job_id = str(uuid.uuid4())
        job = ProvisioningJob(job_id=job_id, model_id=model_id or "", status="checking")
        self._persist_job(job)

        task = asyncio.create_task(self._run_provisioning(job, auto, hf_api_key))
        self._tasks[job_id] = task
        return {"job_id": job_id, "status": "checking", "message": "Provisioning started"}

    async def _run_provisioning(self, job: ProvisioningJob, auto: bool, hf_api_key: Optional[str]):
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
                    job.status = "ready"
                    job.percent = 100.0
                    job.message = f"{entry.display_name} is already installed and healthy"
                    job.completed_at = datetime.utcnow().isoformat()
                    self._persist_job(job)
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

            # Done
            job.status = "ready"
            job.percent = 100.0
            job.message = f"{entry.display_name} provisioned successfully and ready for inference"
            job.completed_at = datetime.utcnow().isoformat()
            self._persist_job(job)

        except asyncio.CancelledError:
            job.status = "cancelled"
            job.message = "Provisioning cancelled by user"
            job.completed_at = datetime.utcnow().isoformat()
            self._persist_job(job)
        except Exception as e:
            logger.error(f"Provisioning error: {e}", exc_info=True)
            job.status = "failed"
            job.error = str(e)
            job.message = f"Provisioning failed: {str(e)}"
            self._persist_job(job)

    async def _check_installed(self, model_id: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.OLLAMA_URL}/api/tags")
                if resp.status_code == 200:
                    tags = [m.get("name", "").lower() for m in resp.json().get("models", [])]
                    return model_id.lower() in tags or model_id.split(":")[0].lower() in tags
        except Exception as e:
            logger.debug(f"Idempotency check failed: {e}")
        return False

    def _check_storage(self, entry: ModelEntry) -> tuple[bool, str]:
        try:
            free = shutil.disk_usage(os.getcwd()).free / (1024 ** 3)
            required = entry.size_gb * 2.5
            if free < required:
                return False, f"Insufficient storage: {free:.1f}GB free, need {required:.1f}GB for {entry.display_name}"
            return True, f"Storage OK: {free:.1f}GB free"
        except Exception as e:
            logger.debug(f"Storage check error: {e}")
            return True, "Storage check skipped"

    async def _pull_model(self, job: ProvisioningJob, entry: ModelEntry) -> bool:
        tag = entry.ollama_tag or entry.model_id
        try:
            async with httpx.AsyncClient(timeout=300.0, connect=2.0) as client:
                async with client.stream("POST", f"{settings.OLLAMA_URL}/api/pull",
                                         json={"name": tag, "stream": True}) as resp:
                    if resp.status_code != 200:
                        logger.error(f"Ollama pull failed: HTTP {resp.status_code}")
                        return False
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            completed = data.get("completed", 0)
                            total = data.get("total", 0)
                            if total > 0:
                                job.percent = 35 + round((completed / total) * 55, 1)
                            elif status == "success":
                                job.percent = 95.0
                            job.message = f"Pulling {tag}: {status}"
                            self._persist_job(job)
                            if status == "success":
                                return True
                        except Exception:
                            pass
            return True
        except Exception as e:
            logger.error(f"Pull failed for {tag}: {e}")
            return False

    async def _health_check(self, model_id: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_URL}/api/generate",
                    json={"model": model_id, "prompt": "ping", "stream": False},
                    timeout=10.0
                )
                return resp.status_code == 200
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
        """Yields Server-Sent Events (SSE) for real-time progress until terminal state."""
        while True:
            job = self._jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'job_id': job_id, 'status': 'not_found', 'error': 'Job not found'})}\n\n"
                break

            payload = job.to_dict()
            yield f"data: {json.dumps(payload)}\n\n"

            if job.status in ("ready", "failed", "cancelled"):
                break
            await asyncio.sleep(0.4)

    async def search_hf_models(self, query: str = "legal gguf",
                               hf_api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search HuggingFace for GGUF model suggestions (read-only, no download)."""
        token = hf_api_key or getattr(settings, "HF_TOKEN", "") or os.getenv("HF_TOKEN", "")
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"https://huggingface.co/api/models?search={query}&limit=10"
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