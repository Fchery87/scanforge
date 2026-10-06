from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Configure asyncpg to use SSL via connect_args
# asyncpg doesn't understand sslmode, so we extract it and use ssl parameter instead
connect_args = {"ssl": True} if settings.DATABASE_URL.startswith("postgresql") else {}
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
