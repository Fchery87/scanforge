"""Soft-delete acceptance against migrated PostgreSQL, including FK-backed lineage."""
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_bulk_project_scope_postgres import scope_db, scope_pg_url  # noqa: F401
from test_scan_dispatch import _seed_org_project_repo

from app.api.v1.routes.scans import delete_scan, get_scan
from app.db.enums import ScanStatus
from app.db.models import Finding, FindingEvent, FindingInstance, OrganizationMember, Scan
from app.services.scans import ScanService


@pytest.mark.parametrize("status", [ScanStatus.QUEUED, ScanStatus.FAILED, ScanStatus.CANCELED])
async def test_soft_delete_is_repeatable_and_preserves_lineage(scope_db, status):  # noqa: F811
    db = scope_db
    org, project, repo, user = await _seed_org_project_repo(db)
    repo.full_name = f"o/{uuid4().hex}"
    db.add(OrganizationMember(id=uuid4(), organization_id=org.id, user_id=user.id, role="admin"))
    scan = Scan(id=uuid4(), project_id=project.id, repository_id=repo.id, trigger_type="manual", status=status)
    visible = Scan(id=uuid4(), project_id=project.id, repository_id=repo.id,
                   trigger_type="manual", status=ScanStatus.COMPLETED)
    finding = Finding(id=uuid4(), project_id=project.id, repository_id=repo.id, category="vulnerability",
                      severity="high", status="open", title="Retained", canonical_fingerprint=uuid4().hex)
    db.add_all([scan, visible, finding])
    await db.flush()
    instance = FindingInstance(id=uuid4(), finding_id=finding.id, scan_id=scan.id,
                               occurrence_fingerprint=uuid4().hex, evidence_json={"source": "retained"})
    event = FindingEvent(id=uuid4(), finding_id=finding.id, event_type="detected",
                         metadata_json={"scan_id": str(scan.id)})
    db.add_all([instance, event])
    await db.commit()
    ids = [scan.id, visible.id, finding.id, instance.id, event.id]
    kwargs = dict(org_id=UUID(str(org.id)), project_id=UUID(str(project.id)), scan_id=scan.id,
                  current_user=SimpleNamespace(user_id=UUID(str(user.id))), db=db)
    service = ScanService(db)
    deleted = await delete_scan(**kwargs)
    timestamp = deleted.deleted_at
    assert timestamp is not None
    with pytest.raises(HTTPException) as hidden:
        await get_scan(**kwargs)
    assert hidden.value.status_code == 404
    assert await service.get_by_id(scan.id, kwargs["current_user"].user_id) is None
    for rows, total in [await service.list_for_project(project.id, kwargs["current_user"].user_id),
                        await service.list_for_repository(repo.id, kwargs["current_user"].user_id)]:
        assert total == 1
        assert [row.id for row in rows] == [visible.id]
    repeated = await delete_scan(**kwargs)
    assert repeated.deleted_at == timestamp
    with pytest.raises(HTTPException) as wrong_project:
        await delete_scan(**{**kwargs, "project_id": uuid4()})
    assert wrong_project.value.status_code == 404
    db.expire_all()
    retained = (await db.execute(select(Scan).where(Scan.id == ids[0]))).scalar_one()
    assert retained.deleted_at == timestamp
    retained_finding = await db.get(Finding, ids[2])
    retained_instance = await db.get(FindingInstance, ids[3])
    retained_event = await db.get(FindingEvent, ids[4])
    assert retained_finding.status == "open"
    assert retained_instance.scan_id == ids[0]
    assert retained_instance.evidence_json == {"source": "retained"}
    assert retained_event.metadata_json == {"scan_id": str(ids[0])}
