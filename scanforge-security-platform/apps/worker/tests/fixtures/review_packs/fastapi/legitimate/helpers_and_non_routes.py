from fastapi import APIRouter, Depends

from .deps import get_current_user

router = APIRouter()


def load(session, item_id):
    return session.get(Item, item_id)


def read_setting(request, default):
    return request.query_params.get("page", default)


@router.get("/items/{item_id}")
async def read_item(item_id: str, user=Depends(get_current_user)):
    return load_for_user(user, item_id)
