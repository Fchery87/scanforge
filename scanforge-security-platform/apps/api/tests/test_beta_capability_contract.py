from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import exports, internal, scan_schedules, scorecard, suppression_rules, webhooks
from app.middleware.auth import UserContext
from app.schemas.exports import ExportCreate
from app.schemas.scan_schedules import ScanScheduleCreate, ScanScheduleUpdate
from app.schemas.scans import ScanCreate


def _user() -> UserContext:
    uid = uuid4()
    return UserContext(sub=str(uid), user_id=uid, email="reviewer@example.com")


@pytest.mark.asyncio
async def test_export_generation_and_download_disabled_in_initial_beta():
    db = AsyncMock()
    with pytest.raises(HTTPException) as create_exc:
        await exports.create_export(
            org_id=uuid4(),
            project_id=uuid4(),
            data=ExportCreate(export_type="findings", format="csv", title="Beta Export"),
            current_user=_user(),
            db=db,
        )
    assert create_exc.value.status_code == 503
    assert "beta_capability_disabled" in str(create_exc.value.detail)
    db.add.assert_not_called()
    db.commit.assert_not_awaited()

    with pytest.raises(HTTPException) as download_exc:
        await exports.download_export(
            org_id=uuid4(),
            project_id=uuid4(),
            export_id=uuid4(),
            current_user=_user(),
            db=db,
        )
    assert download_exc.value.status_code == 503
    assert "beta_capability_disabled" in str(download_exc.value.detail)


@pytest.mark.asyncio
async def test_suppression_rule_mutations_disabled_in_initial_beta():
    db = AsyncMock()
    with pytest.raises(HTTPException) as create_exc:
        await suppression_rules.create_rule(
            org_id=uuid4(),
            body=suppression_rules.SuppressionRuleCreate(
                rule_type="severity",
                match_criteria_json={"severity": "low"},
                reason="defer",
            ),
            current_user=_user(),
            db=db,
        )
    assert create_exc.value.status_code == 503
    assert "beta_capability_disabled" in str(create_exc.value.detail)
    db.add.assert_not_called()

    with pytest.raises(HTTPException) as update_exc:
        await suppression_rules.update_rule(
            org_id=uuid4(),
            rule_id=uuid4(),
            body=suppression_rules.SuppressionRuleUpdate(is_active=True),
            current_user=_user(),
            db=db,
        )
    assert update_exc.value.status_code == 503

    with pytest.raises(HTTPException) as delete_exc:
        await suppression_rules.delete_rule(
            org_id=uuid4(),
            rule_id=uuid4(),
            current_user=_user(),
            db=db,
        )
    assert delete_exc.value.status_code == 503


