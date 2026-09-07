import os
import logging
from typing import AsyncGenerator, Generator, Optional
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool

from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

# Determine active database URL
def get_db_url(async_driver: bool = True) -> str:
    url = settings.memory.postgres_url.strip()
    if not url:
        sqlite_path = settings.SQLITE_DB_PATH.replace("./", "")
        return f"sqlite+aiosqlite:///{sqlite_path}" if async_driver else f"sqlite:///{sqlite_path}"

    if async_driver:
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
    else:
        if url.startswith("postgresql+psycopg://"):
            url = url.replace("postgresql+psycopg://", "postgresql://", 1)
        elif url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


# Sync Engine & Session (for migrations, local dev, synchronous tasks)
_sync_engine = None
_sync_session_factory = None

def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        url = get_db_url(async_driver=False)
        is_sqlite = "sqlite" in url
        engine_kwargs = {
            "echo": False,
        }
        if is_sqlite:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            _sync_engine = create_engine(url, **engine_kwargs)
        else:
            engine_kwargs.update({
                "pool_size": 10,
                "max_overflow": 5,
                "pool_timeout": 3.0,
                "pool_pre_ping": True,
                "pool_recycle": 1800,
                "connect_args": {"connect_timeout": 2},
            })
            try:
                candidate = create_engine(url, **engine_kwargs)
                with candidate.connect() as conn:
                    conn.execute(text("SELECT 1"))
                _sync_engine = candidate
            except Exception as exc:
                logger.warning(f"PostgreSQL connection to {url} failed: {exc}. Falling back to SQLite local storage.")
                sqlite_path = settings.SQLITE_DB_PATH.replace("./", "")
                fallback_url = f"sqlite:///{sqlite_path}"
                _sync_engine = create_engine(fallback_url, connect_args={"check_same_thread": False}, echo=False)
        
        # Ensure schema tables exist
        try:
            Base.metadata.create_all(bind=_sync_engine)
            _auto_migrate_schema(_sync_engine)
        except Exception as e:
            logger.debug(f"Schema verification deferred: {e}")
    return _sync_engine


def _auto_migrate_schema(engine):
    """Ensures columns added in Phase 01 exist even if the SQLite database was already initialized."""
    with engine.connect() as conn:
        try:
            # Check conversations table
            res = conn.execute(text("PRAGMA table_info(conversations)")).fetchall()
            conv_cols = {row[1] for row in res}
            if conv_cols and "project_vault_id" not in conv_cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN project_vault_id VARCHAR(64)"))
                conn.commit()

            # Check messages table
            res = conn.execute(text("PRAGMA table_info(messages)")).fetchall()
            msg_cols = {row[1] for row in res}
            if msg_cols:
                if "citations_json" not in msg_cols:
                    conn.execute(text("ALTER TABLE messages ADD COLUMN citations_json JSON"))
                if "reasoning_trace" not in msg_cols:
                    conn.execute(text("ALTER TABLE messages ADD COLUMN reasoning_trace TEXT"))
                if "model_used" not in msg_cols:
                    conn.execute(text("ALTER TABLE messages ADD COLUMN model_used VARCHAR(64)"))
                if "runtime_used" not in msg_cols:
                    conn.execute(text("ALTER TABLE messages ADD COLUMN runtime_used VARCHAR(16)"))
                if "token_count" not in msg_cols:
                    conn.execute(text("ALTER TABLE messages ADD COLUMN token_count INTEGER"))
                if "grounding_score" not in msg_cols:
                    conn.execute(text("ALTER TABLE messages ADD COLUMN grounding_score FLOAT"))
                conn.commit()

            # Check document_memory table
            res = conn.execute(text("PRAGMA table_info(document_memory)")).fetchall()
            doc_cols = {row[1] for row in res}
            if doc_cols:
                if "project_vault_id" not in doc_cols:
                    conn.execute(text("ALTER TABLE document_memory ADD COLUMN project_vault_id VARCHAR(64)"))
                if "file_hash" not in doc_cols:
                    conn.execute(text("ALTER TABLE document_memory ADD COLUMN file_hash VARCHAR(64)"))
                if "vector_ns" not in doc_cols:
                    conn.execute(text("ALTER TABLE document_memory ADD COLUMN vector_ns VARCHAR(128)"))
                if "ingest_status" not in doc_cols:
                    conn.execute(text("ALTER TABLE document_memory ADD COLUMN ingest_status VARCHAR(32) DEFAULT 'ready'"))
                if "ingest_error" not in doc_cols:
                    conn.execute(text("ALTER TABLE document_memory ADD COLUMN ingest_error TEXT"))
                if "ingest_progress" not in doc_cols:
                    conn.execute(text("ALTER TABLE document_memory ADD COLUMN ingest_progress INTEGER DEFAULT 100"))
                conn.commit()
        except Exception as e:
            logger.debug(f"Auto-migration check non-fatal notice: {e}")


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
