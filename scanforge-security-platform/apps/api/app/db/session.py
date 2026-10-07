from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def database_connect_args(database_url: str) -> dict:
    """Remote Postgres needs TLS. Local Postgres does not present a usable certificate."""
    if not database_url.startswith("postgresql"):
        return {}
    host = (urlparse(database_url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return {}
    return {"ssl": True}


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=database_connect_args(settings.DATABASE_URL),
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
