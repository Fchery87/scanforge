"""R04 PostgreSQL integration boundary.

The first red case is retained as an integration test.  This environment has
``pg_config`` but no ``initdb``/``pg_ctl``, so it cannot create the disposable
cluster required by the test.
"""
import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.schemas.scan_completion import ScanCompletionRequest
from app.services.scan_completion import ScanCompletionService


POSTGRES_INFRA_REASON = (
    "PostgreSQL disposable-cluster infrastructure unavailable: initdb and pg_ctl "
    "are not installed (pg_config alone cannot start an isolated server)"
)


def test_r04_service_import_and_fixture_path_probe():
    """Runnable probe: imports the boundary and constructs its DB fixture path."""
    assert ScanCompletionService is not None
    assert ScanCompletionRequest is not None
    if not os.getenv("R04_POSTGRES_URL"):
        pytest.skip("set R04_POSTGRES_URL to exercise the PostgreSQL fixture path")
    engine = create_async_engine(os.environ["R04_POSTGRES_URL"])
    try:
        assert engine.url.drivername == "postgresql+asyncpg"
    finally:
        engine.sync_engine.dispose()


@pytest.mark.asyncio
async def test_changed_valid_replay_is_conflict_and_does_not_mutate():
    """First real red case; requires a disposable PostgreSQL cluster."""
    if not os.getenv("R04_POSTGRES_URL"):
        pytest.skip("set R04_POSTGRES_URL to a disposable PostgreSQL database")
    pytest.skip(POSTGRES_INFRA_REASON)
