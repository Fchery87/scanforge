from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routes import scans
from app.schemas.canonical_findings import CanonicalFindingCandidate
from app.services.onboarding import build_onboarding_checklist
from app.services.scan_lifecycle import ScanLifecycleService


@pytest.mark.asyncio
async def test_scan_lifecycle_program_contract_preserves_core_seams():
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    user_id = uuid4()
    scan = SimpleNamespace(
        id=uuid4(),
        repository_id=repository_id,
        project_id=project_id,
        branch_name="main",
        commit_sha="deadbeef",
        status="queued",
        error_message=None,
    )
    scan_service = SimpleNamespace(create=AsyncMock(return_value=(scan, None, None)))
    queue = SimpleNamespace(enqueue=AsyncMock(return_value="job-1"))
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

    created_scan = await ScanLifecycleService(db, scan_service=scan_service, queue=queue).create_manual_scan(
        org_id=org_id,
        data=SimpleNamespace(repository_id=repository_id, scan_type="full"),
        user_id=user_id,
    )

    assert created_scan is scan
    queue.enqueue.assert_awaited_once_with("scan.repo.full", {"scan_id": str(scan.id)})

    candidate = CanonicalFindingCandidate.model_validate(
        {
            "canonical_fingerprint": "fp-1",
            "severity": "critical",
            "category": "secret",
            "title": "Exposed secret",
            "instance": {"path": "app.py", "line_start": 10},
            "references": [{"type": "rule", "value": "GITLEAKS-1"}],
        }
    )
    assert candidate.instance.path == "app.py"
    assert candidate.references[0].value == "GITLEAKS-1"

    scan_detail = SimpleNamespace(
        id=scan.id,
        project_id=project_id,
        repository_id=repository_id,
        trigger_type="manual",
        scan_type="full",
        status="completed",
        branch_name="main",
        commit_sha="deadbeef",
        pull_request_number=None,
        requested_by_user_id=user_id,
        error_message=None,
        summary_json=None,
        created_at="2026-05-02T00:00:00Z",
        updated_at="2026-05-02T00:00:00Z",
        scanner_runs=[],
    )
    payload = scans._apply_scan_download_urls(scan_detail, org_id=org_id, project_id=project_id)
    assert payload.scanner_runs == []

    checklist = build_onboarding_checklist(
        user_id=str(user_id),
        org_id=str(org_id),
        has_github=True,
        has_projects=True,
        has_repositories=True,
        has_scans=True,
        has_findings=True,
        has_schedules=True,
    )
    assert checklist.is_complete() is True
