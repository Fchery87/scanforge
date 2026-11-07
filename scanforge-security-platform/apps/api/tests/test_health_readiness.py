from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1.routes.health import router
from app.db.session import get_db


@pytest.mark.asyncio
@pytest.mark.parametrize("available", [True, False])
async def test_readiness_reflects_database_connectivity_without_breaking_liveness(available):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    db = AsyncMock()
    if not available:
        db.execute.side_effect = ConnectionError("database unavailable: private-connection-details")

    async def session():
        yield db

    app.dependency_overrides[get_db] = session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        db.execute.assert_not_awaited()
        ready = await client.get("/api/v1/ready")
        assert ready.status_code == (200 if available else 503)
        assert ready.json() == {"status": "ready" if available else "unavailable"}
        db.execute.assert_awaited_once()
        assert str(db.execute.call_args.args[0]) == "SELECT 1"
        assert "private-connection-details" not in ready.text
