"""人群圈选成交贡献接口：发布视图、贡献看板、按组下钻、名单刷新。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas import ContributionViewPayload, MembershipRefreshPayload
from app.services.cohort_contribution import contribution_service

router = APIRouter(prefix="/api/cohort-contribution", tags=["成交贡献"])


def _fail(error: ValueError) -> HTTPException:
    return HTTPException(400, str(error))


@router.get("/catalog")
def catalog() -> dict[str, Any]:
    """可参与成交贡献的圈选名单和默认统计窗口。"""
    return contribution_service.catalog()


@router.get("/views")
def list_views() -> dict[str, Any]:
    """已发布的成交贡献视图列表。"""
    items = contribution_service.list_views()
    return {"items": items, "total": len(items)}


@router.post("/views")
def publish_view(payload: ContributionViewPayload) -> dict[str, Any]:
    """发布某期成交贡献视图，冻结两组圈选名单快照。"""
    try:
        return contribution_service.publish_view(
            cohort_a_id=payload.cohort_a_id,
            cohort_b_id=payload.cohort_b_id,
            window_start=payload.window_start,
            window_end=payload.window_end,
            label=payload.label,
        )
    except ValueError as error:
        raise _fail(error)


@router.get("/preview")
def preview(
    cohort_a_id: int,
    cohort_b_id: int,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, Any]:
    """按当前名单预览统计窗口内的成交贡献，不落发布快照。"""
    try:
        return contribution_service.preview(
            cohort_a_id=cohort_a_id,
            cohort_b_id=cohort_b_id,
            window_start=window_start,
            window_end=window_end,
        )
    except ValueError as error:
        raise _fail(error)


@router.get("/views/{view_id}")
def view_detail(view_id: int) -> dict[str, Any]:
    """贡献看板：两组各自计入金额、交叠订单计入方式和复算对平结果。"""
    try:
        return contribution_service.view_detail(view_id)
    except ValueError as error:
        raise HTTPException(404, str(error))


@router.get("/views/{view_id}/groups/{group_key}")
def group_drill(view_id: int, group_key: str) -> dict[str, Any]:
    """按组下钻：从原始订单明细复算该组实际计入的订单和用户金额。"""
    try:
        return contribution_service.group_drill(view_id, group_key)
    except ValueError as error:
        message = str(error)
        raise HTTPException(404 if "视图" in message else 400, message)


@router.post("/cohorts/{cohort_id}/membership/refresh")
def refresh_membership(
    cohort_id: int,
    payload: MembershipRefreshPayload | None = None,
) -> dict[str, Any]:
    """刷新圈选名单，已发布视图仍按发布时的快照复算。"""
    body = payload or MembershipRefreshPayload()
    try:
        return contribution_service.refresh_membership(
            cohort_id,
            add_users=body.add_users,
            remove_users=body.remove_users,
        )
    except ValueError as error:
        raise _fail(error)
