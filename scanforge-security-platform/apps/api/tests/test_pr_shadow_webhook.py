"""Signed-fixture style webhook ingress tests for shadow PR analysis (#46).

Signature verification is stubbed exactly as in test_webhook_route_security.py (the
verifier itself is covered by test_webhook_verification.py); live GitHub App delivery
was NOT run.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from app.api.v1.routes import webhooks
from app.core.config import settings
from app.db.models import RepositoryIntegration, Scan, WebhookDelivery

BASE = "b" * 40
HEAD = "a" * 40
MERGE_BASE = "d" * 40


class _Request:
    def __init__(self, payload, *, delivery="delivery-1", event="pull_request"):
        self._payload = payload
        self.headers = {"x-github-event": event, "x-github-delivery": delivery}

    async def json(self):
        return self._payload


class _FakeGitHub:
    calls: list[tuple] = []
    result: dict = {"status": "ahead", "merge_base_sha": MERGE_BASE}

    def __init__(self, _db):
        pass

    async def compare_commits(self, installation_id, owner, repo, base_sha, head_sha):
        type(self).calls.append((installation_id, owner, repo, base_sha, head_sha))
        return dict(type(self).result)


def _payload(
    repo, *, action="opened", head_repo="acme/core-platform", head_sha=HEAD, number=17, updated_at=None
):
    return {
        "action": action,
        "pull_request": {
            "number": number,
            **({"updated_at": updated_at} if updated_at else {}),
            "head": {
                "sha": head_sha,
                "ref": "main",
                "repo": {"full_name": head_repo, "id": 7} if head_repo else None,
            },
            "base": {"sha": BASE, "ref": "main", "repo": {"full_name": "acme/core-platform", "id": 42}},
        },
        "repository": {"full_name": repo.full_name, "id": int(repo.external_repo_id)},
        "installation": {"id": 99},
    }


@pytest.fixture
def dispatch_calls(monkeypatch):
    calls: list[str] = []

    class _Dispatch:
        def __init__(self, _db, **_kw):
            pass

        async def dispatch_for_scan(self, scan_id):
            calls.append(str(scan_id))

    monkeypatch.setattr(webhooks, "ScanDispatchService", _Dispatch)
    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))
    monkeypatch.setattr(webhooks, "GitHubService", _FakeGitHub)
    _FakeGitHub.calls = []
    _FakeGitHub.result = {"status": "ahead", "merge_base_sha": MERGE_BASE}
    return calls


async def _seed(db_session):
    org, project, repo, _user = await _seed_org_project_repo(db_session)
    repo.external_repo_id = "42"
    db_session.add(RepositoryIntegration(repository_id=repo.id, installation_id="99"))
    await db_session.commit()
    return org, project, repo


async def _deliver(db_session, org, project, repo, payload, **kw):
    return await webhooks.github_webhook(
        org_id=org.id,
        project_id=project.id,
        repository_id=repo.id,
        request=_Request(payload, **kw),
        db=db_session,
    )


async def _scans(db_session):
    return (await db_session.execute(select(Scan))).scalars().all()


@pytest.mark.asyncio
async def test_pr_event_creates_no_run_while_pr_shadow_is_off(db_session, dispatch_calls):
    org, project, repo = await _seed(db_session)

    response = await _deliver(db_session, org, project, repo, _payload(repo))

    assert response == {"status": "ignored", "event": "pull_request"}
    assert await _scans(db_session) == []
    assert _FakeGitHub.calls == []
    assert dispatch_calls == []


@pytest.mark.asyncio
async def test_pr_event_for_another_organization_creates_no_run(db_session, dispatch_calls, monkeypatch):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", "11111111-1111-1111-1111-111111111111")

    response = await _deliver(db_session, org, project, repo, _payload(repo))

    assert response["status"] == "ignored"
    assert await _scans(db_session) == []


@pytest.mark.asyncio
async def test_pr_event_records_base_head_and_merge_base_when_pr_shadow_is_on(
    db_session, dispatch_calls, monkeypatch
):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org.id))

    response = await _deliver(db_session, org, project, repo, _payload(repo))

    (scan,) = await _scans(db_session)
    assert response == {"status": "queued", "scan_id": str(scan.id), "mode": "shadow"}
    assert (scan.commit_sha, scan.base_sha, scan.merge_base_sha) == (HEAD, BASE, MERGE_BASE)
    assert scan.comparison_strategy == "head_vs_merge_base"
    assert scan.scan_type == "full"
    assert scan.pull_request_number == 17
    assert scan.head_is_fork is False
    assert _FakeGitHub.calls == [("99", "acme", "core-platform", BASE, HEAD)]
    assert dispatch_calls == [str(scan.id)]
    delivery = (await db_session.execute(select(WebhookDelivery))).scalar_one()
    assert str(delivery.scan_id) == str(scan.id)


@pytest.mark.asyncio
async def test_shadow_response_carries_no_publication_payload(db_session, dispatch_calls, monkeypatch):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org.id))
    advisory = AsyncMock(side_effect=AssertionError("advisory payload must not be built for shadow runs"))
    monkeypatch.setattr(webhooks, "build_pr_advisory_payload", advisory)

    response = await _deliver(db_session, org, project, repo, _payload(repo))

    assert "advisory" not in response
    advisory.assert_not_called()


@pytest.mark.asyncio
async def test_pr_shadow_does_not_depend_on_or_enable_pr_review(db_session, dispatch_calls, monkeypatch):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org.id))
    lifecycle = AsyncMock(side_effect=AssertionError("pr_review path must stay unreachable"))
    monkeypatch.setattr(webhooks, "ScanLifecycleService", lifecycle)

    await _deliver(db_session, org, project, repo, _payload(repo))

    lifecycle.assert_not_called()


@pytest.mark.asyncio
async def test_fork_pr_is_marked_fork_and_missing_head_repository_counts_as_fork(
    db_session, dispatch_calls, monkeypatch
):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org.id))

    await _deliver(db_session, org, project, repo, _payload(repo, head_repo="evil/core-platform"), delivery="d-fork")
    await _deliver(
        db_session, org, project, repo, _payload(repo, head_repo=None, number=18, head_sha="e" * 40), delivery="d-gone"
    )

    scans = {s.pull_request_number: s for s in await _scans(db_session)}
    assert scans[17].head_is_fork is True
    assert scans[18].head_is_fork is True


@pytest.mark.asyncio
async def test_unresolved_merge_base_is_recorded_as_unknown_and_run_still_created(
    db_session, dispatch_calls, monkeypatch
):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org.id))
    _FakeGitHub.result = {"status": "unknown", "base_sha": BASE, "head_sha": HEAD, "http_status": 502}

    await _deliver(db_session, org, project, repo, _payload(repo))

    (scan,) = await _scans(db_session)
    assert scan.merge_base_sha is None
    assert scan.commit_sha == HEAD


@pytest.mark.asyncio
async def test_redelivery_under_a_new_delivery_id_does_not_duplicate_the_run(
    db_session, dispatch_calls, monkeypatch
):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org.id))

    first = await _deliver(db_session, org, project, repo, _payload(repo), delivery="d-1")
    second = await _deliver(db_session, org, project, repo, _payload(repo), delivery="d-2")

    assert second == first
    assert len(await _scans(db_session)) == 1
    assert len(dispatch_calls) == 1


@pytest.mark.asyncio
async def test_non_analysis_pr_actions_are_ignored(db_session, dispatch_calls, monkeypatch):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org.id))

    response = await _deliver(db_session, org, project, repo, _payload(repo, action="closed"))

    assert response == {"status": "ignored", "event": "pull_request"}
    assert await _scans(db_session) == []


@pytest.mark.asyncio
async def test_shadow_run_with_malformed_head_sha_is_rejected_without_a_run(
    db_session, dispatch_calls, monkeypatch
):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org.id))

    response = await _deliver(db_session, org, project, repo, _payload(repo, head_sha="cafebabe"))

    assert response == {"status": "ignored", "event": "pull_request", "reason": "invalid_head_sha"}
    assert await _scans(db_session) == []


def test_no_github_write_path_exists_in_the_api():
    """Shadow never publishes: no check-run, comment or status write URL exists in app/."""
    import pathlib

    root = pathlib.Path(webhooks.__file__).resolve().parents[3]
    forbidden = ("/check-runs", "/statuses/", "/comments", "/reviews")
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text()
        if "api.github.com" not in text:
            continue
        offenders.extend(f"{path.name}:{needle}" for needle in forbidden if needle in text)
    assert offenders == []


@pytest.mark.asyncio
async def test_late_delivery_for_an_older_head_is_recorded_ignored_and_cannot_displace_the_newer_run(
    db_session, dispatch_calls, monkeypatch
):
    org, project, repo = await _seed(db_session)
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org.id))
    newer_head, older_head = "c" * 40, "e" * 40

    newer = await _deliver(
        db_session,
        org,
        project,
        repo,
        _payload(repo, action="synchronize", head_sha=newer_head, updated_at="2026-11-05T12:10:00Z"),
        delivery="delivery-newer",
    )
    late = await _deliver(
        db_session,
        org,
        project,
        repo,
        _payload(repo, action="synchronize", head_sha=older_head, updated_at="2026-11-05T12:05:00Z"),
        delivery="delivery-late",
    )

    assert late["status"] == "ignored"
    assert late["reason"] == "stale_pull_request_head"
    assert (late["ignored_head_sha"], late["recorded_head_sha"]) == (older_head, newer_head)
    (scan,) = await _scans(db_session)
    assert scan.commit_sha == newer_head
    assert str(scan.id) == newer["scan_id"]
    assert scan.status.value == "queued"
    assert scan.superseded_by_scan_id is None
    assert dispatch_calls == [str(scan.id)]
    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    recorded = {row.delivery_id: row.response_json for row in rows}
    assert recorded["delivery-late"]["reason"] == "stale_pull_request_head"
