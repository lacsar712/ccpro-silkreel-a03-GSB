from datetime import timedelta

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import Basin, BathReading, Filature, User, utcnow
from app.security import hash_password

# (盆号, 状态, 最近汤温, 茧粒)
DOCK_SPECS = [
    (
        "江口缫丝坞",
        "东津渡",
        [
            ("甲-1", Basin.STATUS_REELING, 40.5, 400),
            ("甲-2", Basin.STATUS_SOAKING, None, 520),  # 浸茧甲：与缫丝中盆差 120 刚过
            ("乙-1", Basin.STATUS_SOAKING, None, 600),  # 浸茧乙：差 200 应挡
            ("乙-2", Basin.STATUS_REELED, 39.2, 430),
            ("丙-1", Basin.STATUS_SOAKING, None, 450),
            ("丙-2", Basin.STATUS_REELED, 41.0, 410),
        ],
    ),
    (
        "西山缫丝坞",
        "清溪渡",
        [
            ("丁-1", Basin.STATUS_SOAKING, None, 380),
            ("丁-2", Basin.STATUS_SOAKING, None, 500),
            ("丁-3", Basin.STATUS_REELED, 39.5, 360),
        ],
    ),
]


async def _upsert_user(session, username: str, role: str) -> None:
    row = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    hashed = hash_password("123456")
    if row is None:
        session.add(User(username=username, password_hash=hashed, role=role))
    else:
        row.password_hash = hashed
        row.role = role


async def seed_demo() -> None:
    """每次启动把演示数据对齐到种子规格：状态、茧粒、最近汤温都复位。

    老数据卷里没有茧粒列值，靠这次对齐补上，保证验收初态一致。
    """
    async with SessionLocal() as session:
        await _upsert_user(session, "admin", "admin")
        await _upsert_user(session, "worker", "worker")
        now = utcnow()
        for dock_name, riverside, specs in DOCK_SPECS:
            mill = (
                await session.execute(select(Filature).where(Filature.name == dock_name))
            ).scalar_one_or_none()
            if mill is None:
                mill = Filature(name=dock_name, riverside=riverside)
                session.add(mill)
                await session.flush()
            else:
                mill.riverside = riverside
            for idx, (code, status, temp, grains) in enumerate(specs):
                basin = (
                    await session.execute(
                        select(Basin).where(
                            Basin.filature_id == mill.id, Basin.code == code
                        )
                    )
                ).scalar_one_or_none()
                if basin is None:
                    basin = Basin(filature_id=mill.id, code=code)
                    session.add(basin)
                    await session.flush()
                basin.status = status
                basin.ring_index = idx
                basin.cocoon_grains = grains
                # 最近汤温也对齐：先清再补一条
                await session.execute(
                    delete(BathReading).where(BathReading.basin_id == basin.id)
                )
                if temp is not None:
                    session.add(
                        BathReading(
                            basin_id=basin.id,
                            water_temp_c=temp,
                            operator="worker",
                            taken_at=now - timedelta(hours=2),
                        )
                    )
        await session.commit()
