"""人群圈选成交贡献明细服务。

口径约定：
- 只统计统计窗口内、至少命中一个圈选组的原始订单；
- 同一订单同时命中两组时按「交叠均分」拆到两组，分位余数按 A→B 顺序补齐，
  两组计入金额相加等于该订单原金额，全窗口只计一次；
- 视图发布时冻结两组圈选名单快照，之后名单刷新不影响旧期视图；
  金额每次读取都从原始订单明细复算，不复用发布时的汇总值。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

GROUP_KEYS = ("A", "B")
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")
DEFAULT_WINDOW = ("2026-09-01 00:00:00", "2026-09-01 23:59:59")
ALLOCATION_POLICY = "交叠均分，分位按 A→B 补齐"

# 原始订单明细：只读的事实表，成交贡献的金额都从这里复算。
SEED_ORDERS: list[dict[str, Any]] = [
    {"order_no": "SO20260901001", "user_id": "U1001", "amount_cents": 4000,
     "paid_at": "2026-09-01 10:00:00", "channel": "小程序"},
    {"order_no": "SO20260901002", "user_id": "U1002", "amount_cents": 2000,
     "paid_at": "2026-09-01 10:30:00", "channel": "App"},
    {"order_no": "SO20260901003", "user_id": "U1003", "amount_cents": 6000,
     "paid_at": "2026-09-01 12:30:00", "channel": "App"},
    {"order_no": "SO20260902004", "user_id": "U1004", "amount_cents": 5000,
     "paid_at": "2026-09-02 09:15:00", "channel": "小程序"},
    {"order_no": "SO20260902005", "user_id": "U1003", "amount_cents": 3000,
     "paid_at": "2026-09-02 10:20:00", "channel": "App"},
]

# 圈选名单当前版本；A 组：U1001 独享、U1003 与 B 组交叠；B 组：U1002 独享。
SEED_MEMBERSHIPS: dict[int, dict[str, Any]] = {
    1: {"version": "2026-09-01#1", "updated_at": "2026-09-01 08:00:00",
        "users": ["U1001", "U1003"]},
    2: {"version": "2026-09-01#1", "updated_at": "2026-09-01 08:05:00",
        "users": ["U1002", "U1003"]},
}

# 次日名单变化：A 组新增 U1004（其 09-02 订单只计入 A），B 组名单不变。
NEXT_DAY_MEMBERSHIPS: dict[int, list[str]] = {
    1: ["U1001", "U1003", "U1004"],
    2: ["U1002", "U1003"],
}
NEXT_DAY_VERSION = "2026-09-02#1"
NEXT_DAY_UPDATED_AT = "2026-09-02 08:00:00"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _yuan(cents: int) -> float:
    return round(cents / 100, 2)


def _parse_time(value: str) -> tuple[datetime, bool]:
    text = str(value or "").strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt), fmt == "%Y-%m-%d"
        except ValueError:
            continue
    raise ValueError(f"时间格式无法识别：{value}，请使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")


def _normalize_window(start: str | None, end: str | None) -> tuple[str, str]:
    """日期只到天时，起始取当天 00:00:00、结束取当天 23:59:59。"""
    start_value = start or DEFAULT_WINDOW[0]
    end_value = end or DEFAULT_WINDOW[1]
    start_dt, _ = _parse_time(start_value)
    end_dt, end_is_date = _parse_time(end_value)
    if end_is_date:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
    if start_dt > end_dt:
        raise ValueError("统计窗口开始时间不能晚于结束时间")
    return start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")


def _allocate(amount_cents: int, groups: list[str]) -> dict[str, int]:
    """把一笔订单金额拆到命中的组，保证各组分位之和等于原金额。"""
    base = amount_cents // len(groups)
    remainder = amount_cents % len(groups)
    return {
        group: base + (1 if index < remainder else 0)
        for index, group in enumerate(groups)
    }


class CohortContributionService:
    """成交贡献视图的发布、复算和按组下钻。"""

    def __init__(self) -> None:
        self.reset()

    # ---- 数据生命周期 -------------------------------------------------
    def reset(self) -> None:
        self._orders = [dict(order) for order in SEED_ORDERS]
        self._memberships = {
            cohort_id: {
                "version": state["version"],
                "updated_at": state["updated_at"],
                "users": list(state["users"]),
            }
            for cohort_id, state in SEED_MEMBERSHIPS.items()
        }
        self._views: dict[int, dict[str, Any]] = {}
        self._next_view_id = 1
        # 预置旧期视图，起服务后可以直接核对样例。
        self._create_view(
            cohort_a_id=1,
            cohort_b_id=2,
            window_start=DEFAULT_WINDOW[0],
            window_end=DEFAULT_WINDOW[1],
            label="2026-09-01 期成交贡献",
            published_at="2026-09-01 23:05:00",
        )

    # ---- 内部组装 -----------------------------------------------------
    def _cohort_name(self, cohort_id: int) -> str:
        cohort = store.find("cohort", cohort_id)
        return str(cohort.get("分群名称")) if cohort else f"分群 {cohort_id}"

    def _membership_state(self, cohort_id: int) -> dict[str, Any]:
        state = self._memberships.get(cohort_id)
        if state is None:
            raise ValueError(f"分群 {cohort_id} 尚未生成成交贡献圈选名单")
        return state

    def _snapshot(self, cohort_id: int) -> dict[str, Any]:
        state = self._membership_state(cohort_id)
        return {
            "cohort_id": cohort_id,
            "cohort_name": self._cohort_name(cohort_id),
            "membership_version": state["version"],
            "member_ids": sorted(set(state["users"])),
        }

    def _create_view(
        self,
        *,
        cohort_a_id: int,
        cohort_b_id: int,
        window_start: str,
        window_end: str,
        label: str | None,
        published_at: str,
    ) -> dict[str, Any]:
        view_id = self._next_view_id
        self._next_view_id += 1
        view = {
            "view_id": view_id,
            "label": label or f"{window_start[:10]} 期成交贡献",
            "period_start": window_start,
            "period_end": window_end,
            "published_at": published_at,
            "snapshots": {
                "A": self._snapshot(cohort_a_id),
                "B": self._snapshot(cohort_b_id),
            },
        }
        self._views[view_id] = view
        return view

    def _get_view(self, view_id: int) -> dict[str, Any]:
        view = self._views.get(view_id)
        if view is None:
            raise ValueError(f"成交贡献视图 {view_id} 不存在")
        return view

    def _compose(self, view: dict[str, Any]) -> dict[str, Any]:
        """从原始订单明细复算某次发布快照下的全部计入结果（单位：分）。"""
        snapshots = view["snapshots"]
        start, end = view["period_start"], view["period_end"]
        lines: list[dict[str, Any]] = []
        for order in self._orders:
            paid_at = str(order.get("paid_at", ""))
            if not (start <= paid_at <= end):
                continue
            matched = [
                group for group in GROUP_KEYS
                if order["user_id"] in snapshots[group]["member_ids"]
            ]
            if not matched:
                continue
            allocations = _allocate(int(order["amount_cents"]), matched)
            lines.append({
                **order,
                "matched_groups": matched,
                "allocations": allocations,
                "allocation_method": "本组独占" if len(matched) == 1 else "交叠均分",
            })

        groups: dict[str, dict[str, Any]] = {}
        for group in GROUP_KEYS:
            own = [line for line in lines if group in line["matched_groups"]]
            groups[group] = {
                "group_key": group,
                "cohort_id": snapshots[group]["cohort_id"],
                "cohort_name": snapshots[group]["cohort_name"],
                "membership_version": snapshots[group]["membership_version"],
                "snapshot_member_ids": snapshots[group]["member_ids"],
                "member_count": len(snapshots[group]["member_ids"]),
                "amount_cents": sum(line["allocations"][group] for line in own),
                "original_cents": sum(int(line["amount_cents"]) for line in own),
                "exclusive_cents": sum(
                    int(line["amount_cents"]) for line in own
                    if len(line["matched_groups"]) == 1
                ),
                "shared_cents": sum(
                    line["allocations"][group] for line in own
                    if len(line["matched_groups"]) > 1
                ),
                "order_count": len(own),
                "user_ids": sorted({str(line["user_id"]) for line in own}),
            }

        distinct_cents = sum(int(line["amount_cents"]) for line in lines)
        group_sum_cents = sum(group["amount_cents"] for group in groups.values())
        raw_sum_cents = sum(group["original_cents"] for group in groups.values())
        for line in lines:
            line["counted_once_cents"] = int(line["amount_cents"])
        return {
            "lines": lines,
            "groups": groups,
            "distinct_cents": distinct_cents,
            "group_sum_cents": group_sum_cents,
            "raw_sum_cents": raw_sum_cents,
        }

    @staticmethod
    def _public_line(line: dict[str, Any]) -> dict[str, Any]:
        return {
            "order_no": line["order_no"],
            "user_id": line["user_id"],
            "paid_at": line["paid_at"],
            "channel": line.get("channel", ""),
            "original_amount": _yuan(int(line["amount_cents"])),
            "matched_groups": line["matched_groups"],
            "allocation_method": line["allocation_method"],
            "allocations": {
                group: _yuan(cents) for group, cents in line["allocations"].items()
            },
            "counted_once_amount": _yuan(line["counted_once_cents"]),
        }

    def _group_payload(self, view: dict[str, Any], composed: dict[str, Any],
                       group_key: str) -> dict[str, Any]:
        group = composed["groups"][group_key]
        snapshot = view["snapshots"][group_key]
        current = self._memberships.get(group["cohort_id"], {"users": []})
        snapshot_users = set(snapshot["member_ids"])
        current_users = set(current.get("users", []))
        return {
            "group_key": group_key,
            "cohort_id": group["cohort_id"],
            "cohort_name": group["cohort_name"],
            "amount": _yuan(group["amount_cents"]),
            "original_order_amount": _yuan(group["original_cents"]),
            "exclusive_amount": _yuan(group["exclusive_cents"]),
            "shared_amount": _yuan(group["shared_cents"]),
            "order_count": group["order_count"],
            "user_count": len(group["user_ids"]),
            "user_ids": group["user_ids"],
            "membership_version": group["membership_version"],
            "membership_source": "发布快照",
            "snapshot_member_count": group["member_count"],
            "current_member_count": len(current_users),
            "added_since_publish": sorted(current_users - snapshot_users),
            "removed_since_publish": sorted(snapshot_users - current_users),
            "member_ids": snapshot["member_ids"],
        }

    def _view_meta(self, view: dict[str, Any]) -> dict[str, Any]:
        return {
            "view_id": view["view_id"],
            "label": view["label"],
            "period_start": view["period_start"],
            "period_end": view["period_end"],
            "published_at": view["published_at"],
            "status": "已发布",
            "group_a_cohort_id": view["snapshots"]["A"]["cohort_id"],
            "group_b_cohort_id": view["snapshots"]["B"]["cohort_id"],
        }

    def _summary(self, composed: dict[str, Any], recomputed_at: str) -> dict[str, Any]:
        distinct = composed["distinct_cents"]
        group_sum = composed["group_sum_cents"]
        raw_sum = composed["raw_sum_cents"]
        return {
            "currency": "CNY",
            "allocation_policy": ALLOCATION_POLICY,
            "group_amounts": {
                group: _yuan(composed["groups"][group]["amount_cents"])
                for group in GROUP_KEYS
            },
            "group_sum_amount": _yuan(group_sum),
            "raw_group_amounts": {
                group: _yuan(composed["groups"][group]["original_cents"])
                for group in GROUP_KEYS
            },
            "raw_group_sum_amount": _yuan(raw_sum),
            "dedup_adjustment_amount": _yuan(raw_sum - distinct),
            "distinct_order_count": len(composed["lines"]),
            "distinct_order_amount": _yuan(distinct),
            "overlap_order_count": sum(
                1 for line in composed["lines"] if len(line["matched_groups"]) > 1
            ),
            "reconciled": group_sum == distinct,
            "difference_amount": _yuan(group_sum - distinct),
            "recomputed_at": recomputed_at,
        }

    def _detail_payload(self, view: dict[str, Any], *, published: bool,
                        recomputed_at: str) -> dict[str, Any]:
        composed = self._compose(view)
        lines = composed["lines"]
        return {
            "published": published,
            "view": self._view_meta(view),
            "summary": self._summary(composed, recomputed_at),
            "groups": [
                self._group_payload(view, composed, group) for group in GROUP_KEYS
            ],
            "overlap_orders": [
                self._public_line(line) for line in lines
                if len(line["matched_groups"]) > 1
            ],
            "order_details": [self._public_line(line) for line in lines],
            "compute_basis": {
                "orders": "原始订单明细复算",
                "membership": "发布快照" if published else "当前名单",
                "recomputed_at": recomputed_at,
            },
        }

    # ---- 对外能力 -----------------------------------------------------
    def catalog(self) -> dict[str, Any]:
        cohorts = []
        for row in store.rows("cohort"):
            cohort_id = int(row["id"])
            state = self._memberships.get(cohort_id)
            cohorts.append({
                "cohort_id": cohort_id,
                "cohort_name": row.get("分群名称"),
                "status": row.get("status"),
                "base_date": row.get("基准日期"),
                "contribution_ready": state is not None,
                "membership_version": state["version"] if state else None,
                "updated_at": state["updated_at"] if state else None,
                "member_count": len(state["users"]) if state else 0,
            })
        return {
            "cohorts": cohorts,
            "group_keys": list(GROUP_KEYS),
            "default_window": {"start": DEFAULT_WINDOW[0], "end": DEFAULT_WINDOW[1]},
            "allocation_policy": ALLOCATION_POLICY,
            "order_total": len(self._orders),
            "view_count": len(self._views),
        }

    def publish_view(
        self,
        *,
        cohort_a_id: int,
        cohort_b_id: int,
        window_start: str | None = None,
        window_end: str | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        if cohort_a_id == cohort_b_id:
            raise ValueError("两组圈选名单不能相同")
        start, end = _normalize_window(window_start, window_end)
        view = self._create_view(
            cohort_a_id=cohort_a_id,
            cohort_b_id=cohort_b_id,
            window_start=start,
            window_end=end,
            label=label,
            published_at=_now(),
        )
        return self._detail_payload(view, published=True, recomputed_at=_now())

    def preview(
        self,
        *,
        cohort_a_id: int,
        cohort_b_id: int,
        window_start: str | None = None,
        window_end: str | None = None,
    ) -> dict[str, Any]:
        """不发布，仅按当前名单预览窗口内的成交贡献。"""
        if cohort_a_id == cohort_b_id:
            raise ValueError("两组圈选名单不能相同")
        start, end = _normalize_window(window_start, window_end)
        view = {
            "view_id": None,
            "label": f"{start[:10]} 期预览",
            "period_start": start,
            "period_end": end,
            "published_at": None,
            "snapshots": {
                "A": self._snapshot(cohort_a_id),
                "B": self._snapshot(cohort_b_id),
            },
        }
        return self._detail_payload(view, published=False, recomputed_at=_now())

    def list_views(self) -> list[dict[str, Any]]:
        result = []
        for view_id in sorted(self._views, reverse=True):
            view = self._views[view_id]
            composed = self._compose(view)
            summary = self._summary(composed, _now())
            result.append({
                **self._view_meta(view),
                "group_amounts": summary["group_amounts"],
                "group_sum_amount": summary["group_sum_amount"],
                "distinct_order_amount": summary["distinct_order_amount"],
                "reconciled": summary["reconciled"],
            })
        return result

    def view_detail(self, view_id: int) -> dict[str, Any]:
        view = self._get_view(view_id)
        return self._detail_payload(view, published=True, recomputed_at=_now())

    def view_by_id(self, view_id: int) -> dict[str, Any] | None:
        """返回内部视图（含发布快照），供跨模块链路读取。"""
        return self._views.get(view_id)

    def latest_view(self, cohort_id: int) -> dict[str, Any] | None:
        for view_id in sorted(self._views, reverse=True):
            view = self._views[view_id]
            if cohort_id in (
                view["snapshots"]["A"]["cohort_id"],
                view["snapshots"]["B"]["cohort_id"],
            ):
                return view
        return None

    def group_drill(self, view_id: int, group_key: str) -> dict[str, Any]:
        key = str(group_key or "").upper()
        if key not in GROUP_KEYS:
            raise ValueError(f"圈选组 {group_key} 不存在，仅支持 A/B")
        view = self._get_view(view_id)
        composed = self._compose(view)
        group = composed["groups"][key]
        lines = [
            line for line in composed["lines"] if key in line["matched_groups"]
        ]
        users: dict[str, dict[str, Any]] = {}
        for line in lines:
            user = users.setdefault(str(line["user_id"]), {
                "user_id": str(line["user_id"]),
                "order_count": 0,
                "original_cents": 0,
                "counted_cents": 0,
                "other_group_cents": {},
                "counted_once_cents": 0,
            })
            user["order_count"] += 1
            user["original_cents"] += int(line["amount_cents"])
            user["counted_cents"] += line["allocations"][key]
            user["counted_once_cents"] += int(line["counted_once_cents"])
            for other, cents in line["allocations"].items():
                if other != key:
                    user["other_group_cents"][other] = (
                        user["other_group_cents"].get(other, 0) + cents
                    )

        group_payload = self._group_payload(view, composed, key)
        detail = self._detail_payload(view, published=True, recomputed_at=_now())
        return {
            "view_id": view_id,
            "group_key": key,
            "cohort_id": group["cohort_id"],
            "cohort_name": group["cohort_name"],
            "membership_version": group["membership_version"],
            "period_start": view["period_start"],
            "period_end": view["period_end"],
            "recomputed": True,
            "amount_source": "原始订单明细复算",
            "recomputed_at": detail["compute_basis"]["recomputed_at"],
            "summary": {
                "group_amount": group_payload["amount"],
                "original_order_amount": group_payload["original_order_amount"],
                "exclusive_amount": group_payload["exclusive_amount"],
                "shared_amount": group_payload["shared_amount"],
                "order_count": group_payload["order_count"],
                "user_count": group_payload["user_count"],
            },
            "reconciliation": {
                "group_amounts": detail["summary"]["group_amounts"],
                "group_sum_amount": detail["summary"]["group_sum_amount"],
                "distinct_order_amount": detail["summary"]["distinct_order_amount"],
                "reconciled": detail["summary"]["reconciled"],
            },
            "orders": [self._public_line(line) for line in lines],
            "users": [
                {
                    "user_id": user["user_id"],
                    "order_count": user["order_count"],
                    "original_amount": _yuan(user["original_cents"]),
                    "counted_amount": _yuan(user["counted_cents"]),
                    "other_group_amounts": {
                        other: _yuan(cents)
                        for other, cents in user["other_group_cents"].items()
                    },
                    "counted_once_amount": _yuan(user["counted_once_cents"]),
                    "in_both_groups": bool(user["other_group_cents"]),
                }
                for user in sorted(users.values(), key=lambda item: item["user_id"])
            ],
        }

    def refresh_membership(
        self,
        cohort_id: int,
        *,
        add_users: list[str] | None = None,
        remove_users: list[str] | None = None,
    ) -> dict[str, Any]:
        """刷新圈选名单；不传增删用户时按预置的次日名单变化模拟。"""
        state = self._membership_state(cohort_id)
        before = list(state["users"])
        if add_users is None and remove_users is None:
            next_day = NEXT_DAY_MEMBERSHIPS.get(cohort_id)
            if next_day is None:
                raise ValueError(f"分群 {cohort_id} 没有预置的次日名单")
            users = list(next_day)
            state["version"] = NEXT_DAY_VERSION
            state["updated_at"] = NEXT_DAY_UPDATED_AT
        else:
            removed = set(remove_users or [])
            users = [user for user in before if user not in removed]
            for user in add_users or []:
                if user not in users:
                    users.append(user)
            state["version"] = self._bump_version(state["version"])
            state["updated_at"] = _now()
        state["users"] = users
        after = set(users)
        return {
            "cohort_id": cohort_id,
            "cohort_name": self._cohort_name(cohort_id),
            "membership_version": state["version"],
            "updated_at": state["updated_at"],
            "member_count": len(users),
            "member_ids": sorted(after),
            "added_users": sorted(after - set(before)),
            "removed_users": sorted(set(before) - after),
        }

    @staticmethod
    def _bump_version(version: str) -> str:
        base, _, suffix = str(version).partition("#")
        try:
            sequence = int(suffix or 0) + 1
        except ValueError:
            sequence = 1
        return f"{base}#{sequence}"


contribution_service = CohortContributionService()
