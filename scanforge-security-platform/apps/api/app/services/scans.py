from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import ScanStatus as ScanStatusEnum
from app.db.models import Organization, OrganizationMember, Project, Repository, Scan, ScannerRun
from app.schemas.scans import ScanCreate
from app.services.repository_refs import (
    SCAN_TYPE_SCANNERS,
    RepositoryRefService,
)


class ScanAuthorizationError(Exception):
    """Caller principal is not bound to the organization that owns the scan."""

    code = "scan_org_mismatch"


class ScanService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        repo_id: UUID,
        data: ScanCreate,
        user_id: UUID | None,
        *,
        force_pushed: bool = False,
        ancestry_relation: str | None = None,
        provider_receipt: dict[str, Any] | None = None,
        revision_resolver: Callable[[str, str | None], Awaitable[str]] | None = None,
        compare_fn: Callable[[str, str], Awaitable[dict[str, Any]]] | None = None,
        require_exact_sha: bool = False,
    ) -> tuple[Scan, Repository, Project]:
        repo = (
            await self.db.execute(
                select(Repository)
                .where(Repository.id == repo_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if not repo:
            raise ValueError("Repository not found")
        if not repo.is_active or getattr(repo, "lifecycle_state", "connected") != "connected":
            raise ValueError("Repository is not active or requires authorization revalidation")

        project = await self.db.get(Project, repo.project_id)
        if not project:
            raise ValueError("Project not found")

        ref_service = RepositoryRefService(self.db)
        if (
            data.branch_name
            or repo.default_branch
            or data.trigger_type == "webhook"
            or require_exact_sha
            or revision_resolver is not None
        ):
            resolved = await ref_service.resolve_scan_revision(
                repo=repo,
                trigger_type=data.trigger_type,
                scan_type=data.scan_type,
                branch_or_ref=data.branch_name,
                commit_sha=data.commit_sha,
                force_pushed=force_pushed,
                ancestry_relation=ancestry_relation,
                provider_receipt=provider_receipt,
                revision_resolver=revision_resolver,
                compare_fn=compare_fn,
                require_exact_sha=require_exact_sha,
            )
            branch_name = resolved.branch_name
            full_ref_name = resolved.full_ref_name
            generation_number = resolved.generation_number
            ancestry_status = resolved.ancestry_status
            commit_sha = resolved.commit_sha or data.commit_sha
            expected_scanners = resolved.expected_scanners
            summary_json = {"coverage_scope": resolved.coverage_scope}
        else:
            branch_name = None
            full_ref_name = None
            generation_number = 1
            ancestry_status = "unknown"
            commit_sha = data.commit_sha
            expected_scanners = list(
                SCAN_TYPE_SCANNERS.get(data.scan_type, SCAN_TYPE_SCANNERS["full"])
            )
            summary_json = None

        scan = Scan(
            project_id=repo.project_id,
            repository_id=repo_id,
            trigger_type=data.trigger_type,
            scan_type=data.scan_type,
            status=ScanStatusEnum.QUEUED,
            branch_name=branch_name,
            full_ref_name=full_ref_name,
            branch_generation_number=generation_number,
            ancestry_status=ancestry_status,
            commit_sha=commit_sha,
            base_sha=data.base_sha,
            pull_request_number=data.pull_request_number,
            requested_by_user_id=user_id,
            expected_scanners_json=expected_scanners,
            summary_json=summary_json,
        )
        self.db.add(scan)
        await self.db.commit()
        await self.db.refresh(scan)

        return scan, repo, project

    async def get_by_id(
        self,
        scan_id: UUID,
        user_id: UUID,
    ) -> Scan | None:
        result = await self.db.execute(
            select(Scan)
            .join(Project, Scan.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .options(selectinload(Scan.scanner_runs))
            .where(
                Scan.id == scan_id,
                Scan.deleted_at.is_(None),
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_repository(
        self,
        repo_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Scan], int]:
        repo = await self.db.get(Repository, repo_id)
        if not repo:
            return [], 0

        base_query = (
            select(Scan)
            .join(Project, Scan.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Scan.repository_id == repo_id,
                Scan.deleted_at.is_(None),
                OrganizationMember.user_id == user_id,
            )
        )

        count_result = await self.db.execute(select(func.count()).select_from(base_query.order_by(None).subquery()))
        total = count_result.scalar_one()

        result = await self.db.execute(
            base_query.options(selectinload(Scan.scanner_runs))
            .order_by(Scan.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        scans = list(result.scalars().all())

        return scans, total

    async def list_for_project(
        self,
        project_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
        *,
        status_filter: str | None = None,
    ) -> tuple[list[Scan], int]:
        base_query = (
            select(Scan)
            .join(Project, Scan.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Scan.project_id == project_id,
                Scan.deleted_at.is_(None),
                OrganizationMember.user_id == user_id,
            )
        )

        if status_filter:
            base_query = base_query.where(Scan.status == status_filter)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.order_by(None).subquery()))
        total = count_result.scalar_one()

        result = await self.db.execute(
            base_query.options(selectinload(Scan.scanner_runs))
            .order_by(Scan.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        scans = list(result.scalars().all())

        return scans, total

    async def update_status(
        self,
        scan_id: UUID,
        status: ScanStatusEnum,
        error_message: str | None = None,
        summary_json: dict | None = None,
        *,
        caller_organization_id: UUID,
    ) -> Scan | None:
        scan = await self.db.get(Scan, scan_id)
        if not scan:
            return None
        project = await self.db.get(Project, scan.project_id)
        if project is None or str(project.organization_id) != str(caller_organization_id):
            raise ScanAuthorizationError(
                "Worker principal is not bound to the organization that owns the scan"
            )
        if scan.status in (ScanStatusEnum.CANCELED, ScanStatusEnum.COMPLETED):
            raise ValueError("Terminal scan state cannot be overwritten")
        if status == ScanStatusEnum.COMPLETED:
            raise ValueError("Use atomic completion to complete a scan")

        scan.status = status
        if error_message is not None:
            scan.error_message = error_message
        if summary_json is not None:
            scan.summary_json = summary_json

        await self.db.commit()
        await self.db.refresh(scan)
        return scan

    async def cancel(
        self,
        scan_id: UUID,
        reason: str | None = None,
        user_id: UUID | None = None,
        *,
        project_id: UUID | None = None,
    ) -> Scan | None:
        if user_id is not None:
            scan = await self.get_by_id(scan_id, user_id)
            if scan is None:
                return None
            if project_id is not None and str(scan.project_id) != str(project_id):
                return None
            # Re-read under the row lock so cancellation and completion serialize
            # on the same Scan lock and exactly one terminal winner exists.
            locked = await self.db.execute(
                select(Scan).where(Scan.id == scan_id).with_for_update()
            )
            scan = locked.scalar_one_or_none() or scan
        else:
            locked = await self.db.execute(
                select(Scan).where(Scan.id == scan_id).with_for_update()
            )
            scan = locked.scalar_one_or_none()
        if not scan:
            return None
        if project_id is not None and str(scan.project_id) != str(project_id):
            return None

        if scan.status not in (ScanStatusEnum.QUEUED, ScanStatusEnum.RUNNING):
            raise ValueError("Can only cancel queued or running scans")

        scan.status = ScanStatusEnum.CANCELED
        if reason:
            scan.error_message = reason

        await self.db.commit()
        await self.db.refresh(scan)
        return scan

    async def delete(
        self,
        scan_id: UUID,
        user_id: UUID,
        *,
        project_id: UUID | None = None,
    ) -> Scan | None:
        scan = await self.get_by_id(scan_id, user_id)
        if not scan:
            return None
        if project_id is not None and str(scan.project_id) != str(project_id):
            return None

        if scan.status not in (
            ScanStatusEnum.QUEUED,
            ScanStatusEnum.FAILED,
            ScanStatusEnum.CANCELED,
        ):
            raise ValueError("Only queued, failed, or canceled scans can be deleted; completed scans are retained")

        scan.deleted_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(scan)
        return scan

    async def _scan_project_for_org(
        self,
        scan_id: UUID,
    ) -> tuple[Scan | None, Project | None]:
        scan = await self.db.get(Scan, scan_id)
        if scan is None:
            return None, None
        project = await self.db.get(Project, scan.project_id)
        return scan, project

    async def authorize_scan_access(
        self,
        scan_id: UUID,
        *,
        caller_organization_id: UUID,
    ) -> tuple[Scan, Project] | None:
        """Service-boundary org check for worker-initiated scan mutations.

        Returns (scan, project), None when the scan does not exist, and raises
        ScanAuthorizationError when the caller organization does not own the
        scan's project.
        """
        scan, project = await self._scan_project_for_org(scan_id)
        if scan is None:
            return None
        if project is None or str(project.organization_id) != str(caller_organization_id):
            raise ScanAuthorizationError(
                "Worker principal is not bound to the organization that owns the scan"
            )
        return scan, project

    async def create_scanner_run(
        self,
        scan_id: UUID,
        scanner_name: str,
        scanner_version: str | None = None,
        *,
        status: ScanStatusEnum = ScanStatusEnum.QUEUED,
        caller_organization_id: UUID,
    ) -> ScannerRun | None:
        scan, project = await self._scan_project_for_org(scan_id)
        if scan is None:
            return None
        if project is None or str(project.organization_id) != str(caller_organization_id):
            raise ScanAuthorizationError(
                "Worker principal is not bound to the organization that owns the scan"
            )

        run = ScannerRun(
            scan_id=scan_id,
            scanner_name=scanner_name,
            scanner_version=scanner_version,
            status=status,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def update_scanner_run(
        self,
        run_id: UUID,
        status: ScanStatusEnum | None,
        duration_ms: int | None = None,
        exit_code: int | None = None,
        *,
        error_message: str | None = None,
        artifact_uri: str | None = None,
        metadata_json: dict | None = None,
        caller_organization_id: UUID,
    ) -> ScannerRun | None:
        run = await self.db.get(ScannerRun, run_id)
        if not run:
            return None
        scan, project = await self._scan_project_for_org(UUID(str(run.scan_id)))
        if scan is None:
            return None
        if project is None or str(project.organization_id) != str(caller_organization_id):
            raise ScanAuthorizationError(
                "Worker principal is not bound to the organization that owns the scan"
            )

        if status is not None:
            run.status = status
        if duration_ms is not None:
            run.duration_ms = duration_ms
        if exit_code is not None:
            run.exit_code = exit_code
        if error_message:
            run.error_message = error_message
        if artifact_uri:
            run.artifact_uri = artifact_uri
        if metadata_json:
            run.metadata_json = metadata_json

        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def get_scanner_runs(self, scan_id: UUID) -> list[ScannerRun]:
        result = await self.db.execute(
            select(ScannerRun).where(ScannerRun.scan_id == scan_id).order_by(ScannerRun.created_at)
        )
        return list(result.scalars().all())
