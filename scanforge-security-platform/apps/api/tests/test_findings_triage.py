from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.db.models.finding import Finding, FindingEvent
from app.schemas.findings import FindingBulkAction, FindingResponse
from app.services.findings import FindingService


def test_finding_bulk_action_allows_accept_risk_and_duplicate():
    accepted = FindingBulkAction.model_validate(
        {
            "finding_ids": [uuid4()],
            "action": "accept_risk",
            "reason": "Compensating control is documented",
        }
    )
    duplicate = FindingBulkAction.model_validate(
        {
            "finding_ids": [uuid4()],
            "action": "mark_duplicate",
            "reason": "Same canonical issue tracked elsewhere",
        }
    )

    assert accepted.action == "accept_risk"
    assert duplicate.action == "mark_duplicate"


@pytest.mark.asyncio
async def test_accept_risk_updates_status_and_records_event():
    finding_id = uuid4()
    user_id = uuid4()
    finding = SimpleNamespace(status="open")
    db = AsyncMock()
    db.get.return_value = finding
    db.scalar.return_value = 1
    db.add = Mock()
    execute_result = Mock()
    execute_result.scalar_one.return_value = finding
    db.execute.return_value = execute_result

    service = FindingService(db)
    service.get_by_id = AsyncMock(return_value=finding)

    result = await service.accept_risk(finding_id, user_id, "Risk accepted with compensating controls")

    assert result is finding
    assert finding.status == "accepted_risk"
    event = db.add.call_args.args[0]
    assert isinstance(event, FindingEvent)
    assert event.finding_id == finding_id
    assert event.event_type == "accepted_risk"
    assert event.actor_user_id == user_id
    assert event.reason == "Risk accepted with compensating controls"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(finding)


@pytest.mark.asyncio
async def test_mark_duplicate_updates_status_and_records_event():
    finding_id = uuid4()
    user_id = uuid4()
    finding = SimpleNamespace(status="open")
    db = AsyncMock()
    db.get.return_value = finding
    db.add = Mock()

    service = FindingService(db)
    service.get_by_id = AsyncMock(return_value=finding)

    result = await service.mark_duplicate(finding_id, user_id, "Duplicate of another finding")

    assert result is finding
    assert finding.status == "duplicate"
    event = db.add.call_args.args[0]
    assert isinstance(event, FindingEvent)
    assert event.finding_id == finding_id
    assert event.event_type == "duplicate"
    assert event.actor_user_id == user_id
    assert event.reason == "Duplicate of another finding"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(finding)


@pytest.mark.asyncio
async def test_update_triage_sets_assignee_and_due_date_and_records_event():
    finding_id = uuid4()
    user_id = uuid4()
    assignee_user_id = uuid4()
    due_date = date(2026, 4, 15)
    finding = SimpleNamespace(
        status="open",
        project_id=uuid4(),
        assignee_user_id=None,
        due_date=None,
    )
    db = AsyncMock()
    db.get.return_value = finding
    db.scalar.return_value = 1
    db.add = Mock()
    execute_result = Mock()
    execute_result.scalar_one.return_value = finding
    db.execute.return_value = execute_result

    service = FindingService(db)
    service.get_by_id = AsyncMock(return_value=finding)

    result = await service.update_triage(
        finding_id,
        user_id,
        assignee_user_id=assignee_user_id,
        due_date=due_date,
    )

    assert result is finding
    assert finding.assignee_user_id == assignee_user_id
    assert finding.due_date == due_date
    event = db.add.call_args.args[0]
    assert isinstance(event, FindingEvent)
    assert event.event_type == "triage_updated"
    assert event.metadata_json == {
        "assignee_user_id": str(assignee_user_id),
        "due_date": "2026-04-15",
    }
    db.commit.assert_awaited_once()
    db.execute.assert_awaited()


