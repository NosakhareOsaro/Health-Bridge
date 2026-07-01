"""SQLAlchemy 2.0 declarative base and async engine/session factory for the ETL's staging layer.

Only the ``staging`` schema is modeled/migrated here with SQLAlchemy + Alembic.
The ``cdm`` (OMOP) schema is owned and materialized by dbt -- see
``services/etl/dbt_omop`` and ``docs/adr`` for why responsibility is split
this way.
"""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

OMOP_DB_URL = os.environ.get(
    "OMOP_DB_ASYNC_URL", "postgresql+asyncpg://omop:omop@localhost:5434/omop"
)


class Base(DeclarativeBase):
    pass


def get_engine(url: str = OMOP_DB_URL) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def get_sessionmaker(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine or get_engine(), expire_on_commit=False)
