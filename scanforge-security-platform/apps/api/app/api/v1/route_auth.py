from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.access_policies import get_project_in_org_for_user, get_repository_in_project_for_user


async def get_project_in_org_or_404(
    db: AsyncSession,
    *,
    project_id: UUID,
    org_id: UUID,
    user_id: UUID,
):
    project = await get_project_in_org_for_user(db, project_id=project_id, org_id=org_id, user_id=user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def get_repository_in_project_or_404(
    db: AsyncSession,
    *,
    repo_id: UUID,
    project_id: UUID,
    user_id: UUID,
):
    repo = await get_repository_in_project_for_user(db, repo_id=repo_id, project_id=project_id, user_id=user_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in this project")
    return repo
