from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.projects import ProjectService
from app.services.repositories import RepositoryService


async def get_project_in_org_or_404(
    db: AsyncSession,
    *,
    project_id: UUID,
    org_id: UUID,
    user_id: UUID,
):
    project = await ProjectService(db).get_by_id(project_id, user_id)
    if not project or project.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def get_repository_in_project_or_404(
    db: AsyncSession,
    *,
    repo_id: UUID,
    project_id: UUID,
    user_id: UUID,
):
    repo = await RepositoryService(db).get_by_id(repo_id, user_id)
    if not repo or repo.project_id != project_id:
        raise HTTPException(status_code=404, detail="Repository not found in this project")
    return repo
