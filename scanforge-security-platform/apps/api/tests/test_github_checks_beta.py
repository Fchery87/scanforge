from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select, update
from test_findings_disappearance_scope import _seed_repository
from test_findings_disappearance_scope import db_session as _db_session

from app.core.config import settings
from app.db.models import Finding, FindingInstance, Project, RepositoryIntegration, Scan
from app.schemas.scans import ScanCreate
from app.services import github as github_module
from app.services.github import GitHubService
from app.services.github_checks import GitHubCheckPublisher, build_check_payload
from app.services.scans import ScanService

db_session = _db_session


async def _pr_scan(db):
    repository_id, project_id = await _seed_repository(db)
    project = await db.get(Project, project_id)
    scan, _, _ = await ScanService(db).create(
        repository_id,
        ScanCreate(
            repository_id=repository_id,
            trigger_type="pull_request",
            scan_type="diff",
            pull_request_number=17,
            base_commit_sha="a" * 40,
            head_commit_sha="b" * 40,
            commit_sha="b" * 40,
        ),
        user_id=None,
    )
    scan.id = str(uuid4())
    db.add(RepositoryIntegration(repository_id=repository_id, installation_id="99"))
    await db.commit()
    return scan, project


@pytest.mark.asyncio
async def test_pr_scan_persists_exact_context(db_session):
    await _pr_scan(db_session)
    db_session.expire_all()
    persisted = (await db_session.execute(select(Scan))).scalar_one()
    assert persisted.base_commit_sha == "a" * 40
    assert persisted.head_commit_sha == "b" * 40
    assert persisted.commit_sha == "b" * 40
    assert persisted.github_check_pending


@pytest.mark.asyncio
async def test_check_outage_preserves_evidence_and_recovers_one_identity(db_session, caplog):
    scan, _ = await _pr_scan(db_session)
    scan.summary_json = {"coverage_complete": True, "scanner_health": {"complete": True}}
    scan.status = "completed"
    await db_session.commit()
    github = SimpleNamespace(publish_check_run=AsyncMock(side_effect=RuntimeError("canary-secret")))
    publisher = GitHubCheckPublisher(db_session, github=github)
    assert not await publisher.publish(scan.id)
    assert "canary-secret" not in caplog.text
    assert scan.status == "completed"
    assert scan.summary_json["coverage_complete"]
    assert scan.github_check_pending
    github.publish_check_run.side_effect = None
    github.publish_check_run.return_value = 123
    assert await publisher.publish(scan.id)
    assert scan.github_check_run_id == 123
    assert not scan.github_check_pending
    scan.github_check_pending = True
    await db_session.commit()
    assert await publisher.publish(scan.id)
    assert github.publish_check_run.await_count == 2
    assert "canary-secret" not in str(github.publish_check_run.await_args)


@pytest.mark.parametrize(
    ("state", "health", "expected_status", "conclusion"),
    [
        ("queued", {}, "queued", None),
        ("running", {}, "in_progress", None),
        ("completed", {"complete": True}, "completed", "neutral"),
        ("completed", {"complete": False, "failed": ["semgrep"]}, "completed", "neutral"),
        ("failed", {}, "completed", "neutral"),
        ("canceled", {}, "completed", "neutral"),
    ],
)
def test_advisory_check_states_are_nonblocking(state, health, expected_status, conclusion):
    scan = SimpleNamespace(
        id=uuid4(),
        status=state,
        project_id=uuid4(),
        repository_id=uuid4(),
        head_commit_sha="b" * 40,
        summary_json={"scanner_health": health},
        error_message="canary-secret",
    )
    payload = build_check_payload(scan, organization_id=uuid4(), counts={"critical": 2, "high": 1})
    assert payload["status"] == expected_status
    assert payload.get("conclusion") == conclusion
    assert "canary-secret" not in str(payload)
    assert "critical=2" in payload["output"]["summary"]
    if state == "completed" and health.get("complete") is False:
        assert "partial" in payload["output"]["summary"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [False, True])
async def test_github_transport_reconciles_check_identity_without_duplicates(monkeypatch, existing):
    calls = []

    def respond(request):
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            runs = [{"id": 123, "external_id": "scan-1", "app": {"id": 99}}] if existing else []
            return httpx.Response(200, json={"check_runs": runs})
        return httpx.Response(200, json={"id": 123})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        github_module.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr(settings, "GITHUB_APP_ID", "99")
    service = GitHubService(object())
    monkeypatch.setattr(service, "_get_installation_token", AsyncMock(return_value="token"))
    result = await service.publish_check_run(
        installation_id="99",
        owner="owner",
        repository="repo",
        head_sha="b" * 40,
        external_id="scan-1",
        payload={"name": "ScanForge advisory", "status": "queued"},
    )
    assert result == 123
    assert calls[-1][0] == ("PATCH" if existing else "POST")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_publisher_reads_latest_terminal_state_from_database(db_session):
    scan, _ = await _pr_scan(db_session)
    await db_session.execute(
        update(Scan).where(Scan.id == scan.id).values(status="canceled"),
        execution_options={"synchronize_session": False},
    )
    await db_session.commit()
    assert str(scan.status) == "queued"
    github = SimpleNamespace(publish_check_run=AsyncMock(return_value=123))
    assert await GitHubCheckPublisher(db_session, github=github).publish(scan.id)
    payload = github.publish_check_run.await_args.kwargs["payload"]
    assert payload["status"] == "completed"
    assert "canceled" in payload["output"]["summary"]


