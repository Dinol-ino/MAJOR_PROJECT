import uuid
import asyncio
import logging
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.system.model_registry import ModelRegistry, ModelEntry

logger = logging.getLogger(__name__)

class ModelDownloadManager:
    """
    Manages non-blocking model pulls from Ollama or external sources.
    Tracks progress per task_id in memory.
    """
    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or ModelRegistry()
        self._tasks: Dict[str, Dict[str, Any]] = {}

    async def pull(self, model_id: str) -> str:
        entry = self.registry.get(model_id)
        tag = entry.ollama_tag if (entry and entry.ollama_tag) else model_id

        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "task_id": task_id,
            "model_id": model_id,
            "status": "starting",
            "percent": 0.0,
            "bytes_downloaded": 0,
            "total_bytes": 0,
            "error": None
        }

        asyncio.create_task(self._run_ollama_pull(task_id, tag))
        return task_id

    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)

    async def _run_ollama_pull(self, task_id: str, tag: str):
        url = f"{settings.OLLAMA_URL.rstrip('/')}/api/pull"
        payload = {"name": tag, "stream": True}
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        self._tasks[task_id]["status"] = "error"
                        self._tasks[task_id]["error"] = f"HTTP {response.status_code}: {response.reason_phrase}"
                        return

                    self._tasks[task_id]["status"] = "downloading"
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            import json
                            data = json.loads(line)
                            status_text = data.get("status", "")
                            completed = data.get("completed", 0)
                            total = data.get("total", 0)

                            if total > 0:
                                percent = round((completed / total) * 100.0, 2)
                                self._tasks[task_id]["percent"] = percent
                                self._tasks[task_id]["bytes_downloaded"] = completed
                                self._tasks[task_id]["total_bytes"] = total

                            if status_text == "success":
                                self._tasks[task_id]["status"] = "done"
                                self._tasks[task_id]["percent"] = 100.0
                                return
                        except Exception:
                            pass

            self._tasks[task_id]["status"] = "done"
            self._tasks[task_id]["percent"] = 100.0
        except Exception as exc:
            logger.error(f"Download failed for task {task_id}: {exc}")
            self._tasks[task_id]["status"] = "error"
            self._tasks[task_id]["error"] = str(exc)
