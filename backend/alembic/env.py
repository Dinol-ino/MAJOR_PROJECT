import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import Base
from app.db.engine import get_db_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_db_url(async_driver=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_db_url(async_driver=False)
    connectable = config.attributes.get("connection", None)

    if connectable is None:
        from sqlalchemy import create_engine
        connectable = create_engine(url, poolclass=pool.NullPool)

        with connectable.connect() as connection:
            context.configure(
                connection=connection, 
                target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(
            connection=connectable, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
