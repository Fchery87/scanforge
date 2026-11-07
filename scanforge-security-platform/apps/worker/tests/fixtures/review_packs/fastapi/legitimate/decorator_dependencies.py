from fastapi import APIRouter, Depends

from .deps import require_user

router = APIRouter()


@router.get("/reports", dependencies=[Depends(require_user)])
async def list_reports():
    return []