@pytest.mark.asyncio
async def test_pending_checks_retry_without_republishing_settled_scans(db_session):
    scan, _ = await _pr_scan(db_session)
    github = SimpleNamespace(publish_check_run=AsyncMock(return_value=123))
    publisher = GitHubCheckPublisher(db_session, github=github)
    assert await publisher.retry_pending() == 1
    assert await publisher.retry_pending() == 0
    github.publish_check_run.assert_awaited_once()
    assert scan.github_check_run_id == 123


@pytest.mark.asyncio
async def test_check_counts_unique_scan_findings_without_exporting_evidence(db_session):
    scan, project = await _pr_scan(db_session)
    finding = Finding(
        id=str(uuid4()),
        project_id=project.id,
        repository_id=scan.repository_id,
        category="secret",
        severity="critical",
        status="open",
        title="canary-secret",
        canonical_fingerprint="fingerprint",
        primary_scanner="gitleaks",
        risk_score=99,
    )
    db_session.add(finding)
    for fingerprint in ("occurrence-1", "occurrence-2"):
        db_session.add(
            FindingInstance(
                id=str(uuid4()),
                finding_id=finding.id,
                scan_id=scan.id,
                occurrence_fingerprint=fingerprint,
                evidence_json={"secret": "canary-secret"},
            )
        )
    scan.status = "completed"
    scan.summary_json = {"scanner_health": {"complete": True}}
    await db_session.commit()
    github = SimpleNamespace(publish_check_run=AsyncMock(return_value=123))
    assert await GitHubCheckPublisher(db_session, github=github).publish(scan.id)
    payload = github.publish_check_run.await_args.kwargs["payload"]
    assert "critical=1" in payload["output"]["summary"]
    assert "Advisory policy fail" in payload["output"]["summary"]
    assert "canary-secret" not in str(payload)
    assert payload["conclusion"] == "neutral"


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"base_commit_sha": "a" * 40},
        {"base_commit_sha": "a" * 40, "head_commit_sha": "b" * 40, "commit_sha": "c" * 40},
    ],
)
def test_pr_scan_rejects_missing_or_conflicting_commit_context(fields):
    with pytest.raises(ValueError, match="Pull request"):
        ScanCreate(repository_id=uuid4(), trigger_type="pull_request", pull_request_number=17, **fields)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("workflow_state", "days_offset", "observed", "policy"),
    [
        ("open", -1, True, "fail"),
        ("reviewing", -1, True, "fail"),
        ("to_fix", -1, True, "fail"),
        ("not_observed", -1, True, "fail"),
        ("accepted_risk", -1, True, "pass"),
        ("false_positive", -1, True, "pass"),
        ("duplicate", -1, True, "pass"),
        ("fixed", -1, True, "pass"),
        ("open", 0, True, "pass"),
        ("open", 1, True, "pass"),
        ("open", -1, False, "pass"),
    ],
)
async def test_check_policy_uses_overdue_observed_nonexempt_findings(
    db_session,
    workflow_state,
    days_offset,
    observed,
    policy,
):
    scan, project = await _pr_scan(db_session)
    finding = Finding(
        id=str(uuid4()),
        project_id=project.id,
        repository_id=scan.repository_id,
        category="vulnerability",
        severity="low",
        status=workflow_state,
        title="Finding",
        canonical_fingerprint="fingerprint",
        primary_scanner="trivy",
        risk_score=10,
        due_date=datetime.now(UTC).date() + timedelta(days=days_offset),
    )
    db_session.add(finding)
    if observed:
        db_session.add(
            FindingInstance(
                id=str(uuid4()),
                finding_id=finding.id,
                scan_id=scan.id,
                occurrence_fingerprint="occurrence",
            )
        )
    scan.status = "completed"
    scan.summary_json = {"scanner_health": {"complete": True}}
    await db_session.commit()
    github = SimpleNamespace(publish_check_run=AsyncMock(return_value=123))
    assert await GitHubCheckPublisher(db_session, github=github).publish(scan.id)
    payload = github.publish_check_run.await_args.kwargs["payload"]
    assert f"Advisory policy {policy}" in payload["output"]["summary"]
    assert payload["conclusion"] == "neutral"
