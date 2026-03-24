from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Export, OrganizationMember, Project
from app.schemas.exports import ExportCreate


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        project_id: UUID,
        data: "ExportCreate",
        user_id: UUID,
    ) -> Export:
        project = await self.db.get(Project, str(project_id))
        if not project:
            raise ValueError("Project not found")

        export = Export(
            project_id=str(project_id),
            export_type=data.export_type,
            format=data.format,
            status="pending",
            requested_by_user_id=str(user_id),
            filter_criteria_json=data.filters,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        self.db.add(export)
        await self.db.commit()
        await self.db.refresh(export)
        return export

    async def list_for_project(
        self,
        project_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Export], int]:
        project = await self.db.get(Project, str(project_id))
        if not project:
            return [], 0

        is_member = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == project.organization_id,
                OrganizationMember.user_id == str(user_id),
            )
        )
        if not is_member.scalar_one_or_none():
            return [], 0

        base_query = select(Export).where(Export.project_id == str(project_id))

        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            base_query.order_by(Export.created_at.desc()).offset(skip).limit(limit)
        )

        return list(result.scalars().all()), total

    async def get_by_id(
        self,
        export_id: UUID,
        user_id: UUID,
    ) -> Export | None:
        export = await self.db.get(Export, str(export_id))
        if not export:
            return None

        if export.project_id:
            project = await self.db.get(Project, export.project_id)
            if project:
                is_member = await self.db.execute(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id == project.organization_id,
                        OrganizationMember.user_id == str(user_id),
                    )
                )
                if not is_member.scalar_one_or_none():
                    return None

        return export

    async def update_status(
        self,
        export_id: UUID,
        status: str,
        storage_uri: str | None = None,
        row_count: int | None = None,
        error_message: str | None = None,
    ) -> Export | None:
        export = await self.db.get(Export, str(export_id))
        if not export:
            return None

        export.status = status
        if storage_uri:
            export.storage_uri = storage_uri
        if row_count is not None:
            export.row_count = row_count
        if error_message:
            export.error_message = error_message
        if status == "completed":
            export.completed_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(export)
        return export
