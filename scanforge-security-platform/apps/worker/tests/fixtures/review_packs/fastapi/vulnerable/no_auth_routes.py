from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter()


@router.get("/projects")
async def list_projects():
    return []


@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    return {"deleted": project_id}
