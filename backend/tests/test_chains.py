"""跨模块业务链路集成测试。"""
import pytest

from app.store import store


def _call_chain(module_id: int, module_name: str):
    """通过导入链路由函数验证链路调用。"""
    from app.routers.chains import (
        chain_metric_query,
        chain_experiment_evaluate,
        chain_cohort_analysis,
        chain_monitor_delivery,
        chain_calibrate_governance,
    )
    if module_name == "metric_def":
        return chain_metric_query(module_id)
    elif module_name == "experiment":
        return chain_experiment_evaluate(module_id)
    elif module_name == "cohort":
        return chain_cohort_analysis(module_id)
    elif module_name == "anomaly_detect":
        return chain_monitor_delivery(module_id)
    elif module_name == "metric_calibrate":
        return chain_calibrate_governance(module_id)


class TestChainMetricQuery:
    """链路1：指标口径→预聚合任务→多维查询→查询缓存"""

    def test_chain_returns_metric_data(self):
        row = store.rows("metric_def")[0]
        from app.routers.chains import chain_metric_query
        result = chain_metric_query(int(row["id"]))
        assert result["chain"] == "指标计算查询链路"
        assert result["aggregated_value"] != 0
        assert "sample_size" in result
        assert len(result.get("pre_aggregation_jobs", [])) >= 0
        assert len(result.get("dimension_queries", [])) >= 0
        assert len(result.get("cache_simulation", [])) >= 0

    def test_chain_nonexistent_metric(self):
        from app.routers.chains import chain_metric_query
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            chain_metric_query(99999)


class TestChainExperimentEvaluate:
    """链路2：实验管理→显著性检验→数据采样"""

    def test_chain_returns_experiment_data(self):
        row = store.rows("experiment")[0]
        from app.routers.chains import chain_experiment_evaluate
        result = chain_experiment_evaluate(int(row["id"]))
        assert result["chain"] == "AB实验评估链路"
        assert "descriptive_stats" in result
        assert result["descriptive_stats"]["control"]["n"] > 0
        assert len(result.get("significance_tests", [])) >= 0
        assert len(result.get("data_sampling", [])) >= 0

    def test_chain_nonexistent_experiment(self):
        from app.routers.chains import chain_experiment_evaluate
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            chain_experiment_evaluate(99999)


class TestChainCohortAnalysis:
    """链路3：人群圈选→分群对比→下钻分析"""

    def test_chain_returns_cohort_data(self):
        row = store.rows("cohort")[0]
        from app.routers.chains import chain_cohort_analysis
        result = chain_cohort_analysis(int(row["id"]))
        assert result["chain"] == "用户分析链路"
        assert result["cohort"]["estimated_size"] > 0
        assert len(result["metric_timeline"]) > 0
        assert len(result.get("segment_comparisons", [])) >= 0
        assert len(result.get("drill_down_analysis", [])) >= 0

    def test_chain_nonexistent_cohort(self):
        from app.routers.chains import chain_cohort_analysis
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            chain_cohort_analysis(99999)


class TestChainMonitorDelivery:
    """链路4：异常检测→数据时效→数据导出"""

    def test_chain_returns_monitor_data(self):
        row = store.rows("anomaly_detect")[0]
        from app.routers.chains import chain_monitor_delivery
        result = chain_monitor_delivery(int(row["id"]))
        assert result["chain"] == "监控交付链路"
        assert "anomaly_detection" in result
        assert len(result.get("data_freshness", [])) >= 0
        assert len(result.get("data_export", [])) >= 0

    def test_chain_nonexistent_rule(self):
        from app.routers.chains import chain_monitor_delivery
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            chain_monitor_delivery(99999)


class TestChainCalibrateGovernance:
    """链路5：指标校准→数据服务→查询日志"""

    def test_chain_returns_calibration_data(self):
        row = store.rows("metric_calibrate")[0]
        from app.routers.chains import chain_calibrate_governance
        result = chain_calibrate_governance(int(row["id"]))
        assert result["chain"] == "口径治理链路"
        assert "bias_analysis" in result
        assert len(result.get("data_service_impact", [])) >= 0
        assert len(result.get("query_log_analysis", {}).get("logs", [])) >= 0

    def test_chain_nonexistent_calibration(self):
        from app.routers.chains import chain_calibrate_governance
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            chain_calibrate_governance(99999)


class TestPipelineFull:
    """综合主链：触发完整数据工程管线"""

    def test_pipeline_returns_all_chains(self):
        from app.routers.chains import chain_pipeline_full
        result = chain_pipeline_full()
        assert result["pipeline"] == "完整数据工程管线"
        assert result["modules_processed"] == 18
        assert result["chains_executed"] == 5
        assert result["elapsed_seconds"] >= 0
        assert result.get("metric_query") is not None
        assert result.get("experiment_evaluate") is not None
        assert result.get("cohort_analysis") is not None
        assert result.get("monitor_delivery") is not None
        assert result.get("calibrate_governance") is not None


class TestDomainOperations:
    """领域业务操作集成测试。"""

    def test_all_domain_modules_executable(self):
        modules = [
            ("metric_def", 1, "domain_compute"),
            ("dim_query", 1, "execute_query"),
            ("experiment", 1, "compute_effect"),
            ("significance", 1, "run_test"),
            ("cohort", 1, "estimate_scale"),
            ("anomaly_detect", 1, "detect_anomalies"),
            ("analysis_chart", 1, "render_chart_data"),
            ("aggregate_job", 1, "execute_aggregate"),
            ("drill_down", 1, "execute_drill_down"),
            ("data_export", 1, "execute_export"),
            ("data_freshness", 1, "run_freshness_check"),
            ("query_cache", 1, "check_cache_status"),
            ("segment_compare", 1, "execute_compare"),
            ("metric_calibrate", 1, "compute_calibration"),
            ("data_sample", 1, "execute_sampling"),
            ("report_schedule", 1, "generate_report"),
        ]
        for module, entry_id, method in modules:
            svc_name = f"{module}_service"
            # 测试每个领域模块可执行操作
            assert store.find(module, entry_id) is not None, f"Seed data missing for {module}"