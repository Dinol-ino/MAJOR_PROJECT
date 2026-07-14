from __future__ import annotations

from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config

from app.config import settings


class PlatformBootstrapError(RuntimeError):
    pass


def ensure_database_exists() -> bool:
    admin_url = settings.postgres_admin_url
    database_name = settings.POSTGRES_DB

    with psycopg.connect(admin_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
            exists = cursor.fetchone() is not None
            if exists:
                return False
            cursor.execute(f'CREATE DATABASE "{database_name}"')
    return True


def run_migrations() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")
