from quart import Quart, g, jsonify, request
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Basin
from app.repositories import BasinRepo, UserRepo
from app.security import make_token, parse_token, verify_password
from app.services import (
    ConflictError,
    RuleError,
    assert_can_set_status,
    latest_temp,
    nearest_reeling,
)

app = Quart(__name__)


def _bearer() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return None


@app.before_request
async def load_user():
    g.user = None
    token = _bearer()
    if not token:
        return
    username = parse_token(token)
    if not username:
        return
    async with SessionLocal() as session:
        g.user = await UserRepo(session).by_username(username)


def require_user():
    if g.user is None:
        return jsonify({"detail": "未登录"}), 401
    return None


@app.route("/api/health")
async def health():
    return {"status": "ok", "service": "SilkReel"}


@app.route("/api/auth/login", methods=["POST"])
async def login():
    body = await request.get_json(force=True)
    username = (body or {}).get("username", "")
    password = (body or {}).get("password", "")
    async with SessionLocal() as session:
        user = await UserRepo(session).by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            return jsonify({"detail": "用户名或密码错误"}), 401
        return {
            "access_token": make_token(user.username),
            "user": {"username": user.username, "role": user.role},
        }


@app.route("/api/auth/me")
async def me():
    denied = require_user()
    if denied:
        return denied
    return {"username": g.user.username, "role": g.user.role}


def _basin_json(basin: Basin) -> dict:
    return {
        "id": basin.id,
        "code": basin.code,
        "status": basin.status,
        "ringIndex": basin.ring_index,
        "cocoonCount": basin.cocoon_count,
        "latestTempC": latest_temp(basin),
        "readingCount": len(basin.readings or []),
    }


def _yard_json(mill, basins) -> dict:
    return {
        "id": mill.id,
        "name": mill.name,
        "riverside": mill.riverside,
        "basins": [_basin_json(b) for b in sorted(basins, key=lambda b: b.ring_index)],
    }


@app.route("/api/board")
async def board():
    denied = require_user()
    if denied:
        return denied
    async with SessionLocal() as session:
        yards = await BasinRepo(session).all_yards()
        if not yards:
            return jsonify({"detail": "尚无缫丝坞"}), 404
        return {"yards": [_yard_json(mill, mill.basins) for mill in yards]}


@app.route("/api/basins/<int:basin_id>/readings", methods=["POST"])
async def add_reading(basin_id: int):
    denied = require_user()
    if denied:
        return denied
    body = await request.get_json(force=True)
    try:
        temp = float((body or {}).get("waterTempC"))
    except (TypeError, ValueError):
        return jsonify({"detail": "汤温必须是数字"}), 400
    async with SessionLocal() as session:
        repo = BasinRepo(session)
        basin = await repo.get(basin_id)
        if basin is None:
            return jsonify({"detail": "盆不存在"}), 404
        await repo.add_reading(basin, temp, g.user.username)
        basin = await repo.get(basin_id)
        return _basin_json(basin)


@app.route("/api/basins/<int:basin_id>/status", methods=["POST"])
async def set_status(basin_id: int):
    denied = require_user()
    if denied:
        return denied
    body = await request.get_json(force=True)
    status = (body or {}).get("status", "")
    async with SessionLocal() as session:
        repo = BasinRepo(session)

        class _NotFound(Exception):
            pass

        try:
            async with session.begin():
                # 事务内先取坞号，再锁坞、锁内重读，保证校验基于最新快照
                fid_row = (
                    await session.execute(
                        select(Basin.filature_id).where(Basin.id == basin_id)
                    )
                ).first()
                if fid_row is None:
                    raise _NotFound
                filature_id = fid_row[0]
                await repo.lock_yard(filature_id)
                basin = await repo.get(basin_id)
                peers = await repo.yard_peers(filature_id)
                assert_can_set_status(basin, status, peers)
                basin.status = status
        except _NotFound:
            return jsonify({"detail": "盆不存在"}), 404
        except RuleError as exc:
            return jsonify({"detail": str(exc)}), 400
        except ConflictError as exc:
            return jsonify({"detail": str(exc)}), 409
        return _basin_json(basin)


@app.route("/api/cocoon-board")
async def cocoon_board():
    """茧粒台（只读）：各坞各盆茧粒数与最近缫丝中盆的差。"""
    denied = require_user()
    if denied:
        return denied
    try:
        filature_id = int(request.args.get("filature_id")) if request.args.get("filature_id") else None
    except ValueError:
        return jsonify({"detail": "filature_id 必须是整数"}), 400
    async with SessionLocal() as session:
        yards = await BasinRepo(session).all_yards()
        result = []
        for mill in yards:
            if filature_id is not None and mill.id != filature_id:
                continue
            basins = sorted(mill.basins, key=lambda b: b.ring_index)
            entries = []
            for basin in basins:
                ref = nearest_reeling(basin, basins)
                if ref is None or ref.id == basin.id:
                    diff = None
                    ref_code = None
                else:
                    diff = abs(basin.cocoon_count - ref.cocoon_count)
                    ref_code = ref.code
                entries.append(
                    {
                        "id": basin.id,
                        "code": basin.code,
                        "status": basin.status,
                        "ringIndex": basin.ring_index,
                        "cocoonCount": basin.cocoon_count,
                        "nearestReelingCode": ref_code,
                        "diffToNearestReeling": diff,
                    }
                )
            result.append(
                {
                    "id": mill.id,
                    "name": mill.name,
                    "riverside": mill.riverside,
                    "basins": entries,
                }
            )
        return {"yards": result}
