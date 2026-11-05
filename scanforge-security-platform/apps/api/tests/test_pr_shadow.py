"""Shadow PR analysis (#46, plan P2.1): private runs with recorded revision identity.

Shadow means analysis is stored and never published to GitHub.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from app.api.v1.routes import internal
from app.core import beta_capabilities
from app.core.config import settings
from app.db.models import Finding, ScanDispatchObligation
from app.middleware.service_auth import WorkerPrincipal
from app.services.scans import ScanService

BASE = "b" * 40
HEAD = "a" * 40
HEAD_2 = "c" * 40
MERGE_BASE = "d" * 40


def test_pr_shadow_is_off_for_every_organization_by_default():
    assert beta_capabilities.is_pr_shadow_enabled(uuid4()) is False


def test_pr_shadow_enables_only_for_allowlisted_organizations(monkeypatch):
    enabled_org, other_org = uuid4(), uuid4()
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", f" {enabled_org} , not-a-uuid")
    assert beta_capabilities.is_pr_shadow_enabled(enabled_org) is True
    assert beta_capabilities.is_pr_shadow_enabled(str(enabled_org).upper()) is True
    assert beta_capabilities.is_pr_shadow_enabled(other_org) is False


def test_pr_shadow_never_enables_publication_capabilities(monkeypatch):
    org = uuid4()
    monkeypatch.setattr(settings, "PR_SHADOW_ORGANIZATION_IDS", str(org))
    assert beta_capabilities.is_pr_shadow_enabled(org) is True
    assert beta_capabilities.is_beta_capability_enabled("pr_review") is False
    assert beta_capabilities.is_beta_capability_enabled("diff_scans") is False
    assert beta_capabilities.is_beta_capability_enabled("pr_shadow") is False


# ---------------------------------------------------------------------------
# Revision identity recorded on the run (service seam: ScanService.create_pr_shadow)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shadow_run_records_base_head_merge_base_and_strategy(db_session):
    _org, _project, repo, _user = await _seed_org_project_repo(db_session)

    scan, _, _ = await ScanService(db_session).create_pr_shadow(
        repo.id,
        pull_request_number=17,
        head_sha=HEAD,
        base_sha=BASE,
        merge_base_sha=MERGE_BASE,
        is_fork=False,
    )

    assert scan.commit_sha == HEAD
    assert scan.base_sha == BASE
    assert scan.merge_base_sha == MERGE_BASE
    assert scan.comparison_strategy == "head_vs_merge_base"
    assert scan.pull_request_number == 17
    assert scan.trigger_type == "pull_request"
    # Full repository at head; never a changed-files-only shortcut.
    assert scan.scan_type == "full"
    assert scan.head_is_fork is False
    assert scan.status.value == "queued"
    assert scan.dispatch_state == "awaiting_dispatch"


@pytest.mark.asyncio
async def test_shadow_run_never_shares_a_branch_identity_with_the_base_repository(db_session):
    _org, _project, repo, _user = await _seed_org_project_repo(db_session)

    scan, _, _ = await ScanService(db_session).create_pr_shadow(
        repo.id,
        pull_request_number=17,
        head_sha=HEAD,
        base_sha=BASE,
        merge_base_sha=MERGE_BASE,
        is_fork=True,
    )

    # A fork branch named "main" must never alias the repository's real branch.
    assert scan.branch_name is None
    assert scan.full_ref_name == "refs/pull/17/head"
    assert scan.head_is_fork is True


@pytest.mark.asyncio
async def test_shadow_run_without_resolvable_merge_base_is_recorded_not_guessed(db_session):
    _org, _project, repo, _user = await _seed_org_project_repo(db_session)

    scan, _, _ = await ScanService(db_session).create_pr_shadow(
        repo.id,
        pull_request_number=17,
        head_sha=HEAD,
        base_sha=BASE,
        merge_base_sha=None,
        is_fork=False,
    )

    assert scan.merge_base_sha is None
    assert scan.base_sha == BASE


@pytest.mark.asyncio
async def test_shadow_run_requires_exact_head_sha(db_session):
    _org, _project, repo, _user = await _seed_org_project_repo(db_session)

    for bad in (None, "", "cafebabe", "z" * 40):
        with pytest.raises(ValueError):
            await ScanService(db_session).create_pr_shadow(
                repo.id,
                pull_request_number=17,
                head_sha=bad,
                base_sha=BASE,
                merge_base_sha=MERGE_BASE,
                is_fork=False,
            )


@pytest.mark.asyncio
async def test_fork_run_receives_no_installation_credentials_for_clone(db_session, monkeypatch):
    _org, project, repo, _user = await _seed_org_project_repo(db_session)
    scan, _, _ = await ScanService(db_session).create_pr_shadow(
        repo.id, pull_request_number=17, head_sha=HEAD, base_sha=BASE, merge_base_sha=MERGE_BASE, is_fork=True
    )
    worker_id = uuid4()
    scan.current_attempt_id, scan.execution_revision = "attempt-1", 1
    scan.worker_incarnation_id, scan.lease_owner = "inc-1", str(worker_id)
    scan.lease_expires_at = datetime.now(UTC) + timedelta(minutes=2)
    await db_session.commit()

    class _NoGitHub:
        def __init__(self, _db):
            raise AssertionError("a fork run must never mint an installation token")

    monkeypatch.setattr(internal, "GitHubService", _NoGitHub)
    principal = WorkerPrincipal(
        worker_id=worker_id, organization_id=UUID(str(project.organization_id)), capabilities=frozenset()
    )

    response = await internal.get_repository_clone_url(
        repo_id=UUID(str(repo.id)),
        principal=principal,
        attempt=internal.ExecutionAttemptIdentity("attempt-1", 1, "inc-1"),
        db=db_session,
    )

    assert response["clone_url"] == "https://github.com/acme/core-platform.git"
    assert response["auth_header"] == ""


@pytest.mark.asyncio
async def test_shadow_redelivery_returns_the_same_run_and_new_head_creates_a_new_one(db_session):
    _org, _project, repo, _user = await _seed_org_project_repo(db_session)
    service = ScanService(db_session)
    kwargs = {"pull_request_number": 17, "base_sha": BASE, "merge_base_sha": MERGE_BASE, "is_fork": False}

    first, _, _ = await service.create_pr_shadow(repo.id, head_sha=HEAD, **kwargs)
    again, _, _ = await service.create_pr_shadow(repo.id, head_sha=HEAD, **kwargs)
    pushed, _, _ = await service.create_pr_shadow(repo.id, head_sha=HEAD_2, **kwargs)

    assert again.id == first.id
    assert pushed.id != first.id
    obligations = (await db_session.execute(select(ScanDispatchObligation))).scalars().all()
    assert len(obligations) == 2
    assert not (await db_session.execute(select(Finding))).scalars().all()
