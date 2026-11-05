from fastapi import APIRouter, Depends

from .deps import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/reports")
async def list_reports():
    return []


@router.post("/reports")
async def create_report(payload: dict):
    return payload
