import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

OMOP_DB_URL = os.environ.get("OMOP_DB_URL", "postgresql://omop:omop@localhost:5434/omop")


@pytest.fixture(scope="session")
def live_engine() -> Engine:
    """A real engine against the OMOP CDM Postgres, skipping tests if it's unreachable.

    These are integration tests against services/etl's output (a live
    docker-compose omop-db with the dbt models already run), not unit tests
    against mocks -- see the analytics service README for how to bring that
    stack up before running this suite.
    """
    engine = create_engine(OMOP_DB_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"OMOP CDM database not reachable at {OMOP_DB_URL}: {exc}")
    return engine