def test_finding_response_exposes_assignment_fields():
    payload = FindingResponse.model_validate(
        {
            "id": uuid4(),
            "project_id": uuid4(),
            "repository_id": uuid4(),
            "category": "vulnerability",
            "severity": "high",
            "status": "open",
            "title": "Example",
            "description": None,
            "canonical_fingerprint": "abc",
            "primary_scanner": "trivy",
            "confidence_score": 0.9,
            "fixed_version": None,
            "metadata_json": None,
            "assignee_user_id": uuid4(),
            "assignee_name": "Jane Dev",
            "assignee_email": "jane@example.com",
            "due_date": "2026-04-15",
            "first_seen_at": "2026-03-30T00:00:00Z",
            "last_seen_at": "2026-03-30T00:00:00Z",
            "created_at": "2026-03-30T00:00:00Z",
            "updated_at": "2026-03-30T00:00:00Z",
        }
    )

    assert payload.assignee_name == "Jane Dev"
    assert payload.assignee_email == "jane@example.com"
    assert payload.due_date == date(2026, 4, 15)
    assert payload.sla_status is None


def test_finding_model_exposes_sla_status_preview():
    finding = Finding(status="open", due_date=date(2026, 1, 5))

    assert finding.sla_status["status"] in {"overdue", "due_soon", "on_track"}


def test_finding_model_exposes_assignee_relationship():
    assert hasattr(Finding, "assignee")


@pytest.mark.asyncio
async def test_accept_risk_returns_none_when_user_cannot_access_finding():
    finding_id = uuid4()
    user_id = uuid4()

    db = AsyncMock()
    service = FindingService(db)
    service.get_by_id = AsyncMock(return_value=None)

    result = await service.accept_risk(finding_id, user_id, "Risk accepted with compensating controls")

    assert result is None
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_not_observed_updates_absent_findings_only_with_complete_scanner_coverage():
    seen = SimpleNamespace(id=uuid4(), canonical_fingerprint="seen", primary_scanner="trivy", status="open", metadata_json=None)
    absent = SimpleNamespace(id=uuid4(), canonical_fingerprint="absent", primary_scanner="trivy", status="open", metadata_json=None)
    failed_scanner = SimpleNamespace(
        id=uuid4(),
        canonical_fingerprint="failed",
        primary_scanner="gitleaks",
        status="open",
        metadata_json=None,
    )
    db = AsyncMock()
    db.add = Mock()

    service = FindingService(db)
    service._list_open_findings_for_repository = AsyncMock(return_value=[seen, absent, failed_scanner])

    updated = await service.mark_not_observed_after_scan(
        repository_id="repo-1",
        scan_id="scan-1",
        seen_fingerprints={"seen"},
        scan_summary={
            "scanner_health": {
                "expected": ["trivy", "gitleaks"],
                "completed": ["trivy"],
                "failed": ["gitleaks"],
                "missing": [],
                "complete": False,
            }
        },
    )

    assert updated == 1
    assert seen.status == "open"
    assert absent.status == "not_observed"
    assert failed_scanner.status == "open"
    event = db.add.call_args.args[0]
    assert isinstance(event, FindingEvent)
    assert event.finding_id == absent.id
    assert event.event_type == "marked_not_observed"
    assert event.metadata_json == {"scan_id": "scan-1", "not_observed_count": 1}
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_not_observed_promotes_repeated_absence_to_fixed():
    finding = SimpleNamespace(
        id=uuid4(),
        canonical_fingerprint="absent",
        primary_scanner="trivy",
        status="not_observed",
        metadata_json={"not_observed_count": 1},
    )
    db = AsyncMock()
    db.add = Mock()

    service = FindingService(db)
    service._list_open_findings_for_repository = AsyncMock(return_value=[finding])

    updated = await service.mark_not_observed_after_scan(
        repository_id="repo-1",
        scan_id="scan-2",
        seen_fingerprints=set(),
        scan_summary={"scanner_health": {"completed": ["trivy"]}},
    )

    assert updated == 1
    assert finding.status == "fixed"
    assert finding.metadata_json["not_observed_count"] == 2
    event = db.add.call_args.args[0]
    assert event.event_type == "fixed"
    assert event.metadata_json == {"scan_id": "scan-2", "not_observed_count": 2}
    db.commit.assert_awaited_once()