@pytest.mark.asyncio
async def test_scan_schedule_mutations_and_due_runner_disabled_in_initial_beta(monkeypatch):
    db = AsyncMock()
    repo_id = uuid4()
    with pytest.raises(HTTPException) as create_exc:
        await scan_schedules.create_schedule(
            org_id=uuid4(),
            project_id=uuid4(),
            repo_id=repo_id,
            data=ScanScheduleCreate(repository_id=repo_id, schedule_type="daily", scan_type="full"),
            current_user=_user(),
            db=db,
        )
    assert create_exc.value.status_code == 503
    assert "beta_capability_disabled" in str(create_exc.value.detail)

    with pytest.raises(HTTPException) as update_exc:
        await scan_schedules.update_schedule(
            org_id=uuid4(),
            project_id=uuid4(),
            repo_id=repo_id,
            schedule_id=uuid4(),
            data=ScanScheduleUpdate(is_active=True),
            current_user=_user(),
            db=db,
        )
    assert update_exc.value.status_code == 503

    with pytest.raises(HTTPException) as delete_exc:
        await scan_schedules.delete_schedule(
            org_id=uuid4(),
            project_id=uuid4(),
            repo_id=repo_id,
            schedule_id=uuid4(),
            current_user=_user(),
            db=db,
        )
    assert delete_exc.value.status_code == 503

    schedule_service = SimpleNamespace(
        get_due_schedules=AsyncMock(return_value=[SimpleNamespace(id=uuid4())]),
        mark_run=AsyncMock(),
    )
    lifecycle = SimpleNamespace(create_scheduled_scan=AsyncMock())
    monkeypatch.setattr(internal, "ScanScheduleService", lambda _db: schedule_service)
    monkeypatch.setattr(internal, "ScanLifecycleService", lambda _db: lifecycle)

    due_result = await internal.run_due_scan_schedules(db=db)
    assert due_result["queued"] == 0
    assert due_result.get("disabled") is True
    lifecycle.create_scheduled_scan.assert_not_awaited()
    schedule_service.mark_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_pull_request_webhook_does_not_enqueue_scan_or_publish_advisory(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    repo = SimpleNamespace(
        id=repository_id,
        project_id=project_id,
        full_name="scanforge/platform",
        external_repo_id="42",
        default_branch="main",
    )
    project = SimpleNamespace(id=project_id, organization_id=org_id)
    integration = SimpleNamespace(installation_id="99")

    class _FakeDB:
        def __init__(self):
            self.added = []
            self.committed = False

        async def get(self, model, _val):
            if model is webhooks.Repository:
                return repo
            if model is webhooks.Project:
                return project
            return None

        async def scalar(self, _q):
            return integration

        async def execute(self, _q):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

        def add(self, obj):
            self.added.append(obj)

        async def flush(self):
            return None

        async def commit(self):
            self.committed = True

    class _FakeRequest:
        headers = {"x-github-event": "pull_request", "x-github-delivery": "deliv-pr-1"}

        async def json(self):
            return {
                "action": "synchronize",
                "pull_request": {
                    "number": 17,
                    "head": {"sha": "cafebabe", "ref": "feature/sec"},
                    "base": {"sha": "basebeef", "ref": "main"},
                },
                "repository": {"full_name": "scanforge/platform", "id": 42},
                "installation": {"id": 99},
            }

    lifecycle = SimpleNamespace(create_manual_scan=AsyncMock())
    scan_service = SimpleNamespace(create=AsyncMock())
    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))
    monkeypatch.setattr(webhooks, "ScanLifecycleService", lambda _db: lifecycle)
    monkeypatch.setattr(webhooks, "ScanService", lambda _db: scan_service)

    response = await webhooks.github_webhook(
        org_id=org_id,
        project_id=project_id,
        repository_id=repository_id,
        request=_FakeRequest(),
        db=_FakeDB(),
    )
    assert response["status"] == "ignored"
    assert response["event"] == "pull_request"
    assert "advisory" not in response
    assert "scan_id" not in response
    lifecycle.create_manual_scan.assert_not_awaited()
    scan_service.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_scorecard_hides_grades_numeric_scores_and_enforcement(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    monkeypatch.setattr(scorecard, "get_project_in_org_or_404", AsyncMock(return_value=SimpleNamespace(id=project_id)))

    class _FakeScalarResult:
        def __init__(self, val=0, items=None):
            self._val = val
            self._items = items or []

        def scalar_one_or_none(self):
            return self._val

        def scalars(self):
            return SimpleNamespace(all=lambda: self._items)

    class _FakeDB:
        async def execute(self, _q):
            return _FakeScalarResult(0)

    res = await scorecard.get_project_scorecard(
        org_id=org_id,
        project_id=project_id,
        current_user=_user(),
        db=_FakeDB(),
    )
    assert res.grade is None
    assert res.overall_score is None
    assert res.security_score is None
    assert res.secrets_score is None
    assert res.dependency_score is None
    assert res.risk_score_average is None
    assert res.policy_evaluation is None


def test_ManualScan_rejects_deferred_diff_or_pr_triggers_in_beta_policy():
    from app.core.beta_capabilities import assert_scan_request_supported

    with pytest.raises(HTTPException) as diff_exc:
        assert_scan_request_supported(
            ScanCreate(repository_id=uuid4(), trigger_type="manual", scan_type="diff")
        )
    assert diff_exc.value.status_code == 503

    with pytest.raises(HTTPException) as pr_exc:
        assert_scan_request_supported(
            ScanCreate(repository_id=uuid4(), trigger_type="pull_request", scan_type="full")
        )
    assert pr_exc.value.status_code == 503
