"""Alembic environment configured for SQLAlchemy 2.0 async engines.

Only the ``staging`` schema is version-controlled here -- the OMOP ``cdm``
schema is created/managed by dbt's table materializations (see
``docs/adr/0004-alembic-for-staging-dbt-for-omop.md``).
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.base import Base  # noqa: E402
from models.staging import (  # noqa: E402,F401
    EtlBatch,
    StagingCondition,
    StagingEncounter,
    StagingObservation,
    StagingPatient,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

DATABASE_URL = os.environ.get(
    "OMOP_DB_ASYNC_URL", "postgresql+asyncpg://omop:omop@localhost:5434/omop"
)


def include_name(name, type_, parent_names):
    """Only manage objects in the `staging` schema; leave `cdm` (dbt-owned) alone."""
    if type_ == "schema":
        return name in (None, "staging")
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema="staging",
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    # The `staging` schema must exist before Alembic can create its own
    # version-tracking table inside it.
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table_schema="staging",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        # Alembic's MigrationContext commits its own DDL transaction against
        # the sync connection facade, but the outer AsyncConnection still
        # thinks it holds an open transaction and will roll it back on close
        # unless we commit here explicitly.
        await connection.commit()

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
