"""Project bulk-action contract on a migrated, disposable PostgreSQL database."""
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from test_scan_dispatch import _disposable_postgres_url, _seed_org_project_repo

from app.api.v1.routes.findings import bulk_finding_action
from app.db.models import Finding, FindingEvent, OrganizationMember, Project, Repository
from app.schemas.findings import FindingBulkAction


@pytest.fixture(scope="module")
def scope_pg_url():
    with _disposable_postgres_url() as url:
        yield url


@pytest_asyncio.fixture
async def scope_db(scope_pg_url):
    engine = create_async_engine(scope_pg_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            yield db
    finally:
        await engine.dispose()


@pytest.mark.parametrize("action", ["suppress", "resolve", "accept_risk", "mark_duplicate"])
@pytest.mark.parametrize("invalid_target", ["sibling_project", "missing"])
async def test_bulk_route_rejects_entire_invalid_batch(scope_db, action, invalid_target):
    db = scope_db
    org, project, repo, user = await _seed_org_project_repo(db)
    db.add(OrganizationMember(id=uuid4(), organization_id=org.id, user_id=user.id, role="admin"))
    repo.full_name = f"o/{uuid4().hex}"
    sibling = Project(id=uuid4(), organization_id=org.id, name="Sibling", slug=uuid4().hex,
                      created_by_user_id=user.id)
    db.add(sibling)
    await db.flush()
    sibling_repo = Repository(id=uuid4(), project_id=sibling.id, provider="github", owner_name="o",
                              repo_name="sibling", full_name=f"o/{uuid4().hex}")
    db.add(sibling_repo)
    await db.flush()
    own = Finding(id=uuid4(), project_id=project.id, repository_id=repo.id, category="vulnerability",
                  severity="high", status="open", title="Own", canonical_fingerprint=uuid4().hex)
    foreign = Finding(id=uuid4(), project_id=sibling.id, repository_id=sibling_repo.id,
                      category="vulnerability", severity="high", status="open", title="Sibling",
                      canonical_fingerprint=uuid4().hex)
    db.add_all([own, foreign])
    await db.commit()
    own_id, foreign_id = own.id, foreign.id
    invalid_id = foreign_id if invalid_target == "sibling_project" else uuid4()
    with pytest.raises(HTTPException) as exc:
        await bulk_finding_action(
            org_id=UUID(str(org.id)), project_id=UUID(str(project.id)),
            data=FindingBulkAction(finding_ids=[own_id, invalid_id], action=action, reason="Reviewed"),
            current_user=SimpleNamespace(user_id=UUID(str(user.id))), db=db,
        )
    assert exc.value.status_code == 400
    assert "do not belong to this project" in exc.value.detail
    assert str(invalid_id) in exc.value.detail
    # Commit deliberately: rejection must not leave partial writes pending either.
    await db.commit()
    db.expire_all()
    rows = (await db.execute(select(Finding).where(Finding.id.in_([own_id, foreign_id])))).scalars().all()
    assert len(rows) == 2
    assert all(row.status == "open" and row.human_revision == 1 for row in rows)
    assert await db.scalar(select(func.count()).select_from(FindingEvent).where(
        FindingEvent.finding_id.in_([own_id, foreign_id]))) == 0
