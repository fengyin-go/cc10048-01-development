"""成交贡献明细视图测试：交叠订单只计一次、按组下钻、名单快照与复算。"""
import pytest

from app.services.cohort_contribution import CohortContributionService
from app.routers.chains import chain_cohort_analysis


@pytest.fixture()
def service() -> CohortContributionService:
    return CohortContributionService()


class TestSampleReconciliation:
    """A 独享 40 + B 独享 20 + 共享 60，两组合计 120，与去重订单对平。"""

    def test_group_amounts(self, service):
        detail = service.view_detail(1)
        assert detail["summary"]["group_amounts"] == {"A": 70.0, "B": 50.0}
        assert detail["summary"]["raw_group_amounts"] == {"A": 100.0, "B": 80.0}

    def test_sum_matches_distinct_orders(self, service):
        summary = service.view_detail(1)["summary"]
        assert summary["group_sum_amount"] == 120.0
        assert summary["distinct_order_amount"] == 120.0
        assert summary["distinct_order_count"] == 3
        assert summary["dedup_adjustment_amount"] == 60.0
        assert summary["reconciled"] is True
        assert summary["difference_amount"] == 0.0

    def test_overlap_order_allocation(self, service):
        overlap = service.view_detail(1)["overlap_orders"]
        assert len(overlap) == 1
        order = overlap[0]
        assert order["order_no"] == "SO20260901003"
        assert order["original_amount"] == 60.0
        assert order["matched_groups"] == ["A", "B"]
        assert order["allocations"] == {"A": 30.0, "B": 30.0}
        assert order["allocation_method"] == "交叠均分"
        assert order["counted_once_amount"] == 60.0


class TestGroupDrill:
    def test_group_a_amount_and_orders(self, service):
        drill = service.group_drill(1, "A")
        assert drill["summary"]["group_amount"] == 70.0
        assert drill["summary"]["original_order_amount"] == 100.0
        assert {order["order_no"] for order in drill["orders"]} == {
            "SO20260901001", "SO20260901003"}
        amounts = {order["order_no"]: order["allocations"]["A"] for order in drill["orders"]}
        assert amounts == {"SO20260901001": 40.0, "SO20260901003": 30.0}

    def test_overlap_user_counted_amount(self, service):
        users = {user["user_id"]: user for user in service.group_drill(1, "A")["users"]}
        shared_user = users["U1003"]
        assert shared_user["in_both_groups"] is True
        assert shared_user["original_amount"] == 60.0
        assert shared_user["counted_amount"] == 30.0
        assert shared_user["other_group_amounts"] == {"B": 30.0}
        assert shared_user["counted_once_amount"] == 60.0

    def test_group_b_amount(self, service):
        drill = service.group_drill(1, "B")
        assert drill["summary"]["group_amount"] == 50.0
        assert drill["reconciliation"]["group_sum_amount"] == 120.0
        assert drill["reconciliation"]["reconciled"] is True

    def test_unknown_group(self, service):
        with pytest.raises(ValueError):
            service.group_drill(1, "C")


class TestMembershipSnapshot:
    def test_next_day_refresh_keeps_published_scope(self, service):
        before = service.view_detail(1)
        refreshed = service.refresh_membership(1)
        assert refreshed["membership_version"] == "2026-09-02#1"
        assert refreshed["added_users"] == ["U1004"]

        after = service.view_detail(1)
        assert after["summary"] == {
            **before["summary"], "recomputed_at": after["summary"]["recomputed_at"]}
        group_a = after["groups"][0]
        assert group_a["member_ids"] == ["U1001", "U1003"]
        assert group_a["membership_version"] == "2026-09-01#1"
        assert group_a["added_since_publish"] == ["U1004"]
        assert group_a["current_member_count"] == 3

    def test_old_view_still_recomputes_from_original_orders(self, service):
        service.refresh_membership(1)
        service.refresh_membership(2)
        # 篡改发布快照里没有的订单也不影响既有视图的金额口径；
        # 这里直接改动原始订单金额，验证读取时是实时复算而不是缓存汇总。
        service.view_detail(1)
        service._orders[0]["amount_cents"] = 8000
        recomputed = service.view_detail(1)
        assert recomputed["summary"]["group_amounts"]["A"] == 110.0
        assert recomputed["summary"]["distinct_order_amount"] == 160.0
        assert recomputed["summary"]["reconciled"] is True

    def test_new_view_uses_refreshed_scope(self, service):
        service.refresh_membership(1)
        detail = service.publish_view(
            cohort_a_id=1,
            cohort_b_id=2,
            window_start="2026-09-01",
            window_end="2026-09-02",
        )
        group_a = detail["groups"][0]
        assert "U1004" in group_a["member_ids"]
        assert detail["summary"]["distinct_order_count"] == 5
        assert detail["summary"]["group_sum_amount"] == 200.0
        assert detail["summary"]["distinct_order_amount"] == 200.0
        assert detail["summary"]["reconciled"] is True


