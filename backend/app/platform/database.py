from __future__ import annotations

from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=2)
def get_engine(database_url: str | None = None) -> Engine:
    return create_engine(
        database_url or settings.database_url,
        future=True,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=2)
def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(database_url),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection(database_url: str | None = None) -> bool:
    engine = get_engine(database_url)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
