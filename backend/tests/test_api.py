"""FastAPI 集成测试：所有端点功能验证。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthAndOverview:
    def test_health(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["modules"] == 18

    def test_overview(self):
        resp = client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "cards" in data
        assert "modules" in data
        assert len(data["modules"]) == 18


class TestResourceCRUD:
    MODULES = [
        "metric_def", "dim_query", "experiment", "significance",
        "cohort", "data_service", "anomaly_detect", "analysis_chart",
        "aggregate_job", "drill_down", "data_export", "data_freshness",
        "query_cache", "segment_compare", "metric_calibrate",
        "query_log", "data_sample", "report_schedule",
    ]

    @pytest.mark.parametrize("module", MODULES)
    def test_list(self, module):
        resp = client.get(f"/api/{module}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert len(data["items"]) >= 3

    @pytest.mark.parametrize("module", MODULES)
    def test_get_entry(self, module):
        resp = client.get(f"/api/{module}/1")
        assert resp.status_code == 200
        entry = resp.json()
        assert "id" in entry
        assert "status" in entry

    @pytest.mark.parametrize("module", MODULES)
    def test_get_nonexistent(self, module):
        resp = client.get(f"/api/{module}/99999")
        assert resp.status_code == 404

    @pytest.mark.parametrize("module", MODULES)
    def test_export(self, module):
        resp = client.get(f"/api/{module}/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")


class TestChainEndpoints:
    def test_metric_query_chain(self):
        resp = client.get("/api/chains/metric-aggregate/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chain"] == "指标计算查询链路"

    def test_experiment_evaluate_chain(self):
        resp = client.get("/api/chains/experiment-evaluate/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chain"] == "AB实验评估链路"

    def test_cohort_analysis_chain(self):
        resp = client.get("/api/chains/cohort-analysis/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chain"] == "用户分析链路"

    def test_monitor_delivery_chain(self):
        resp = client.get("/api/chains/monitor-delivery/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chain"] == "监控交付链路"

    def test_calibrate_governance_chain(self):
        resp = client.get("/api/chains/calibrate-governance/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chain"] == "口径治理链路"

    def test_pipeline_full(self):
        resp = client.get("/api/chains/pipeline-full")
        assert resp.status_code == 200
        data = resp.json()
        assert data["modules_processed"] == 18
        assert data["chains_executed"] == 5

    def test_chain_nonexistent(self):
        resp = client.get("/api/chains/metric-aggregate/99999")
        assert resp.status_code == 404


class TestDomainEndpoints:
    def test_metric_compute(self):
        resp = client.get("/api/domain/metric_def/1/compute")
        assert resp.status_code == 200
        assert "result" in resp.json()

    def test_dim_query_execute(self):
        resp = client.get("/api/domain/dim_query/1/execute")
        assert resp.status_code == 200
        assert "cross_table" in resp.json()

    def test_experiment_compute(self):
        resp = client.get("/api/domain/experiment/1/compute-effect")
        assert resp.status_code == 200
        assert "sample_sizes" in resp.json()

    def test_significance_run(self):
        resp = client.get("/api/domain/significance/1/run-test")
        assert resp.status_code == 200
        assert "result" in resp.json()

    def test_cohort_estimate(self):
        resp = client.get("/api/domain/cohort/1/estimate-scale")
        assert resp.status_code == 200
        assert "estimated_scale" in resp.json()

    def test_anomaly_detect(self):
        resp = client.get("/api/domain/anomaly_detect/1/detect")
        assert resp.status_code == 200
        assert "detection_result" in resp.json()

    def test_aggregate_execute(self):
        resp = client.get("/api/domain/aggregate_job/1/execute")
        assert resp.status_code == 200
        assert "aggregation_results" in resp.json()

    def test_drill_down_execute(self):
        resp = client.get("/api/domain/drill_down/1/execute")
        assert resp.status_code == 200
        assert "layers" in resp.json()

    def test_data_export_execute(self):
        resp = client.get("/api/domain/data_export/1/execute")
        assert resp.status_code == 200
        assert "rows_exported" in resp.json()

    def test_data_freshness_check(self):
        resp = client.get("/api/domain/data_freshness/1/check")
        assert resp.status_code == 200
        assert "result" in resp.json()

    def test_query_cache_status(self):
        resp = client.get("/api/domain/query_cache/1/check-status")
        assert resp.status_code == 200
        assert "result" in resp.json()

    def test_segment_compare(self):
        resp = client.get("/api/domain/segment_compare/1/execute")
        assert resp.status_code == 200
        assert "report" in resp.json()

    def test_metric_calibrate(self):
        resp = client.get("/api/domain/metric_calibrate/1/compute")
        assert resp.status_code == 200
        assert "bias_analysis" in resp.json()

    def test_query_log(self):
        resp = client.post("/api/domain/query_log/log")
        assert resp.status_code == 200
        assert "log_id" in resp.json()

    def test_data_sample(self):
        resp = client.get("/api/domain/data_sample/1/execute")
        assert resp.status_code == 200
        assert "sampled_count" in resp.json()

    def test_report_generate(self):
        resp = client.get("/api/domain/report_schedule/1/generate")
        assert resp.status_code == 200
        assert "title" in resp.json()


class TestCreateEntry:
    def test_create_and_list(self):
        resp = client.post("/api/metric_def", json={
            "values": {"指标标识": "TST-NEW", "指标名称": "测试指标",
                       "计算公式": "COUNT(*)", "聚合粒度": "count",
                       "业务域": "测试"}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_create_missing_fields(self):
        resp = client.post("/api/metric_def", json={
            "values": {"指标标识": "TST-PARTIAL"}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False


class TestAction:
    def test_run_action(self):
        resp = client.post("/api/metric_def/1/actions", json={"action": "提交审批"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_invalid_action(self):
        resp = client.post("/api/metric_def/1/actions", json={"action": "不存在的动作"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False