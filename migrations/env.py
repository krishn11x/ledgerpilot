"""Alembic migration environment.

Reads the database URL from LedgerPilot settings rather than alembic.ini, so
credentials live only in ``.env`` and never in a committed file.

``render_as_batch`` is enabled because SQLite cannot ALTER columns in place.
With it, the same migration scripts apply to both SQLite (local dev) and
PostgreSQL (deployment) -- which is what "PostgreSQL-ready" has to mean in
practice.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from ledgerpilot.config import settings
from ledgerpilot.store import tables  # noqa: F401  -- registers mappers
from ledgerpilot.store.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect and run migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
