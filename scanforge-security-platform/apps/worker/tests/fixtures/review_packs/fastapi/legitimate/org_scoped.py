from fastapi import APIRouter, Depends, HTTPException

from .deps import get_db, require_org_member

router = APIRouter()


@router.get("/orgs/{organization_id}/members")
async def list_members(organization_id: str, member=Depends(require_org_member)):
    return await members_for(organization_id)


@router.get("/projects/{project_id}")
async def read_project(project_id: str, member=Depends(require_org_member), db=Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None or project.organization_id != member.organization_id:
        raise HTTPException(status_code=404)
    return project


@router.get("/repos/{repo_id}")
async def read_repo(repo_id: str, member=Depends(require_org_member), db=Depends(get_db)):
    return db.execute(
        select(Repo).where(Repo.id == repo_id, Repo.organization_id == member.organization_id)
    ).scalar_one_or_none()
