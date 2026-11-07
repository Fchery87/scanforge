from fastapi import APIRouter, Depends

from .deps import get_current_user

router = APIRouter()


@router.get("/orgs/{organization_id}/members")
async def list_members(organization_id: str, user=Depends(get_current_user)):
    return await members_for(organization_id)
