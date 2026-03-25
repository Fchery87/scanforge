from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Finding,
    FindingEvent,
    FindingInstance,
    FindingReference,
    Organization,
    OrganizationMember,
    Project,
)
from app.schemas.findings import (
    FindingStats,
)


class FindingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_project(
        self,
        project_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50,
        severity: str | None = None,
        category: str | None = None,
        status: str | None = None,
        scanner: str | None = None,
        repository_id: UUID | None = None,
        search: str | None = None,
    ) -> tuple[list[Finding], int]:
        base_query = (
            select(Finding)
            .join(Project, Finding.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Finding.project_id == project_id,
                OrganizationMember.user_id == user_id,
            )
        )

        if severity:
            base_query = base_query.where(Finding.severity == severity)
        if category:
            base_query = base_query.where(Finding.category == category)
        if status:
            base_query = base_query.where(Finding.status == status)
        if scanner:
            base_query = base_query.where(Finding.primary_scanner == scanner)
        if repository_id:
            base_query = base_query.where(Finding.repository_id == repository_id)
        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(
                or_(
                    Finding.title.ilike(search_term),
                    Finding.description.ilike(search_term),
                )
            )

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        result = await self.db.execute(
            base_query.order_by(Finding.created_at.desc()).offset(skip).limit(limit)
        )
        findings = list(result.scalars().all())

        return findings, total

    async def get_by_id(
        self,
        finding_id: UUID,
        user_id: UUID,
    ) -> Finding | None:
        result = await self.db.execute(
            select(Finding)
            .join(Project, Finding.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .options(
                selectinload(Finding.instances),
                selectinload(Finding.references),
                selectinload(Finding.events),
            )
            .where(
                Finding.id == finding_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_scan(
        self,
        scan_id: str,
        repository_id: str,
        project_id: str,
        normalized_findings: list[dict],
    ) -> tuple[int, int]:
        new_count = 0
        updated_count = 0

        for finding_data in normalized_findings:
            fingerprint = finding_data["canonical_fingerprint"]
            instance_data = finding_data.pop("instance", None) or {}
            references_data = finding_data.pop("references", None) or []

            existing = await self.db.execute(
                select(Finding).where(
                    and_(
                        Finding.repository_id == repository_id,
                        Finding.canonical_fingerprint == fingerprint,
                    )
                )
            )
            finding = existing.scalar_one_or_none()

            if finding:
                finding.last_seen_at = datetime.now(UTC)
                if finding.status == "fixed":
                    finding.status = "open"
                updated_count += 1
            else:
                finding = Finding(
                    project_id=project_id,
                    repository_id=repository_id,
                    category=finding_data.get("category", "unknown"),
                    severity=finding_data.get("severity", "medium"),
                    status="open",
                    title=finding_data.get("title", "Untitled Finding"),
                    description=finding_data.get("description"),
                    canonical_fingerprint=fingerprint,
                    primary_scanner=finding_data.get("primary_scanner"),
                    confidence_score=finding_data.get("confidence_score"),
                    fixed_version=finding_data.get("fixed_version"),
                    metadata_json=finding_data.get("metadata_json"),
                    first_seen_at=datetime.now(UTC),
                    last_seen_at=datetime.now(UTC),
                )
                self.db.add(finding)
                new_count += 1

            await self.db.flush()

            instance = FindingInstance(
                finding_id=finding.id,
                scan_id=scan_id,
                path=instance_data.get("path"),
                line_start=instance_data.get("line_start"),
                line_end=instance_data.get("line_end"),
                package_name=instance_data.get("package_name"),
                installed_version=instance_data.get("installed_version"),
                fixed_version=instance_data.get("fixed_version"),
                evidence_json=instance_data,
            )
            self.db.add(instance)

            for ref_data in references_data or []:
                reference = FindingReference(
                    finding_id=finding.id,
                    reference_type=ref_data.get("type", "unknown"),
                    reference_value=ref_data.get("value", ""),
                    url=ref_data.get("url"),
                )
                self.db.add(reference)

        await self.db.commit()
        return new_count, updated_count

    async def suppress(
        self,
        finding_id: UUID,
        user_id: UUID,
        reason: str,
        rule_id: UUID | None = None,
    ) -> Finding | None:
        finding = await self.db.get(Finding, finding_id)
        if not finding:
            return None

        finding.status = "suppressed"

        event = FindingEvent(
            finding_id=finding_id,
            event_type="suppressed",
            actor_user_id=user_id,
            reason=reason,
            metadata_json={"rule_id": str(rule_id)} if rule_id else None,
        )
        self.db.add(event)

        await self.db.commit()
        await self.db.refresh(finding)
        return finding

    async def resolve(
        self,
        finding_id: UUID,
        user_id: UUID,
        fixed_version: str | None = None,
        reason: str | None = None,
    ) -> Finding | None:
        finding = await self.db.get(Finding, finding_id)
        if not finding:
            return None

        finding.status = "fixed"
        if fixed_version:
            finding.fixed_version = fixed_version

        event = FindingEvent(
            finding_id=finding_id,
            event_type="fixed",
            actor_user_id=user_id,
            reason=reason,
            metadata_json={"fixed_version": fixed_version} if fixed_version else None,
        )
        self.db.add(event)

        await self.db.commit()
        await self.db.refresh(finding)
        return finding

    async def reopen(
        self,
        finding_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> Finding | None:
        finding = await self.db.get(Finding, finding_id)
        if not finding:
            return None

        finding.status = "open"

        event = FindingEvent(
            finding_id=finding_id,
            event_type="reopened",
            actor_user_id=user_id,
            reason=reason,
        )
        self.db.add(event)

        await self.db.commit()
        await self.db.refresh(finding)
        return finding

    async def get_events(
        self,
        finding_id: UUID,
        user_id: UUID,
    ) -> list[FindingEvent]:
        finding = await self.get_by_id(finding_id, user_id)
        if not finding:
            return []
        return finding.events or []

    async def get_stats(
        self,
        project_id: UUID,
        user_id: UUID,
        repository_id: UUID | None = None,
    ) -> FindingStats:
        repo_filter = [Finding.repository_id == repository_id] if repository_id else []
        base_where = (
            select(Finding)
            .join(Project, Finding.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Finding.project_id == project_id,
                OrganizationMember.user_id == user_id,
                *repo_filter,
            )
        )

        total = await self.db.scalar(select(func.count()).select_from(base_where.subquery())) or 0

        open_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(Finding)
                .join(Project, Finding.project_id == Project.id)
                .join(Organization, Project.organization_id == Organization.id)
                .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                .where(
                    Finding.project_id == project_id,
                    OrganizationMember.user_id == user_id,
                    Finding.status == "open",
                    *repo_filter,
                )
            )
            or 0
        )

        fixed_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(Finding)
                .join(Project, Finding.project_id == Project.id)
                .join(Organization, Project.organization_id == Organization.id)
                .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                .where(
                    Finding.project_id == project_id,
                    OrganizationMember.user_id == user_id,
                    Finding.status == "fixed",
                    *repo_filter,
                )
            )
            or 0
        )

        suppressed_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(Finding)
                .join(Project, Finding.project_id == Project.id)
                .join(Organization, Project.organization_id == Organization.id)
                .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                .where(
                    Finding.project_id == project_id,
                    OrganizationMember.user_id == user_id,
                    Finding.status == "suppressed",
                    *repo_filter,
                )
            )
            or 0
        )

        severity_counts = {}
        for sev in ["critical", "high", "medium", "low", "info"]:
            count = (
                await self.db.scalar(
                    select(func.count())
                    .select_from(Finding)
                    .join(Project)
                    .join(OrganizationMember)
                    .where(
                        Finding.project_id == project_id,
                        OrganizationMember.user_id == user_id,
                        Finding.severity == sev,
                        Finding.status == "open",
                        *repo_filter,
                    )
                )
                or 0
            )
            severity_counts[sev] = count

        category_counts = {}
        categories = ["vulnerability", "secret", "dependency_outdated", "code_quality"]
        for cat in categories:
            count = (
                await self.db.scalar(
                    select(func.count())
                    .select_from(Finding)
                    .join(Project)
                    .join(OrganizationMember)
                    .where(
                        Finding.project_id == project_id,
                        OrganizationMember.user_id == user_id,
                        Finding.category == cat,
                        Finding.status == "open",
                    )
                )
                or 0
            )
            category_counts[cat] = count

        return FindingStats(
            total=total,
            open=open_count,
            fixed=fixed_count,
            suppressed=suppressed_count,
            by_severity=severity_counts,
            by_category=category_counts,
        )

    async def bulk_suppress(
        self,
        finding_ids: list[UUID],
        user_id: UUID,
        reason: str,
    ) -> int:
        count = 0
        for finding_id in finding_ids:
            result = await self.suppress(finding_id, user_id, reason)
            if result:
                count += 1
        return count

    async def bulk_resolve(
        self,
        finding_ids: list[UUID],
        user_id: UUID,
        fixed_version: str | None = None,
    ) -> int:
        count = 0
        for finding_id in finding_ids:
            result = await self.resolve(finding_id, user_id, fixed_version)
            if result:
                count += 1
        return count
