from pathlib import Path
import os
import uuid

from dotenv import load_dotenv
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


class Settings(BaseModel):
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:3b")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./audit_log.db")
    MAX_FILE_SIZE_MB: int = _env_int("MAX_FILE_SIZE_MB", 10)
    MAX_FILE_PAGES: int = _env_int("MAX_FILE_PAGES", 100)

    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = _env_int("POSTGRES_PORT", 5432)
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "dfrag")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    PGVECTOR_DIMENSIONS: int = _env_int("PGVECTOR_DIMENSIONS", 1024)

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SESSION_TTL_SECONDS: int = _env_int("SESSION_TTL_SECONDS", 7200)

    CHROMA_LEGACY_ENABLED: bool = _env_bool("CHROMA_LEGACY_ENABLED", True)

    UPLOAD_ROOT: str = os.getenv("UPLOAD_ROOT", "./data/uploads")
    DEFAULT_WORKSPACE_ID: str = os.getenv(
        "DEFAULT_WORKSPACE_ID",
        "00000000-0000-0000-0000-000000000001",
    )
    OCR_ENABLED: bool = _env_bool("OCR_ENABLED", False)
    OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "en")
    OCR_MIN_TEXT_THRESHOLD: float = _env_float("OCR_MIN_TEXT_THRESHOLD", 0.15)

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_admin_url(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/postgres"
        )

    @property
    def default_workspace_uuid(self) -> uuid.UUID:
        return uuid.UUID(self.DEFAULT_WORKSPACE_ID)


settings = Settings()
