import os
import time
import logging
import threading
from typing import Any, AsyncGenerator, Dict, Generator, Optional
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool

from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

class DatabaseUnavailableError(RuntimeError):
    """Raised when the configured database cannot be reached and fallback is not permitted."""


def _sqlite_url(async_driver: bool) -> str:
    sqlite_path = settings.SQLITE_DB_PATH.replace("./", "")
    return f"sqlite+aiosqlite:///{sqlite_path}" if async_driver else f"sqlite:///{sqlite_path}"


def _redact_url(url: str) -> str:
    """Never log credentials embedded in a database URL."""
    import re
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url)


# Determine active database URL
def get_db_url(async_driver: bool = True) -> str:
    """Normalizes the configured DATABASE_URL for the requested driver.

    An empty DATABASE_URL selects the local SQLite store explicitly. A configured
    PostgreSQL URL is never silently swapped for SQLite here; see get_sync_engine()
    and DB_ALLOW_SQLITE_FALLBACK for the (opt-in, logged) fallback policy.
    """
    url = settings.memory.postgres_url.strip()
    if not url:
        return _sqlite_url(async_driver)

    if async_driver:
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
    else:
        if url.startswith("postgresql+psycopg://"):
            url = url.replace("postgresql+psycopg://", "postgresql://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        elif url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


# Sync Engine & Session (for migrations, local dev, synchronous tasks)
_sync_engine = None
_sync_session_factory = None
_active_backend: Dict[str, Any] = {"backend": None, "fallback": False, "url": None}
_last_connect_failure: float = 0.0
_connect_lock = threading.Lock()


def _db_policy() -> Dict[str, Any]:
    return {
        "allow_sqlite_fallback": os.getenv("DB_ALLOW_SQLITE_FALLBACK", "false").lower() == "true",
        "connect_retries": max(1, int(os.getenv("DB_CONNECT_RETRIES", "3"))),
        "retry_backoff_seconds": float(os.getenv("DB_RETRY_BACKOFF_SECONDS", "1.0")),
        "retry_cooldown_seconds": float(os.getenv("DB_RETRY_COOLDOWN_SECONDS", "5.0")),
        "connect_timeout": int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")),
    }


def get_db_backend_info() -> Dict[str, Any]:
    """Which store is actually serving requests (surfaced by /health so a fallback is never silent)."""
    return dict(_active_backend)


def get_sync_engine():
    global _sync_engine, _last_connect_failure
    if _sync_engine is not None:
        return _sync_engine

    with _connect_lock:
        if _sync_engine is not None:
            return _sync_engine

        policy = _db_policy()
        now = time.time()
        if _last_connect_failure and now - _last_connect_failure < policy["retry_cooldown_seconds"]:
            raise DatabaseUnavailableError("Database unavailable (retry cooling down).")

        url = get_db_url(async_driver=False)
        engine = None
        if "sqlite" in url:
            engine = create_engine(url, connect_args={"check_same_thread": False}, echo=False)
            _active_backend.update({"backend": "sqlite", "fallback": False, "url": _redact_url(url)})
        else:
            engine_kwargs = {
                "echo": False,
                "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "5")),
                "pool_timeout": 3.0,
                "pool_pre_ping": True,
                "pool_recycle": 1800,
                "connect_args": {"connect_timeout": policy["connect_timeout"]},
            }
            last_exc: Optional[Exception] = None
            for attempt in range(policy["connect_retries"]):
                try:
                    candidate = create_engine(url, **engine_kwargs)
                    with candidate.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    engine = candidate
                    _active_backend.update({"backend": "postgresql", "fallback": False, "url": _redact_url(url)})
                    break
                except Exception as exc:  # bounded retry with backoff
                    last_exc = exc
                    if attempt < policy["connect_retries"] - 1:
                        time.sleep(policy["retry_backoff_seconds"] * (2 ** attempt))

            if engine is None:
                if policy["allow_sqlite_fallback"]:
                    fallback_url = _sqlite_url(async_driver=False)
                    logger.error(
                        "PostgreSQL at %s is unreachable (%s). DB_ALLOW_SQLITE_FALLBACK=true: serving from LOCAL SQLITE %s. "
                        "Data written now will NOT be in PostgreSQL.",
                        _redact_url(url), type(last_exc).__name__, fallback_url,
                    )
                    engine = create_engine(fallback_url, connect_args={"check_same_thread": False}, echo=False)
                    _active_backend.update({"backend": "sqlite", "fallback": True, "url": _redact_url(fallback_url)})
                else:
                    _last_connect_failure = time.time()
                    logger.error(
                        "PostgreSQL at %s is unreachable after %d attempt(s) (%s). Requests needing the database will return 503. "
                        "Fix DATABASE_URL, start PostgreSQL, or set DB_ALLOW_SQLITE_FALLBACK=true for local development.",
                        _redact_url(url), policy["connect_retries"], type(last_exc).__name__,
                    )
                    raise DatabaseUnavailableError("Configured PostgreSQL database is unreachable.") from last_exc

        # Ensure schema tables exist
        try:
            Base.metadata.create_all(bind=engine)
            _auto_migrate_schema(engine)
        except Exception as e:
            logger.warning("Schema verification deferred: %s", type(e).__name__)
        _last_connect_failure = 0.0
        _sync_engine = engine
    return _sync_engine


# Additive, idempotent column upgrades for databases created before a column existed.
# (create_all() creates missing tables but never adds columns to existing ones.)
_ADDITIVE_COLUMNS: Dict[str, Dict[str, str]] = {
    "conversations": {"project_vault_id": "VARCHAR(64)"},
    "messages": {
        "citations_json": "JSON",
        "reasoning_trace": "TEXT",
        "model_used": "VARCHAR(64)",
        "runtime_used": "VARCHAR(16)",
        "token_count": "INTEGER",
        "grounding_score": "FLOAT",
    },
    "project_vaults": {"deleted_at": "TIMESTAMP"},
    "document_memory": {
        "project_vault_id": "VARCHAR(64)",
        "file_hash": "VARCHAR(64)",
        "vector_ns": "VARCHAR(128)",
        "ingest_status": "VARCHAR(32) DEFAULT 'ready'",
        "ingest_error": "TEXT",
        "ingest_progress": "INTEGER DEFAULT 100",
        "storage_path": "VARCHAR(512)",
        "doc_type": "VARCHAR(32)",
        "parser_version": "VARCHAR(64)",
        "indexed_at": "TIMESTAMP",
    },
    "citation_edges": {"derivation_method": "VARCHAR(64) DEFAULT 'curated_legal_relationship'"},
    "statute_sections": {"cited_in_conversations": "INTEGER DEFAULT 0"},
    "statutes": {
        "source_url": "VARCHAR(512)",
        "source_version": "VARCHAR(256)",
        "publication_date": "VARCHAR(32)",
        "legal_status": "VARCHAR(32)",
        "content_hash": "VARCHAR(64)",
        "verified_at": "VARCHAR(32)",
    },
}


def _auto_migrate_schema(engine):
    """Adds missing columns on both SQLite and PostgreSQL (dialect-neutral via the inspector)."""
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDITIVE_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in present:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
                    logger.info("Schema upgrade: added %s.%s", table, name)


def get_sync_sessionmaker():
    global _sync_session_factory
    if _sync_session_factory is None:
        engine = get_sync_engine()
        _sync_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _sync_session_factory


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Context manager for synchronous database sessions with auto-rollback on error."""
    factory = get_sync_sessionmaker()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Async Engine & Session (for FastAPI routes & async workflows)
_async_engine = None
_async_session_factory = None

def get_async_engine():
    global _async_engine
    if _async_engine is None:
        sync_engine = get_sync_engine()
        if "sqlite" in str(sync_engine.url):
            url = _sqlite_url(async_driver=True)
            is_sqlite = True
        else:
            url = get_db_url(async_driver=True)
            is_sqlite = "sqlite" in url

        engine_kwargs = {
            "echo": False,
        }
        if is_sqlite:
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs.update({
                "pool_size": 10,
                "max_overflow": 5,
                "pool_timeout": 3.0,
                "pool_pre_ping": True,
                "pool_recycle": 1800,
                "connect_args": {"connect_timeout": 3},
            })
        _async_engine = create_async_engine(url, **engine_kwargs)
    return _async_engine


def get_async_sessionmaker():
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            bind=engine, 
            class_=AsyncSession, 
            expire_on_commit=False,
            autoflush=False
        )
    return _async_session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for DB transactions with explicit rollback boundaries."""
    factory = get_async_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db_schema(engine=None):
    """Initializes tables for SQLite / testing or startup environments."""
    if engine is None:
        engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")
