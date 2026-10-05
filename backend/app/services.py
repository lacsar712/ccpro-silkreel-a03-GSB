"""缫丝盆门槛：已缫完须最近一次汤温 38～42℃；浸茧改缫丝中须过邻盆茧粒差。"""

from app.models import Basin

MIN_TEMP = 38.0
MAX_TEMP = 42.0
MAX_GRAIN_GAP = 120

STATUS_LABELS = {
    Basin.STATUS_SOAKING: "浸茧",
    Basin.STATUS_REELING: "缫丝中",
    Basin.STATUS_REELED: "已缫完",
}


class RuleError(ValueError):
    pass


def latest_temp(basin: Basin) -> float | None:
    if not basin.readings:
        return None
    latest = max(basin.readings, key=lambda r: r.taken_at)
    return latest.water_temp_c


def widest_reeling_gap(basin: Basin, siblings: list[Basin]) -> tuple[Basin, int] | None:
    """同坞缫丝中盆里茧粒差最大的那口及其差值；没有缫丝中邻盆则 None。"""
    pool = [
        b
        for b in siblings
        if b.id != basin.id and b.status == Basin.STATUS_REELING
    ]
    if not pool:
        return None
    other = min(
        pool,
        key=lambda b: (-abs(b.cocoon_grains - basin.cocoon_grains), b.id),
    )
    return other, abs(other.cocoon_grains - basin.cocoon_grains)


def assert_can_set_status(
    basin: Basin, new_status: str, siblings: list[Basin] | None = None
) -> None:
    allowed = {Basin.STATUS_SOAKING, Basin.STATUS_REELING, Basin.STATUS_REELED}
    if new_status not in allowed:
        raise RuleError(f"无效状态：{new_status}")
    if new_status == basin.status:
        raise RuleError(f"该盆已是「{STATUS_LABELS[basin.status]}」，无需重复改动")
    if new_status == Basin.STATUS_REELED:
        # 已缫完只认最近汤温，茧粒差不参与
        temp = latest_temp(basin)
        if temp is None:
            raise RuleError("该盆尚无汤温记录，不能标已缫完")
        if temp < MIN_TEMP or temp > MAX_TEMP:
            raise RuleError(
                f"最近汤温 {temp}℃ 不在 {MIN_TEMP:.0f}～{MAX_TEMP:.0f}℃，不能标已缫完"
            )
        return
    if new_status == Basin.STATUS_REELING and basin.status == Basin.STATUS_SOAKING:
        # 浸茧改缫丝中：与坞内缫丝中盆比茧粒；没有缫丝中邻盆则不比
        hit = widest_reeling_gap(basin, siblings or [])
        if hit is None:
            return
        other, gap = hit
        if gap > MAX_GRAIN_GAP:
            raise RuleError(
                f"与缫丝中邻盆「{other.code}」茧粒差 {gap} 粒，"
                f"超过 {MAX_GRAIN_GAP} 粒上限，不能改成缫丝中"
            )
