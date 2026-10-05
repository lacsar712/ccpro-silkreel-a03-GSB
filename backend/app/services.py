"""缫丝盆门槛。

- 标成已缫完：只认最近一次汤温落在 38～42℃（茧粒差不参与）。
- 浸茧改成缫丝中：环上相邻盆若有正在缫丝中的，茧粒数与之相差不得
  超过 120 粒（严格大于 120 才挡，差恰好 120 放行）；没有缫丝中邻盆
  则不比较。
"""

from app.models import Basin

MIN_TEMP = 38.0
MAX_TEMP = 42.0
MAX_COCOON_DIFF = 120


class RuleError(ValueError):
    """业务门槛未过（400）。"""


class ConflictError(RuntimeError):
    """状态已被他人改动，本次转换不再成立（409）。"""


def latest_temp(basin: Basin) -> float | None:
    if not basin.readings:
        return None
    latest = max(basin.readings, key=lambda r: r.taken_at)
    return latest.water_temp_c


def ring_neighbors(basin: Basin, peers: list[Basin]) -> list[Basin]:
    """同坞环上 ring_index 恰差一位（首尾相接）的盆。"""
    same_yard = [b for b in peers if b.filature_id == basin.filature_id]
    size = max((b.ring_index for b in same_yard), default=-1) + 1
    if size < 2:
        return []
    prev_idx = (basin.ring_index - 1) % size
    next_idx = (basin.ring_index + 1) % size
    return [
        b
        for b in same_yard
        if b.id != basin.id and b.ring_index in (prev_idx, next_idx)
    ]


def assert_can_set_status(basin: Basin, new_status: str, peers: list[Basin]) -> None:
    allowed = {Basin.STATUS_SOAKING, Basin.STATUS_REELING, Basin.STATUS_REELED}
    if new_status not in allowed:
        raise RuleError(f"无效状态：{new_status}")
    if basin.status == new_status:
        raise ConflictError(f"该盆当前已是{_STATUS_LABEL[new_status]}，状态未变")

    if new_status == Basin.STATUS_REELED:
        # 已缫完只看汤温，茧粒差不得在此拦路。
        temp = latest_temp(basin)
        if temp is None:
            raise RuleError("该盆尚无汤温记录，不能标已缫完")
        if temp < MIN_TEMP or temp > MAX_TEMP:
            raise RuleError(
                f"最近汤温 {temp}℃ 不在 {MIN_TEMP:.0f}～{MAX_TEMP:.0f}℃，不能标已缫完"
            )
        return

    if basin.status == Basin.STATUS_SOAKING and new_status == Basin.STATUS_REELING:
        reeling_next = [
            b for b in ring_neighbors(basin, peers) if b.status == Basin.STATUS_REELING
        ]
        if not reeling_next:
            return
        for other in reeling_next:
            diff = abs(basin.cocoon_count - other.cocoon_count)
            if diff > MAX_COCOON_DIFF:
                raise RuleError(
                    f"邻盆{other.code}正在缫丝中（{other.cocoon_count} 粒），"
                    f"本盆 {basin.cocoon_count} 粒，相差 {diff} 粒"
                    f"（超过 {MAX_COCOON_DIFF} 粒），不能改成缫丝中"
                )


def nearest_reeling(basin: Basin, peers: list[Basin]) -> Basin | None:
    """同坞环上离本盆最近的缫丝中盆；本盆自己在缫丝中时返回自身。"""
    same_yard = [b for b in peers if b.filature_id == basin.filature_id]
    reeling = [b for b in same_yard if b.status == Basin.STATUS_REELING]
    if not reeling:
        return None
    size = max((b.ring_index for b in same_yard), default=0) + 1

    def distance(other: Basin) -> int:
        raw = abs(other.ring_index - basin.ring_index)
        return min(raw, size - raw)

    return min(reeling, key=lambda b: (distance(b), b.ring_index, b.id))


_STATUS_LABEL = {
    Basin.STATUS_SOAKING: "浸茧",
    Basin.STATUS_REELING: "缫丝中",
    Basin.STATUS_REELED: "已缫完",
}
