from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.api.v1.routes.exports import _serialize_export
from app.schemas.exports import ExportResponse
from app.services.exports import ExportAuthorizationError, ExportService


@pytest.mark.asyncio
async def test_create_export_persists_title():
    project_id = uuid4()
    user_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=uuid4())
    captured = {}

    db = AsyncMock()
    db.get.return_value = project
    db.add = Mock(side_effect=lambda export: captured.setdefault("export", export))

    service = ExportService(db)

    result = await service.create(
        project_id,
        SimpleNamespace(
            export_type="findings",
            format="csv",
            filters=None,
            title="Q1 report",
        ),
        user_id,
    )

    assert result is captured["export"]
    assert captured["export"].title == "Q1 report"



@pytest.mark.asyncio
async def test_create_export_rejects_non_member_of_target_org():
    project_id = uuid4()
    user_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=uuid4())

    db = AsyncMock()
    db.get.return_value = project
    membership_result = Mock()
    membership_result.scalar_one_or_none.return_value = None
    db.execute.return_value = membership_result

    service = ExportService(db)

    with pytest.raises(ExportAuthorizationError):
        await service.create(
            project_id,
            SimpleNamespace(
                export_type="findings",
                format="csv",
                filters=None,
                title="Q1 report",
            ),
            user_id,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_export_allows_member_of_target_org():
    project_id = uuid4()
    user_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=uuid4())
    captured = {}

    db = AsyncMock()
    db.get.return_value = project
    membership_result = Mock()
    membership_result.scalar_one_or_none.return_value = SimpleNamespace(id=uuid4())
    db.execute.return_value = membership_result
    db.add = Mock(side_effect=lambda export: captured.setdefault("export", export))

    service = ExportService(db)

    result = await service.create(
        project_id,
        SimpleNamespace(
            export_type="findings",
            format="csv",
            filters=None,
            title="Q1 report",
        ),
        user_id,
    )

    assert result is captured["export"]
    assert captured["export"].project_id == str(project_id)
    assert captured["export"].requested_by_user_id == str(user_id)
def test_export_response_contract_excludes_secret_bearing_columns():
    """R08: findings export surface must never grow internal secret-bearing columns."""
    forbidden_markers = (
        "secret", "token", "credential", "webhook", "signature", "matched", "plaintext", "raw_value",
    )
    field_names = set(ExportResponse.model_fields)
    leaks = [marker for marker in forbidden_markers if any(marker in name for name in field_names)]
    assert not leaks, f"ExportResponse exposes secret-bearing columns: {leaks}"


def test_export_download_payload_nulls_internal_storage_uri():
    """R08: serialized exports must not expose internal storage keys."""
    export = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        organization_id=uuid4(),
        export_type="findings",
        format="csv",
        status="completed",
        title="Q1 findings",
        storage_uri="s3://bucket/scan-artifacts/org/scan/scanner/out.json",
        download_url=None,
        file_name="findings.csv",
        size_bytes=120,
        created_by_user_id=uuid4(),
        error_message=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
    )
    payload = _serialize_export(export, org_id=export.organization_id, project_id=export.project_id)
    assert payload.storage_uri is None
    assert "scan-artifacts" not in (payload.download_url or "")
