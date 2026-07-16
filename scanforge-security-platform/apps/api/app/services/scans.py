from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import ScanStatus as ScanStatusEnum
from app.db.models import Organization, OrganizationMember, Project, Repository, Scan, ScannerRun
from app.schemas.scans import ScanCreate


class ScanService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        repo_id: UUID,
        data: ScanCreate,
        user_id: UUID | None,
    ) -> tuple[Scan, Repository, Project]:
        repo = await self.db.get(Repository, repo_id)
        if not repo:
            raise ValueError("Repository not found")

        project = await self.db.get(Project, repo.project_id)
        if not project:
            raise ValueError("Project not found")

        scan = Scan(
            project_id=repo.project_id,
            repository_id=repo_id,
            trigger_type=data.trigger_type,
            scan_type=data.scan_type,
            status=ScanStatusEnum.QUEUED,
            branch_name=data.branch_name or repo.default_branch,
            commit_sha=data.commit_sha,
            pull_request_number=data.pull_request_number,
            requested_by_user_id=user_id,
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
    ) -> Scan | None:
        scan = await self.db.get(Scan, scan_id)
        if not scan:
            return None

        scan.status = status
        if error_message:
            scan.error_message = error_message
        if summary_json:
            scan.summary_json = summary_json

        await self.db.commit()
        await self.db.refresh(scan)
        return scan

    async def cancel(self, scan_id: UUID, reason: str | None = None, user_id: UUID | None = None) -> Scan | None:
        if user_id is not None:
            scan = await self.get_by_id(scan_id, user_id)
        else:
            scan = await self.db.get(Scan, scan_id)
        if not scan:
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
    ) -> Scan | None:
        scan = await self.get_by_id(scan_id, user_id)
        if not scan:
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

    async def create_scanner_run(
        self,
        scan_id: UUID,
        scanner_name: str,
        scanner_version: str | None = None,
    ) -> ScannerRun:
        run = ScannerRun(
            scan_id=scan_id,
            scanner_name=scanner_name,
            scanner_version=scanner_version,
            status=ScanStatusEnum.QUEUED,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def update_scanner_run(
        self,
        run_id: UUID,
        status: ScanStatusEnum,
        duration_ms: int | None = None,
        exit_code: int | None = None,
        error_message: str | None = None,
        artifact_uri: str | None = None,
        metadata_json: dict | None = None,
    ) -> ScannerRun | None:
        run = await self.db.get(ScannerRun, run_id)
        if not run:
            return None

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
