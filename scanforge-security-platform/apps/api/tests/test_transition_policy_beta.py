from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.services.finding_lifecycle import validate_transition
from app.services.findings import FindingService


@pytest.mark.parametrize("current,target", [("fixed", "accepted_risk"), ("false_positive", "to_fix"), ("open", "not_observed")])
def test_terminal_findings_reopen_before_retriage_and_absence_is_system_owned(current, target):
    with pytest.raises(ValueError):
        validate_transition(current, target)


def test_active_triage_and_terminal_reopen_are_supported():
    assert validate_transition("open", "reviewing").value == "reviewing"
    assert validate_transition("to_fix", "fixed").value == "fixed"
    assert validate_transition("fixed", "open").value == "open"


@pytest.mark.asyncio
async def test_manual_fix_requires_resolution_evidence_before_mutation():
    db = AsyncMock()
    db.add = Mock()
    finding = SimpleNamespace(status="open")
    service = FindingService(db)
    service.get_by_id = AsyncMock(return_value=finding)
    with pytest.raises(ValueError, match="evidence"):
        await service.resolve(uuid4(), uuid4())
    assert finding.status == "open"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_disposition_requires_nonempty_reason():
    service = FindingService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=SimpleNamespace(status="open"))
    with pytest.raises(ValueError, match="reason"):
        await service.accept_risk(uuid4(), uuid4(), "  ")


def test_unknown_or_changed_scanner_provenance_cannot_close_finding():
    from app.services.finding_lifecycle import comparable_scanner_evidence

    evidence = {"scanner_version": "1.0", "configuration_digest": "image-a", "rules_version": "rules-a"}
    assert comparable_scanner_evidence(evidence, evidence)
    assert not comparable_scanner_evidence({}, evidence)
    assert not comparable_scanner_evidence(evidence, {**evidence, "scanner_version": "2.0"})
    assert not comparable_scanner_evidence(evidence, {**evidence, "rules_version": "rules-b"})