class TestWindow:
    def test_date_range_expands_to_day_boundaries(self, service):
        detail = service.publish_view(
            cohort_a_id=1, cohort_b_id=2,
            window_start="2026-09-01", window_end="2026-09-02",
        )
        assert detail["view"]["period_start"] == "2026-09-01 00:00:00"
        assert detail["view"]["period_end"] == "2026-09-02 23:59:59"

    def test_empty_window(self, service):
        detail = service.publish_view(
            cohort_a_id=1, cohort_b_id=2,
            window_start="2026-08-01", window_end="2026-08-31",
        )
        assert detail["summary"]["group_sum_amount"] == 0.0
        assert detail["summary"]["reconciled"] is True

    def test_invalid_window(self, service):
        with pytest.raises(ValueError):
            service.publish_view(
                cohort_a_id=1, cohort_b_id=2,
                window_start="2026-09-03", window_end="2026-09-01",
            )

    def test_same_cohort_rejected(self, service):
        with pytest.raises(ValueError):
            service.publish_view(cohort_a_id=1, cohort_b_id=1)


class TestChainReadsContribution:
    def test_user_analysis_reads_view_orders(self, service, monkeypatch):
        from app.routers import chains as chains_module
        monkeypatch.setattr(chains_module, "contribution_service", service)
        result = chain_cohort_analysis(1)
        audit = result["contribution_orders"]
        assert audit["available"] is True
        assert audit["view"]["view_id"] == 1
        assert [group["group_key"] for group in audit["groups"]] == ["A", "B"]
        pairs = {(order["group_key"], order["order_no"]) for order in audit["orders"]}
        assert ("A", "SO20260901003") in pairs
        assert ("B", "SO20260901003") in pairs
        shared = [
            order for order in audit["orders"]
            if order["order_no"] == "SO20260901003"
        ]
        assert {order["group_key"]: order["group_amount"] for order in shared} == {
            "A": 30.0, "B": 30.0}
        for order in shared:
            assert order["original_amount"] == 60.0


class TestContributionRouter:
    """直接调用路由函数，覆盖发布参数校验和错误映射。"""

    def test_publish_and_drill(self):
        from app.routers import cohort_contribution as route
        from app.schemas import ContributionViewPayload
        published = route.publish_view(ContributionViewPayload(
            cohort_a_id=1, cohort_b_id=2,
            window_start="2026-09-01", window_end="2026-09-01",
        ))
        view_id = published["view"]["view_id"]
        drill = route.group_drill(view_id, "b")
        assert drill["group_key"] == "B"
        assert drill["summary"]["group_amount"] == 50.0

    def test_invalid_group_returns_400(self):
        from fastapi import HTTPException
        from app.routers import cohort_contribution as route
        with pytest.raises(HTTPException) as excinfo:
            route.group_drill(1, "C")
        assert excinfo.value.status_code == 400

    def test_missing_view_returns_404(self):
        from fastapi import HTTPException
        from app.routers import cohort_contribution as route
        with pytest.raises(HTTPException) as excinfo:
            route.view_detail(99999)
        assert excinfo.value.status_code == 404

    def test_publish_same_cohort_returns_400(self):
        from fastapi import HTTPException
        from app.routers import cohort_contribution as route
        from app.schemas import ContributionViewPayload
        with pytest.raises(HTTPException) as excinfo:
            route.publish_view(ContributionViewPayload(cohort_a_id=2, cohort_b_id=2))
        assert excinfo.value.status_code == 400
