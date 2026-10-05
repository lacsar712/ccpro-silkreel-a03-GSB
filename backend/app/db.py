from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DATABASE_URL
from app.models import Base

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 老库补列；create_all 不会改已存在的表
        await conn.execute(
            text("ALTER TABLE basins ADD COLUMN IF NOT EXISTS cocoon_grains INTEGER NOT NULL DEFAULT 0")
        )


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
