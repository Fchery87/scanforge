from fastapi import APIRouter, Depends

from .deps import get_current_user, get_db

router = APIRouter()


@router.get("/projects/{project_id}")
async def read_project(project_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    project = db.get(Project, project_id)
    return project
