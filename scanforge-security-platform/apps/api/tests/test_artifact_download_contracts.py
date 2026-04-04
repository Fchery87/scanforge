from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import datetime, UTC

import pytest

from app.api.v1.routes import exports, scans


def test_export_response_redacts_storage_uri_and_exposes_download_url():
    org_id = uuid4()
    project_id = uuid4()
    export_id = uuid4()
    export = SimpleNamespace(
        id=export_id,
        project_id=project_id,
        organization_id=org_id,
        export_type="findings",
        format="csv",
        status="completed",
        title="report",
        storage_uri="exports/report.csv",
        file_name=None,
        size_bytes=None,
        created_by_user_id=None,
        error_message=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        expires_at=None,
    )

    payload = exports._serialize_export(export, org_id=org_id, project_id=project_id)

    assert payload.storage_uri is None
    assert payload.download_url.endswith(f"/exports/{export_id}/download")


def test_scan_detail_redacts_artifact_uris_and_sets_download_urls():
    org_id = uuid4()
    project_id = uuid4()
    scan_id = uuid4()
    run_id = uuid4()
    scan = SimpleNamespace(
        id=scan_id,
        project_id=project_id,
        repository_id=uuid4(),
        trigger_type="manual",
        status="completed",
        branch_name="main",
        commit_sha="deadbeef",
        pull_request_number=None,
        requested_by_user_id=None,
        error_message=None,
        summary_json=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        scanner_runs=[
            SimpleNamespace(
                id=run_id,
                scan_id=scan_id,
                scanner_name="trivy",
                scanner_version="1",
                status="completed",
                duration_ms=1,
                exit_code=0,
                error_message=None,
                artifact_uri="scans/123/trivy/output.json",
                metadata_json={"raw_output_uri": "scans/123/trivy/raw.json", "other": "value"},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ],
    )

    payload = scans._apply_scan_download_urls(scan, org_id=org_id, project_id=project_id)

    run = payload.scanner_runs[0]
    assert run.artifact_uri is None
    assert run.artifact_download_url.endswith(f"/scans/{scan_id}/scanner-runs/{run_id}/download")
    assert run.metadata_json == {"other": "value"}


@pytest.mark.asyncio
async def test_download_scan_artifact_uses_presigned_url(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    scan_id = uuid4()
    run_id = uuid4()
    current_user = SimpleNamespace(user_id=uuid4())
    scan = SimpleNamespace(
        project_id=project_id,
        scanner_runs=[SimpleNamespace(id=run_id, artifact_uri="scans/123/trivy/output.json")],
    )

    monkeypatch.setattr(scans, "get_project_in_org_or_404", AsyncMock())
    monkeypatch.setattr(scans, "ScanService", lambda _db: SimpleNamespace(get_by_id=AsyncMock(return_value=scan)))
    monkeypatch.setattr(
        scans,
        "_get_r2_client",
        lambda: SimpleNamespace(generate_presigned_url=lambda key: f"https://signed.example/{key}"),
    )

    response = await scans.download_scan_artifact(
        org_id=org_id,
        project_id=project_id,
        scan_id=scan_id,
        run_id=run_id,
        current_user=current_user,
        db=object(),
    )

    assert response.headers["location"] == "https://signed.example/scans/123/trivy/output.json"
