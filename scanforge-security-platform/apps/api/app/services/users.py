from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.schemas.auth import UserCreate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_auth_id(self, auth_provider_user_id: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.auth_provider_user_id == auth_provider_user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, data: UserCreate) -> User:
        user = User(
            auth_provider_user_id=data.auth_provider_user_id,
            email=data.email,
            name=data.name,
            avatar_url=data.avatar_url,
            is_active=True,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_or_create_from_token(self, token_payload: dict) -> User:
        auth_id = token_payload.get("sub", "")
        email = token_payload.get("email", "")
        name = token_payload.get("name")
        avatar_url = token_payload.get("picture")

        user = await self.get_by_auth_id(auth_id)
        if user:
            if name and user.name != name:
                user.name = name
            if avatar_url and user.avatar_url != avatar_url:
                user.avatar_url = avatar_url
            await self.db.commit()
            return user

        user = User(
            auth_provider_user_id=auth_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
            is_active=True,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user_id: UUID, **kwargs) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None

        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def deactivate(self, user_id: UUID) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False

        user.is_active = False
        await self.db.commit()
        return True
