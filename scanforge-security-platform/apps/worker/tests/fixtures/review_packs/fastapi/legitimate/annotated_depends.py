from typing import Annotated

from fastapi import APIRouter, Depends, Security

from .deps import get_current_user, get_scoped_user

router = APIRouter()


@router.get("/me")
async def read_me(user: Annotated[dict, Depends(get_current_user)]):
    return user


@router.get("/scopes")
async def read_scopes(user: dict = Security(get_scoped_user, scopes=["read"])):
    return user


@router.get("/scoped")
async def read_scoped(user: Annotated[dict, Security(get_scoped_user, scopes=["read"])]):
    return user
