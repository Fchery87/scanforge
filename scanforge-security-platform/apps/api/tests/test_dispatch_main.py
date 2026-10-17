from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app import dispatch_main


@pytest.mark.asyncio
async def test_dispatch_due_scans_claims_a_bounded_batch(monkeypatch):
    session = object()
    entered = False

    @asynccontextmanager
    async def session_factory():
        nonlocal entered
        entered = True
        yield session

    class FakeDispatcher:
        def __init__(self, received_session, *, queue):
            assert received_session is session
            assert queue is marker_queue

        async def dispatch_due_obligations(self, *, lease_owner, limit):
            assert lease_owner.startswith("api-dispatcher-")
            assert limit == 7
            return [SimpleNamespace(dispatched=True), SimpleNamespace(dispatched=False)]

    marker_queue = object()
    monkeypatch.setattr(dispatch_main, "ScanDispatchService", FakeDispatcher)

    dispatched = await dispatch_main.dispatch_due_scans(
        session_factory=session_factory,
        queue=marker_queue,
        limit=7,
    )

    assert entered
    assert dispatched == 1


@pytest.mark.asyncio
async def test_dispatch_due_scans_returns_zero_when_no_obligations_are_due(monkeypatch):
    @asynccontextmanager
    async def session_factory():
        yield object()

    class FakeDispatcher:
        def __init__(self, _session, *, queue):
            pass

        async def dispatch_due_obligations(self, **_kwargs):
            return []

    monkeypatch.setattr(dispatch_main, "ScanDispatchService", FakeDispatcher)

    assert await dispatch_main.dispatch_due_scans(session_factory=session_factory) == 0
