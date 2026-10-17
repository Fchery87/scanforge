"""Task M06 verification: repository authority, exact revisions, and branch generation continuity.

Exercises:
1. Connecting user installation access verification, foreign-installation denial,
   and unverified-binding rejection.
2. Repository connection binding by immutable provider ID (`external_repo_id`)
   before uniqueness reservation.
3. Rename within same installation (preserves repository ID and scan history) vs.
   transfer across owners/installations (requires reauthorization, revokes clone/scan
   access, never transfers history).
4. Exact revision, full ref preservation (`refs/heads/...`), default vs. manual
   branch scope, and provider-backed ancestry continuity (`verified_initial`,
   `verified_descendant`, `same_revision`, `diverged_reset`, `unknown_reset`,
   `recreated_reset`).
5. Real local Git repository fixture with worker `ScanExecutionStage.prepare_repository`
   proving queued branch movement checks out the exact queued SHA (never branch tip)
   and inaccessible/pruned SHAs fail explicitly.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import CHAR, TypeDecorator

from app.api.v1.routes import github as github_routes
from app.api.v1.routes import internal as internal_routes
from app.db.base import Base
from app.db.models import (
    Organization,
    OrganizationIntegration,
    OrganizationMember,
    Project,
    Repository,
    RepositoryBranchGeneration,
    RepositoryIntegration,
    Scan,
    User,
)
from app.middleware.service_auth import WorkerPrincipal
from app.schemas.github import GitHubConnectRequest, GitHubOAuthCallbackRequest, GitHubRepoItem
from app.schemas.repositories import RepositoryConnect
from app.schemas.scans import ScanCreate
from app.services.github import (
    GitHubInstallationAccessError,
    GitHubInstallationConflictError,
    GitHubRevisionNotFoundError,
    GitHubService,
)
from app.services.repositories import (
    RepositoryAuthorizationError,
    RepositoryConflictError,
    RepositoryService,
)
from app.services.repository_refs import (
    RepositoryRefError,
    RepositoryRefService,
    RepositoryScopeError,
)
from app.services.scans import ScanService


class _SQLiteUUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR())

    def bind_processor(self, dialect):
        if dialect.name == "postgresql":
            return None

        def process(value):
            return str(value) if value is not None else None

        return process


@compiles(JSONB, "sqlite")
def _pg_jsonb_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


@compiles(INET, "sqlite")
def _pg_inet_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "VARCHAR(45)"


def _downcast_postgres_uuid_columns() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = _SQLiteUUID()


_downcast_postgres_uuid_columns()


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    _downcast_postgres_uuid_columns()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _seed_two_tenants(session):
    user_a, user_b = uuid4(), uuid4()
    org_a, org_b = uuid4(), uuid4()
    proj_a, proj_b = uuid4(), uuid4()

    session.add_all(
        [
            User(id=str(user_a), auth_provider_user_id=f"u-{user_a}", email="a@example.com"),
            User(id=str(user_b), auth_provider_user_id=f"u-{user_b}", email="b@example.com"),
            Organization(id=str(org_a), name="Org A", slug=f"org-a-{org_a}", created_by_user_id=str(user_a)),
            Organization(id=str(org_b), name="Org B", slug=f"org-b-{org_b}", created_by_user_id=str(user_b)),
            OrganizationMember(id=str(uuid4()), organization_id=str(org_a), user_id=str(user_a), role="owner"),
            OrganizationMember(id=str(uuid4()), organization_id=str(org_b), user_id=str(user_b), role="owner"),
            Project(
                id=str(proj_a),
                organization_id=str(org_a),
                name="Proj A",
                slug=f"proj-a-{proj_a}",
                created_by_user_id=str(user_a),
            ),
            Project(
                id=str(proj_b),
                organization_id=str(org_b),
                name="Proj B",
                slug=f"proj-b-{proj_b}",
                created_by_user_id=str(user_b),
            ),
        ]
    )
    await session.commit()
    return {
        "user_a": user_a,
        "user_b": user_b,
        "org_a": org_a,
        "org_b": org_b,
        "proj_a": proj_a,
        "proj_b": proj_b,
    }


@pytest.mark.asyncio
async def test_installation_binding_verifies_user_access_and_rejects_foreign_or_unverified_binding(
    db_session,
    monkeypatch,
):
    tenants = await _seed_two_tenants(db_session)
    gh = GitHubService(db_session)

    # 1. Unverified installation details cannot be silently bound
    monkeypatch.setattr(
        gh,
        "_get_installation_details",
        AsyncMock(side_effect=RuntimeError("GitHub 404 installation not found")),
    )
    with pytest.raises(GitHubInstallationAccessError):
        await gh.save_integration(
            tenants["org_a"],
            GitHubConnectRequest(installation_id="inst-unverified", state="s"),
        )
    assert await gh.get_integration(tenants["org_a"]) is None

    # 2. Connecting user lacking installation access in /user/installations is rejected
    monkeypatch.setattr(
        gh,
        "_exchange_code_for_user_token",
        AsyncMock(return_value="ghu_test_token"),
    )
    monkeypatch.setattr(
        gh,
        "_get_user_installation",
        AsyncMock(
            side_effect=GitHubInstallationAccessError(
                "Connecting user does not have access to the requested GitHub installation."
            )
        ),
    )
    with pytest.raises(GitHubInstallationAccessError):
        await gh.handle_oauth_callback(
            GitHubOAuthCallbackRequest(code="oauth-code", state="s", installation_id="inst-999"),
            "https://app.scanforge.test/github/callback",
            tenants["org_a"],
        )
    assert await gh.get_integration(tenants["org_a"]) is None

    # 3. Verified user installation binds cleanly to Org A
    monkeypatch.setattr(
        gh,
        "_get_user_installation",
        AsyncMock(
            return_value={
                "id": 77001,
                "account": {"login": "acme-sec", "type": "Organization"},
            }
        ),
    )
    bound_a = await gh.handle_oauth_callback(
        GitHubOAuthCallbackRequest(code="oauth-code", state="s", installation_id="77001"),
        "https://app.scanforge.test/github/callback",
        tenants["org_a"],
    )
    assert bound_a.installation_id == "77001"
    assert bound_a.account_login == "acme-sec"

    # 4. Org B attempting to bind Org A's installation 77001 is rejected before touching provider or DB
    with pytest.raises(GitHubInstallationConflictError):
        await gh.save_integration(
            tenants["org_b"],
            GitHubConnectRequest(installation_id="77001", state="s"),
            verified_installation={"id": 77001, "account": {"login": "acme-sec", "type": "Organization"}},
        )
    assert await gh.get_integration(tenants["org_b"]) is None


@pytest.mark.asyncio
async def test_repository_binding_uses_immutable_provider_id_and_rejects_foreign_installation(
    db_session,
):
    tenants = await _seed_two_tenants(db_session)
    db_session.add(
        OrganizationIntegration(
            organization_id=tenants["org_a"],
            provider="github",
            installation_id="77001",
            account_login="acme-sec",
            account_type="Organization",
        )
    )
    await db_session.commit()

    repo_service = RepositoryService(db_session)

    # Provider verifier returning authoritative metadata with immutable ID 900123
    provider_verifier = SimpleNamespace(
        get_installation_repository=AsyncMock(
            return_value={
                "external_repo_id": "900123",
                "owner_name": "acme-sec",
                "repo_name": "payments-api",
                "full_name": "acme-sec/payments-api",
                "default_branch": "main",
                "clone_url": "https://github.com/acme-sec/payments-api.git",
                "html_url": "https://github.com/acme-sec/payments-api",
            }
        )
    )

    # 1. Org B (without installation 77001) cannot bind a repository claiming installation 77001
    with pytest.raises(RepositoryAuthorizationError):
        await repo_service.connect(
            tenants["proj_b"],
            RepositoryConnect(
                provider="github",
                external_repo_id="900123",
                owner_name="acme-sec",
                repo_name="payments-api",
                full_name="acme-sec/payments-api",
                installation_id="77001",
            ),
            tenants["user_b"],
            provider_verifier=provider_verifier,
        )

    # 2. Org A connects repository — server derives RepositoryIntegration from verified org integration
    connected = await repo_service.connect(
        tenants["proj_a"],
        RepositoryConnect(
            provider="github",
            external_repo_id="900123",
            owner_name="acme-sec",
            repo_name="payments-api",
            full_name="acme-sec/payments-api",
            default_branch="main",
        ),
        tenants["user_a"],
        provider_verifier=provider_verifier,
    )
    assert connected.external_repo_id == "900123"
    assert connected.lifecycle_state == "connected"
    integration = await repo_service.get_integration(UUID(str(connected.id)))
    assert integration is not None
    assert integration.installation_id == "77001"

    # 3. Duplicate binding by immutable external_repo_id (even under a different mutable name) conflicts
    with pytest.raises(RepositoryConflictError):
        await repo_service.connect(
            tenants["proj_a"],
            RepositoryConnect(
                provider="github",
                external_repo_id="900123",
                owner_name="acme-sec",
                repo_name="payments-api-renamed",
                full_name="acme-sec/payments-api-renamed",
            ),
            tenants["user_a"],
        )


@pytest.mark.asyncio
async def test_repository_rename_preserves_history_while_transfer_requires_reauthorization(
    db_session,
    monkeypatch,
):
    tenants = await _seed_two_tenants(db_session)
    db_session.add(
        OrganizationIntegration(
            organization_id=tenants["org_a"],
            provider="github",
            installation_id="77001",
            account_login="acme-sec",
            account_type="Organization",
        )
    )
    await db_session.commit()

    repo_service = RepositoryService(db_session)
    scan_service = ScanService(db_session)

    repo = await repo_service.connect(
        tenants["proj_a"],
        RepositoryConnect(
            provider="github",
            external_repo_id="900555",
            owner_name="acme-sec",
            repo_name="legacy-name",
            full_name="acme-sec/legacy-name",
            default_branch="main",
        ),
        tenants["user_a"],
    )
    original_repo_id = str(repo.id)

    sha_1 = "1" * 40
    scan_1, _, _ = await scan_service.create(
        UUID(original_repo_id),
        ScanCreate(
            repository_id=UUID(original_repo_id),
            trigger_type="manual",
            scan_type="full",
            branch_name="main",
            commit_sha=sha_1,
        ),
        tenants["user_a"],
        require_exact_sha=True,
    )

    # 1. Rename within the same installation/owner preserves Repository.id and scan history
    renamed = await repo_service.reconcile_rename_or_transfer(
        external_repo_id="900555",
        new_owner_name="acme-sec",
        new_repo_name="modern-name",
        new_full_name="acme-sec/modern-name",
        installation_id="77001",
        installation_accessible=True,
    )
    assert renamed is not None
    assert str(renamed.id) == original_repo_id
    assert renamed.repo_name == "modern-name"
    assert renamed.full_name == "acme-sec/modern-name"
    assert renamed.is_active is True
    assert renamed.lifecycle_state == "connected"

    scans_after_rename, total = await scan_service.list_for_repository(
        UUID(original_repo_id),
        tenants["user_a"],
    )
    assert total == 1
    assert str(scans_after_rename[0].id) == str(scan_1.id)

    # 2. Transfer to a different owner/installation marks repository reauthorization_required
    transferred = await repo_service.reconcile_rename_or_transfer(
        external_repo_id="900555",
        new_owner_name="other-corp",
        new_repo_name="modern-name",
        new_full_name="other-corp/modern-name",
        installation_id="88999",
        installation_accessible=False,
    )
    assert transferred is not None
    assert str(transferred.id) == original_repo_id
    assert transferred.project_id == str(tenants["proj_a"])
    assert transferred.is_active is False
    assert transferred.lifecycle_state == "reauthorization_required"

    # Disallow new scans and clone-url access while reauthorization is required
    with pytest.raises(ValueError, match="revalidation"):
        await scan_service.create(
            UUID(original_repo_id),
            ScanCreate(
                repository_id=UUID(original_repo_id),
                trigger_type="manual",
                scan_type="full",
                branch_name="main",
                commit_sha="2" * 40,
            ),
            tenants["user_a"],
        )

    principal = WorkerPrincipal(
        worker_id=uuid4(),
        organization_id=tenants["org_a"],
        capabilities=frozenset({"repositories:clone"}),
    )
    with pytest.raises(HTTPException) as exc_info:
        await internal_routes.get_repository_clone_url(
            repo_id=UUID(original_repo_id),
            principal=principal,
            db=db_session,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_branch_generations_ancestry_receipts_and_scope_enforcement(db_session):
    tenants = await _seed_two_tenants(db_session)
    db_session.add(
        OrganizationIntegration(
            organization_id=tenants["org_a"],
            provider="github",
            installation_id="77001",
            account_login="acme-sec",
            account_type="Organization",
        )
    )
    await db_session.commit()

    repo_service = RepositoryService(db_session)
    scan_service = ScanService(db_session)
    ref_service = RepositoryRefService(db_session)

    repo = await repo_service.connect(
        tenants["proj_a"],
        RepositoryConnect(
            provider="github",
            external_repo_id="900777",
            owner_name="acme-sec",
            repo_name="core-service",
            full_name="acme-sec/core-service",
            default_branch="main",
        ),
        tenants["user_a"],
    )
    repo_uuid = UUID(str(repo.id))

    # 1. Automatic push scan on non-default branch is rejected; manual scan on slash branch is allowed
    with pytest.raises(RepositoryScopeError):
        await scan_service.create(
            repo_uuid,
            ScanCreate(
                repository_id=repo_uuid,
                trigger_type="webhook",
                scan_type="full",
                branch_name="refs/heads/release/2026-10",
                commit_sha="a" * 40,
            ),
            None,
            require_exact_sha=True,
        )

    manual_release_scan, _, _ = await scan_service.create(
        repo_uuid,
        ScanCreate(
            repository_id=repo_uuid,
            trigger_type="manual",
            scan_type="full",
            branch_name="refs/heads/release/2026-10",
            commit_sha="a" * 40,
        ),
        tenants["user_a"],
        require_exact_sha=True,
    )
    assert manual_release_scan.branch_name == "release/2026-10"
    assert manual_release_scan.full_ref_name == "refs/heads/release/2026-10"
    assert manual_release_scan.branch_generation_number == 1
    assert manual_release_scan.ancestry_status == "verified_initial"
    assert manual_release_scan.summary_json["coverage_scope"]["branch_scope"] == "manual_branch"
    assert manual_release_scan.summary_json["coverage_scope"]["absence_credit_eligible"] is False

    # 2. Default branch initial commit -> descendant commit -> same-SHA rerun -> force-push -> recreation
    sha_c1 = "1" * 40
    sha_c2 = "2" * 40
    sha_c3_force = "3" * 40
    sha_c4_unknown = "4" * 40
    sha_c5_recreated = "5" * 40

    s1, _, _ = await scan_service.create(
        repo_uuid,
        ScanCreate(
            repository_id=repo_uuid,
            trigger_type="webhook",
            scan_type="full",
            branch_name="refs/heads/main",
            commit_sha=sha_c1,
        ),
        None,
        require_exact_sha=True,
    )
    assert s1.branch_generation_number == 1
    assert s1.ancestry_status == "verified_initial"
    assert s1.summary_json["coverage_scope"]["absence_credit_eligible"] is False

    # Verified descendant (ahead) stays in generation 1 and is eligible for absence observation
    async def _compare_ahead(base: str, head: str):
        return {"status": "ahead", "ahead_by": 2, "behind_by": 0, "base_sha": base, "head_sha": head}

    s2, _, _ = await scan_service.create(
        repo_uuid,
        ScanCreate(
            repository_id=repo_uuid,
            trigger_type="webhook",
            scan_type="full",
            branch_name="main",
            commit_sha=sha_c2,
        ),
        None,
        compare_fn=_compare_ahead,
        require_exact_sha=True,
    )
    assert s2.branch_generation_number == 1
    assert s2.ancestry_status == "verified_descendant"
    assert s2.summary_json["coverage_scope"]["absence_credit_eligible"] is True

    # Same-SHA rerun keeps generation 1 but never grants absence credit
    s2_rerun, _, _ = await scan_service.create(
        repo_uuid,
        ScanCreate(
            repository_id=repo_uuid,
            trigger_type="manual",
            scan_type="full",
            branch_name="main",
            commit_sha=sha_c2,
        ),
        tenants["user_a"],
        require_exact_sha=True,
    )
    assert s2_rerun.branch_generation_number == 1
    assert s2_rerun.ancestry_status == "same_revision"
    assert s2_rerun.summary_json["coverage_scope"]["absence_credit_eligible"] is False

    # Force-push retires generation 1 and starts generation 2 with diverged_reset
    s3_force, _, _ = await scan_service.create(
        repo_uuid,
        ScanCreate(
            repository_id=repo_uuid,
            trigger_type="webhook",
            scan_type="full",
            branch_name="main",
            commit_sha=sha_c3_force,
        ),
        None,
        force_pushed=True,
        require_exact_sha=True,
    )
    assert s3_force.branch_generation_number == 2
    assert s3_force.ancestry_status == "diverged_reset"
    assert s3_force.summary_json["coverage_scope"]["absence_credit_eligible"] is False

    # Unverifiable ancestry starts generation 3 with unknown_reset
    async def _compare_unknown(base: str, head: str):
        return {"status": "unknown", "base_sha": base, "head_sha": head}

    s4_unknown, _, _ = await scan_service.create(
        repo_uuid,
        ScanCreate(
            repository_id=repo_uuid,
            trigger_type="webhook",
            scan_type="full",
            branch_name="main",
            commit_sha=sha_c4_unknown,
        ),
        None,
        compare_fn=_compare_unknown,
        require_exact_sha=True,
    )
    assert s4_unknown.branch_generation_number == 3
    assert s4_unknown.ancestry_status == "unknown_reset"
    assert s4_unknown.summary_json["coverage_scope"]["absence_credit_eligible"] is False

    # Branch deletion retires generation 3; recreating the branch starts generation 4 with recreated_reset
    retired = await ref_service.retire_branch(repo_uuid, "refs/heads/main")
    assert retired is not None
    assert retired.generation_number == 3
    assert retired.retired_at is not None

    s5_recreated, _, _ = await scan_service.create(
        repo_uuid,
        ScanCreate(
            repository_id=repo_uuid,
            trigger_type="webhook",
            scan_type="full",
            branch_name="refs/heads/main",
            commit_sha=sha_c5_recreated,
        ),
        None,
        require_exact_sha=True,
    )
    assert s5_recreated.branch_generation_number == 4
    assert s5_recreated.ancestry_status == "recreated_reset"
    assert s5_recreated.summary_json["coverage_scope"]["absence_credit_eligible"] is False

    generations = (
        await db_session.execute(
            select(RepositoryBranchGeneration)
            .where(
                RepositoryBranchGeneration.repository_id == str(repo_uuid),
                RepositoryBranchGeneration.full_ref_name == "refs/heads/main",
            )
            .order_by(RepositoryBranchGeneration.generation_number.asc())
        )
    ).scalars().all()
    assert [g.generation_number for g in generations] == [1, 2, 3, 4]
    assert [g.retired_at is not None for g in generations] == [True, True, True, False]


@pytest.mark.asyncio
async def test_worker_checkout_verifies_exact_sha_under_queued_branch_movement_and_rejects_inaccessible_sha(
    monkeypatch,
    tmp_path: Path,
):
    """Real local Git fixture proving worker checkout pins exact queued SHA and rejects missing SHAs."""
    worker_root = Path(__file__).resolve().parents[2] / "worker"
    saved_app_modules = {
        k: v for k, v in list(sys.modules.items()) if k == "app" or k.startswith("app.")
    }
    for k in saved_app_modules:
        sys.modules.pop(k, None)
    sys.path.insert(0, str(worker_root))

    try:
        from app.services.scan_pipeline import context as context_mod
        from app.services.scan_pipeline import execution as execution_mod

        # Build a real local Git repository with commit 1 (queued target) and commit 2 (moved branch tip)
        origin_repo = tmp_path / "origin_repo"
        origin_repo.mkdir()
        git_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "GIT_AUTHOR_NAME": "ScanForge Test",
            "GIT_AUTHOR_EMAIL": "test@scanforge.local",
            "GIT_COMMITTER_NAME": "ScanForge Test",
            "GIT_COMMITTER_EMAIL": "test@scanforge.local",
        }
        subprocess.run(["git", "init", "-b", "main", str(origin_repo)], check=True, env=git_env)
        (origin_repo / "service.py").write_text("REVISION = 'queued-commit-1'\n")
        subprocess.run(["git", "-C", str(origin_repo), "add", "service.py"], check=True, env=git_env)
        subprocess.run(["git", "-C", str(origin_repo), "commit", "-m", "Commit 1"], check=True, env=git_env)
        sha_commit_1 = (
            subprocess.run(
                ["git", "-C", str(origin_repo), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            .stdout.strip()
            .lower()
        )

        # Branch advances to Commit 2 while the scan for Commit 1 is still queued
        (origin_repo / "service.py").write_text("REVISION = 'moved-branch-tip-2'\n")
        subprocess.run(["git", "-C", str(origin_repo), "add", "service.py"], check=True, env=git_env)
        subprocess.run(["git", "-C", str(origin_repo), "commit", "-m", "Commit 2"], check=True, env=git_env)
        sha_commit_2 = (
            subprocess.run(
                ["git", "-C", str(origin_repo), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            .stdout.strip()
            .lower()
        )
        assert sha_commit_1 != sha_commit_2

        workspace_root = tmp_path / "workspaces"
        workspace_root.mkdir()
        monkeypatch.setenv("SCANFORGE_WORKSPACE_ROOT", str(workspace_root))
        monkeypatch.setenv("SCANFORGE_ALLOW_LOCAL_GIT_FIXTURES", "1")
        monkeypatch.setenv("ENVIRONMENT", "development")

        stage = execution_mod.ScanExecutionStage(
            r2=SimpleNamespace(),
            api_base_url="http://api.local",
            worker_credential="worker-secret",
            runtime=SimpleNamespace(),
        )
        monkeypatch.setattr(
            stage,
            "_get_clone_url",
            AsyncMock(return_value=(f"file://{origin_repo}", "Authorization: Basic dGVzdA==")),
        )

        # 1. Queued branch movement: worker checks out exact sha_commit_1, NOT sha_commit_2
        ctx_queued = context_mod.ScanContext(
            scan_id="scan-queued-1",
            organization_id="org-1",
            repository_id="repo-1",
            project_id="proj-1",
            branch="main",
            full_ref_name="refs/heads/main",
            commit_sha=sha_commit_1,
            job_id="job-1",
            attempt_id="attempt-1",
        )
        checked_out_dir = await stage.prepare_repository(ctx_queued)
        head_sha = (
            subprocess.run(
                ["git", "-C", str(checked_out_dir), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            .stdout.strip()
            .lower()
        )
        assert head_sha == sha_commit_1
        assert ctx_queued.verified_commit_sha == sha_commit_1
        assert (checked_out_dir / "service.py").read_text() == "REVISION = 'queued-commit-1'\n"

        # 2. Inaccessible / force-pushed-away SHA fails explicitly and never substitutes branch tip
        inaccessible_sha = "f" * 40
        ctx_missing = context_mod.ScanContext(
            scan_id="scan-missing-1",
            organization_id="org-1",
            repository_id="repo-1",
            project_id="proj-1",
            branch="main",
            full_ref_name="refs/heads/main",
            commit_sha=inaccessible_sha,
            job_id="job-2",
            attempt_id="attempt-1",
        )
        with pytest.raises(RuntimeError, match=inaccessible_sha):
            await stage.prepare_repository(ctx_missing)
    finally:
        for k in list(sys.modules.keys()):
            if k == "app" or k.startswith("app."):
                sys.modules.pop(k, None)
        sys.modules.update(saved_app_modules)
        if str(worker_root) in sys.path:
            sys.path.remove(str(worker_root))
