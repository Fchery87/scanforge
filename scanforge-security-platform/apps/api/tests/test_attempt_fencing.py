"""P1.3 / #36: every worker write route fences stale attempts.

Seam: the HTTP routes under /api/v1/internal, authenticated with real worker
credentials against an in-memory database.  Each rejected write must leave
no rows behind.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.db.enums import ScanStatus
from app.db.models import Scan
from app.db.models.finding import Finding
from app.db.models.scan import ScannerRun
from app.db.session import get_db
from app.main import app
from app.middleware import redis_rate_limit as rate_limit
from app.services.worker_identities import WorkerIdentityService
from test_execution_context_identity import _seed_scan, db_session  # noqa: F401

PEPPER = "test-pepper"
CAPS = ["scans:read", "scans:write", "findings:write", "artifacts:write", "repositories:clone"]
FINDING = {"canonical_fingerprint": "fp-1", "title": "t"}


@pytest.fixture(autouse=True)
def _pepper(monkeypatch):
    monkeypatch.setattr(settings, "WORKER_CREDENTIAL_PEPPER", PEPPER)


@pytest.fixture
async def client(db_session):  # noqa: F811
    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    # The app's local rate limiter is process-global; these tests send many requests.
    rate_limit.LOCAL_STATE.store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    rate_limit.LOCAL_STATE.store.clear()


async def _worker(db, org_id):
    identity, credential = WorkerIdentityService(db, PEPPER).create_identity(
        organization_id=org_id, name=f"w-{uuid4()}", capabilities=CAPS
    )
    await db.commit()
    return identity, {"X-Worker-Credential": credential}


def _attempt_headers(ctx):
    return {
        "X-Scan-Attempt-Id": ctx["attempt_id"],
        "X-Scan-Execution-Revision": str(ctx["execution_revision"]),
        "X-Scan-Worker-Incarnation-Id": ctx["worker_incarnation_id"],
    }


async def _claim(client, scan, creds):
    response = await client.get(f"/api/v1/internal/scans/{scan.id}/execution-context", headers=creds)
    assert response.status_code == 200, response.text
    return response.json()


async def _counts(db):
    await db.commit()  # end any open snapshot; expire_on_commit is False
    counts = []
    for model in (ScannerRun, Finding):
        counts.append((await db.execute(select(func.count()).select_from(model))).scalar_one())
    return tuple(counts)


def _route_calls(scan_id, run_id, ctx):
    """route name -> (method, path, json)."""
    body_identity = {
        "attempt_id": ctx["attempt_id"],
        "execution_revision": ctx["execution_revision"],
        "worker_incarnation_id": ctx["worker_incarnation_id"],
    }
    base = f"/api/v1/internal/scans/{scan_id}"
    return {
        "status": ("PATCH", f"{base}/status", {"status": "running"}),
        "scanner_run_create": ("POST", f"{base}/scanner-runs", {"scanner_name": "semgrep"}),
        "scanner_run_update": ("PATCH", f"/api/v1/internal/scanner-runs/{run_id}", {"status": "completed"}),
        "findings": ("POST", f"{base}/findings", {"findings": [FINDING]}),
        "artifact_upload": (
            "POST",
            f"{base}/artifacts/upload-url",
            {"scanner_name": "semgrep", "filename": "out.json", "size_bytes": 10},
        ),
        "artifact_finalize": (
            "POST",
            f"{base}/artifacts/{uuid4()}/finalize",
            {"checksum_sha256": "0" * 64},
        ),
        "heartbeat": ("POST", f"{base}/heartbeat", body_identity),
    }


ROUTES = ["status", "scanner_run_create", "scanner_run_update", "findings", "artifact_upload", "artifact_finalize", "heartbeat"]


def _tamper(ctx, how):
    ctx = dict(ctx)
    if how == "stale_attempt":
        ctx["attempt_id"] = str(uuid4())
    elif how == "stale_revision":
        ctx["execution_revision"] += 1
    elif how == "replacement_incarnation":
        ctx["worker_incarnation_id"] = str(uuid4())
    return ctx


async def _send(client, route, scan_id, run_id, ctx, creds):
    method, path, body = _route_calls(scan_id, run_id, ctx)[route]
    headers = dict(creds)
    if route != "heartbeat":
        headers.update(_attempt_headers(ctx))
    return await client.request(method, path, json=body, headers=headers)


async def _live(client, db):
    scan, org_id = await _seed_scan(db)
    owner, creds = await _worker(db, org_id)
    ctx = await _claim(client, scan, creds)
    run = await client.post(
        f"/api/v1/internal/scans/{scan.id}/scanner-runs",
        json={"scanner_name": "trivy"},
        headers={**creds, **_attempt_headers(ctx)},
    )
    assert run.status_code == 200, run.text
    return scan, org_id, owner, creds, ctx, run.json()["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("how", ["stale_attempt", "stale_revision", "replacement_incarnation"])
async def test_superseded_identity_is_rejected_on_every_write_route(client, db_session, route, how):  # noqa: F811
    scan, _org, _owner, creds, ctx, run_id = await _live(client, db_session)
    before = await _counts(db_session)

    response = await _send(client, route, scan.id, run_id, _tamper(ctx, how), creds)

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "stale_attempt"
    assert await _counts(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ROUTES)
async def test_non_owner_principal_is_rejected_on_every_write_route(client, db_session, route):  # noqa: F811
    scan, org_id, _owner, _creds, ctx, run_id = await _live(client, db_session)
    _other, other_creds = await _worker(db_session, org_id)
    before = await _counts(db_session)

    response = await _send(client, route, scan.id, run_id, ctx, other_creds)

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "stale_worker"
    assert await _counts(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ROUTES)
async def test_disabled_principal_is_rejected_on_every_write_route(client, db_session, route):  # noqa: F811
    scan, _org, owner, creds, ctx, run_id = await _live(client, db_session)
    await WorkerIdentityService(db_session, PEPPER).disable_identity(UUID(str(owner.id)))
    before = await _counts(db_session)

    response = await _send(client, route, scan.id, run_id, ctx, creds)

    assert response.status_code == 401, response.text
    assert await _counts(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("terminal", [ScanStatus.COMPLETED, ScanStatus.CANCELED])
async def test_terminal_scan_rejects_writes_even_with_unexpired_lease(client, db_session, route, terminal):  # noqa: F811
    scan, _org, _owner, creds, ctx, run_id = await _live(client, db_session)
    stored = await db_session.get(Scan, str(scan.id))
    stored.status = terminal
    await db_session.commit()
    before = await _counts(db_session)

    response = await _send(client, route, scan.id, run_id, ctx, creds)

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "scan_terminal"
    assert await _counts(db_session) == before


@pytest.mark.asyncio
async def test_completion_rejects_stale_identity_and_writes_nothing(client, db_session):  # noqa: F811
    scan, _org, _owner, creds, ctx, _run = await _live(client, db_session)
    stale = _tamper(ctx, "stale_attempt")
    before = await _counts(db_session)

    response = await client.post(
        f"/api/v1/internal/scans/{scan.id}/complete",
        json={
            "winning_attempt_id": stale["attempt_id"],
            "execution_revision": stale["execution_revision"],
            "worker_incarnation_id": stale["worker_incarnation_id"],
            "findings": [],
            "scanner_runs": [{"scanner_name": "trivy", "status": "completed", "exit_code": 0}],
            "summary_json": {"seen_fingerprints": [], "scanner_health": {"complete": True}},
        },
        headers=creds,
    )

    assert response.status_code == 409, response.text
    assert await _counts(db_session) == before


# --- context refetch never adopts successor authority -----------------------


@pytest.mark.asyncio
async def test_refetch_with_matching_identity_is_idempotent(client, db_session):  # noqa: F811
    scan, _org, _owner, creds, ctx, _run = await _live(client, db_session)

    again = await client.get(
        f"/api/v1/internal/scans/{scan.id}/execution-context",
        headers={**creds, **_attempt_headers(ctx)},
    )

    assert again.status_code == 200
    assert again.json()["attempt_id"] == ctx["attempt_id"]
    assert again.json()["worker_incarnation_id"] == ctx["worker_incarnation_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("how", ["stale_attempt", "stale_revision", "replacement_incarnation"])
async def test_refetch_with_superseded_identity_is_refused_without_leaking_authority(client, db_session, how):  # noqa: F811
    scan, _org, _owner, creds, ctx, _run = await _live(client, db_session)

    response = await client.get(
        f"/api/v1/internal/scans/{scan.id}/execution-context",
        headers={**creds, **_attempt_headers(_tamper(ctx, how))},
    )

    assert response.status_code == 409
    assert ctx["worker_incarnation_id"] not in response.text
    assert ctx["attempt_id"] not in response.text
    stored = await db_session.get(Scan, str(scan.id))
    await db_session.refresh(stored)
    assert stored.current_attempt_id == ctx["attempt_id"]


@pytest.mark.asyncio
async def test_same_principal_refetch_without_identity_cannot_adopt_live_attempt(client, db_session):  # noqa: F811
    """A restarted process of the same principal shows no identity; it must
    wait for lease expiry rather than inherit the live incarnation."""
    scan, _org, _owner, creds, ctx, _run = await _live(client, db_session)

    response = await client.get(f"/api/v1/internal/scans/{scan.id}/execution-context", headers=creds)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "lease_active"
    assert ctx["worker_incarnation_id"] not in response.text


@pytest.mark.asyncio
async def test_superseded_holder_refetch_does_not_take_over_successor(client, db_session):  # noqa: F811
    scan, org_id, _owner, old_creds, old_ctx, _run = await _live(client, db_session)
    stored = await db_session.get(Scan, str(scan.id))
    stored.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    _succ, succ_creds = await _worker(db_session, org_id)
    successor = await _claim(client, scan, succ_creds)

    refetch = await client.get(
        f"/api/v1/internal/scans/{scan.id}/execution-context",
        headers={**old_creds, **_attempt_headers(old_ctx)},
    )

    assert refetch.status_code == 409
    assert successor["attempt_id"] not in refetch.text
    stored = await db_session.get(Scan, str(scan.id))
    await db_session.refresh(stored)
    assert stored.current_attempt_id == successor["attempt_id"]
    method, path, body = _route_calls(scan.id, uuid4(), old_ctx)["findings"]
    write = await client.request(method, path, json=body, headers={**old_creds, **_attempt_headers(old_ctx)})
    assert write.status_code == 409
