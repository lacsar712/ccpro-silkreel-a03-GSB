from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Basin, BathReading, Filature, User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()


class BasinRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def board(self) -> Filature | None:
        result = await self.session.execute(
            select(Filature)
            .order_by(Filature.id)
            .options(selectinload(Filature.basins).selectinload(Basin.readings))
        )
        return result.scalars().first()

    async def docks(self) -> list[Filature]:
        result = await self.session.execute(
            select(Filature)
            .order_by(Filature.id)
            .options(selectinload(Filature.basins).selectinload(Basin.readings))
        )
        return list(result.scalars())

    async def get(self, basin_id: int) -> Basin | None:
        result = await self.session.execute(
            select(Basin)
            .options(selectinload(Basin.readings))
            .where(Basin.id == basin_id)
        )
        return result.scalar_one_or_none()

    async def lock_dock_of(self, basin_id: int) -> None:
        """锁住该盆所在坞的行，串行化同坞状态变更，提交前一直持有。"""
        subq = select(Basin.filature_id).where(Basin.id == basin_id).scalar_subquery()
        await self.session.execute(
            select(Filature.id).where(Filature.id == subq).with_for_update()
        )

    async def siblings(self, basin: Basin) -> list[Basin]:
        result = await self.session.execute(
            select(Basin)
            .where(Basin.filature_id == basin.filature_id)
            .order_by(Basin.ring_index)
        )
        return list(result.scalars())

    async def add_reading(self, basin: Basin, temp_c: float, operator: str) -> BathReading:
        row = BathReading(basin=basin, water_temp_c=temp_c, operator=operator)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def save_status(self, basin: Basin, status: str) -> None:
        basin.status = status
        await self.session.commit()
