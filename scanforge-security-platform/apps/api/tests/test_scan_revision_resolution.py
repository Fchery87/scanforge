"""Manual and scheduled scans resolve an exact head SHA at creation (gap from #34).

The worker refuses to scan without an exact commit SHA, so the API must record one.
GitHub is faked; a live GitHub lookup was NOT run.
"""

from __future__ import annotations

import pytest
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from app.db.models import OrganizationIntegration
from app.schemas.scans import ScanCreate
from app.services import scans as scans_module
from app.services.github import GitHubRevisionNotFoundError
from app.services.scans import ScanService

RESOLVED = "f" * 40


class _FakeGitHub:
    calls: list[tuple] = []
    error: Exception | None = None

    def __init__(self, _db):
        pass

    async def resolve_branch_commit(self, installation_id, owner, repo, branch, *, expected_commit_sha=None):
        type(self).calls.append((installation_id, owner, repo, branch, expected_commit_sha))
        if type(self).error:
            raise type(self).error
        return RESOLVED


@pytest.fixture
def github(monkeypatch):
    _FakeGitHub.calls = []
    _FakeGitHub.error = None
    monkeypatch.setattr(scans_module, "GitHubService", _FakeGitHub)
    return _FakeGitHub


async def _seed(db_session, *, integration=True):
    org, _project, repo, user = await _seed_org_project_repo(db_session)
    if integration:
        db_session.add(OrganizationIntegration(organization_id=org.id, installation_id="99"))
        await db_session.commit()
    return org, repo, user


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["manual", "scheduled"])
async def test_scan_without_commit_resolves_default_branch_head(db_session, github, trigger):
    _org, repo, user = await _seed(db_session)

    scan, _, _ = await ScanService(db_session).create(
        repo.id,
        ScanCreate(repository_id=repo.id, trigger_type=trigger, scan_type="full"),
        user.id if trigger == "manual" else None,
    )

    assert scan.commit_sha == RESOLVED
    assert scan.full_ref_name == "refs/heads/main"
    assert github.calls == [("99", "acme", "core-platform", "main", None)]


@pytest.mark.asyncio
async def test_manual_branch_request_resolves_that_branch(db_session, github):
    _org, repo, user = await _seed(db_session)

    scan, _, _ = await ScanService(db_session).create(
        repo.id,
        ScanCreate(repository_id=repo.id, trigger_type="manual", scan_type="full", branch_name="release/1"),
        user.id,
    )

    assert scan.commit_sha == RESOLVED
    assert github.calls[0][3] == "release/1"


@pytest.mark.asyncio
async def test_supplied_commit_is_used_as_given_without_a_lookup(db_session, github):
    _org, repo, user = await _seed(db_session)
    supplied = "1" * 40

    await ScanService(db_session).create(
        repo.id,
        ScanCreate(repository_id=repo.id, trigger_type="manual", scan_type="full", commit_sha=supplied),
        user.id,
    )

    assert github.calls == []


@pytest.mark.asyncio
async def test_unresolvable_head_fails_scan_creation_instead_of_queueing_a_doomed_scan(db_session, github):
    _org, repo, user = await _seed(db_session)
    github.error = GitHubRevisionNotFoundError("not accessible")

    with pytest.raises(ValueError, match="exact commit"):
        await ScanService(db_session).create(
            repo.id, ScanCreate(repository_id=repo.id, trigger_type="manual", scan_type="full"), user.id
        )

    from sqlalchemy import select

    from app.db.models import Scan

    assert (await db_session.execute(select(Scan))).scalars().all() == []


@pytest.mark.asyncio
async def test_missing_github_integration_fails_scan_creation_explicitly(db_session, github):
    _org, repo, user = await _seed(db_session, integration=False)

    with pytest.raises(ValueError, match="exact commit"):
        await ScanService(db_session).create(
            repo.id, ScanCreate(repository_id=repo.id, trigger_type="manual", scan_type="full"), user.id
        )
    assert github.calls == []
