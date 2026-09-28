"""
Statute library synchronisation.

The library is populated ONLY from the local statutory corpus (data/acts_raw + manifest.yaml)
via app.ingestion.statutory_corpus. There is no built-in list of statutes, sections,
penalties or case relationships: an empty corpus produces an empty library.
"""
import logging
import threading
from typing import Any, Dict

from app.ingestion.statutory_corpus import acts_dir, index_statutory_corpus

logger = logging.getLogger(__name__)


class StatuteSyncService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._auto_checked = False

    def sync_all_statutes(self) -> Dict[str, Any]:
        """(Re)indexes the local statutory corpus. Idempotent; serialised."""
        with self._lock:
            stats = index_statutory_corpus()
        return {
            "status": "success" if stats["acts_indexed"] else "empty_corpus",
            "statutes_synced": stats["acts_indexed"],
            "sections_synced": stats["sections_indexed"],
            **stats,
        }

    def auto_seed_if_empty(self) -> bool:
        """Indexes the corpus once per process when the library has no corpus-backed statutes."""
        if self._auto_checked:
            return False
        self._auto_checked = True
        try:
            import os
            from app.db.engine import get_sync_session
            from app.db.models import Statute
            from app.ingestion.statutory_corpus import CORPUS_SOURCE

            with get_sync_session() as session:
                has_corpus = session.query(Statute).filter(Statute.source == CORPUS_SOURCE).count() > 0
            directory = acts_dir()
            has_files = os.path.isdir(directory) and any(f.endswith(".txt") for f in os.listdir(directory))
            if not has_corpus and has_files:
                logger.info("Statute library empty; indexing local statutory corpus from %s", directory)
                self.sync_all_statutes()
                return True
        except Exception as exc:
            self._auto_checked = False
            logger.warning("Statute auto-index deferred: %s", type(exc).__name__)
        return False


statute_sync_service = StatuteSyncService()
