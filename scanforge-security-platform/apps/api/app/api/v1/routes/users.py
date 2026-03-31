from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.auth import UserResponse
from app.services.users import UserService

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await UserService(db).get_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Authenticated user not found")
    return user
