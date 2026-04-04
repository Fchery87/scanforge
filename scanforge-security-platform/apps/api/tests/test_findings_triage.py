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
