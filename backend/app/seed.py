"""演示种子（幂等对账）。

江口缫丝坞为三口环盆：
  甲 缫丝中 400 粒
  乙 浸茧   520 粒（与甲差 120，阈值“超过 120”故刚可放过）
  丙 浸茧   600 粒（与甲差 200，改成缫丝中必被挡）
乙、丙在环上都与甲相邻（三环互邻）。

西湾缫丝坞用于按坞筛选，并保留已缫完只看汤温 38～42℃ 的场景。
"""

from datetime import timedelta

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import Basin, BathReading, Filature, User, utcnow
from app.security import hash_password

# (code, status, ring_index, cocoon_count, 最近汤温或 None)
JIANGKOU = [
    ("甲", Basin.STATUS_REELING, 0, 400, 40.5),
    ("乙", Basin.STATUS_SOAKING, 1, 520, None),
    ("丙", Basin.STATUS_SOAKING, 2, 600, None),
]
XIWAN = [
    ("西一", Basin.STATUS_REELING, 0, 380, 40.0),
    ("西二", Basin.STATUS_REELED, 1, 410, 40.8),
    ("西三", Basin.STATUS_SOAKING, 2, 500, 36.5),
]


async def _ensure_users(session) -> None:
    for username, role in (("admin", "admin"), ("worker", "worker")):
        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    username=username,
                    password_hash=hash_password("123456"),
                    role=role,
                )
            )
        else:
            user.password_hash = hash_password("123456")
            user.role = role


async def _reconcile_filature(session, name, riverside, specs) -> None:
    mill = (
        await session.execute(select(Filature).where(Filature.name == name))
    ).scalar_one_or_none()
    if mill is None:
        mill = Filature(name=name, riverside=riverside)
        session.add(mill)
        await session.flush()

    wanted = {code for code, *_ in specs}
    existing = (
        await session.execute(select(Basin).where(Basin.filature_id == mill.id))
    ).scalars().all()

    # 清掉旧版（A03）残留在本坞、不在新规格内的盆
    for basin in existing:
        if basin.code not in wanted:
            await session.execute(
                delete(BathReading).where(BathReading.basin_id == basin.id)
            )
            await session.delete(basin)
    by_code = {b.code: b for b in existing if b.code in wanted}

    now = utcnow()
    for code, status, idx, cocoons, temp in specs:
        basin = by_code.get(code)
        if basin is None:
            basin = Basin(filature_id=mill.id, code=code)
            session.add(basin)
        basin.status = status
        basin.ring_index = idx
        basin.cocoon_count = cocoons
        if temp is not None:
            await session.flush()
            has_reading = (
                await session.execute(
                    select(BathReading.id).where(BathReading.basin_id == basin.id)
                )
            ).first()
            if has_reading is None:
                session.add(
                    BathReading(
                        basin_id=basin.id,
                        water_temp_c=temp,
                        operator="worker",
                        taken_at=now - timedelta(hours=2),
                    )
                )


async def seed_demo() -> None:
    async with SessionLocal() as session:
        await _ensure_users(session)
        await _reconcile_filature(session, "江口缫丝坞", "东津渡", JIANGKOU)
        await _reconcile_filature(session, "西湾缫丝坞", "西湾渡", XIWAN)
        await session.commit()
