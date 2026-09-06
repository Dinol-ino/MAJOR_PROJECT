"""
Phase 12 — Eval Run Store.
SQLite-backed persistence for per-category eval scores across runs.
Enables trend tracking: score per category per git commit.
No Postgres required — uses a local SQLite file in the backend directory.
"""
import os
import uuid
import sqlite3
import subprocess
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Store path adjacent to audit_log.db in the backend directory
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "eval_runs.db",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS eval_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    git_commit  TEXT,
    category    TEXT NOT NULL,
    score       REAL NOT NULL DEFAULT 0.0,
    pass_count  INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'PASS',
    details_json TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_eval_runs_run_id ON eval_runs(run_id);
CREATE INDEX IF NOT EXISTS ix_eval_runs_category ON eval_runs(category);
"""


def _get_git_commit() -> Optional[str]:
    """Returns short HEAD commit hash, or None if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


class EvalRunStore:
    """
    Lightweight SQLite store for eval run history.
    Thread-safe via WAL mode; no async required for CI tooling.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
        except Exception as e:
            logger.error(f"EvalRunStore schema init failed: {e}")

    def save_category_result(
        self,
        run_id: str,
        category: str,
        score: float,
        pass_count: int,
        total_count: int,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        git_commit: Optional[str] = None,
    ) -> None:
        """Persists one category result row for the given run."""
        import json
        commit = git_commit or _get_git_commit()
        now = datetime.utcnow().isoformat()
        details_json = json.dumps(details) if details else None
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO eval_runs
                      (run_id, git_commit, category, score, pass_count, total_count, status, details_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, commit, category, round(score, 4), pass_count, total_count, status, details_json, now),
                )
        except Exception as e:
            logger.error(f"EvalRunStore.save_category_result failed: {e}")

    def get_trend(self, category: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns the N most recent runs for a given category (newest first)."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT run_id, git_commit, score, pass_count, total_count, status, created_at
                    FROM eval_runs
                    WHERE category = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (category, limit),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"EvalRunStore.get_trend failed: {e}")
            return []

    def get_run_summary(self, run_id: str) -> List[Dict[str, Any]]:
        """Returns all category results for a single run."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM eval_runs WHERE run_id = ? ORDER BY category",
                    (run_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"EvalRunStore.get_run_summary failed: {e}")
            return []


def new_run_id() -> str:
    """Generates a fresh UUID run ID for a complete eval run."""
    return str(uuid.uuid4())


# Module-level singleton — eval tools import this directly
eval_run_store = EvalRunStore()
