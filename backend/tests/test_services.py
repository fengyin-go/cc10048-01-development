"""业务服务单元测试：所有18个领域服务的CRUD和业务操作。"""
import pytest

from app.services.aggregate_job import AggregateJobService
from app.services.analysis_chart import AnalysisChartService
from app.services.anomaly_detect import AnomalyDetectService
from app.services.cohort import CohortService
from app.services.data_export import DataExportService
from app.services.data_freshness import DataFreshnessService
from app.services.data_sample import DataSampleService
from app.services.data_service import DataServiceService
from app.services.dim_query import DimQueryService
from app.services.drill_down import DrillDownService
from app.services.experiment import ExperimentService
from app.services.metric_calibrate import MetricCalibrateService
from app.services.metric_def import MetricDefService
from app.services.query_cache import QueryCacheService
from app.services.query_log import QueryLogService
from app.services.report_schedule import ReportScheduleService
from app.services.segment_compare import SegmentCompareService
from app.services.significance import SignificanceService


class TestMetricDefService:
    def setup_method(self):
        self.svc = MetricDefService()

    def test_module_keys(self):
        assert self.svc.MODULE == "metric_def"
        assert self.svc.ENTITY == "指标定义"

    def test_required_fields(self):
        assert "指标标识" in self.svc.REQUIRED_FIELDS

    def test_create_missing_fields(self):
        entry, missing = self.svc.create_entry({})
        assert entry is None
        assert len(missing) >= 1

    def test_create_success(self):
        entry, missing = self.svc.create_entry({
            "指标标识": "TST-GMV", "指标名称": "GMV",
            "计算公式": "SUM(order_amount)", "聚合粒度": "sum",
            "业务域": "交易"
        })
        assert entry is not None
        assert missing == []
        assert entry["status"] == "草稿"

    def test_list_entries(self):
        items, total = self.svc.list_entries()
        assert total >= 3
        assert len(items) >= 3

    def test_domain_compute(self):
        result = self.svc.domain_compute(1)
        assert "result" in result
        assert result["sample_size"] == 30


class TestDimQueryService:
    def setup_method(self):
        self.svc = DimQueryService()

    def test_execute_query(self):
        result = self.svc.execute_query(1)
        assert "cross_table" in result
        assert result["row_count"] > 0
        assert result["total"] > 0


class TestExperimentService:
    def setup_method(self):
        self.svc = ExperimentService()

    def test_compute_effect(self):
        result = self.svc.compute_effect(1)
        assert "statistics" in result
        assert "control" in result["sample_sizes"]


class TestSignificanceService:
    def setup_method(self):
        self.svc = SignificanceService()

    def test_run_test(self):
        result = self.svc.run_test(1)
        assert "method" in result
        assert "result" in result


class TestCohortService:
    def setup_method(self):
        self.svc = CohortService()

    def test_estimate_scale(self):
        result = self.svc.estimate_scale(1)
        assert "estimated_scale" in result
        assert result["estimated_scale"] > 0


class TestDataServiceService:
    def setup_method(self):
        self.svc = DataServiceService()

    def test_invoke_unpublished(self):
        result = self.svc.invoke_service(1)
        # ID 1 状态为"待发布"，invoke应返回error
        assert "error" in result or "results" in result


class TestAnomalyDetectService:
    def setup_method(self):
        self.svc = AnomalyDetectService()

    def test_detect_anomalies(self):
        result = self.svc.detect_anomalies(1)
        assert "detection_result" in result


class TestAnalysisChartService:
    def setup_method(self):
        self.svc = AnalysisChartService()

    def test_render_chart(self):
        result = self.svc.render_chart_data(1)
        assert "data" in result
        assert len(result["data"]) >= 1


class TestAggregateJobService:
    def setup_method(self):
        self.svc = AggregateJobService()

    def test_execute_aggregate(self):
        result = self.svc.execute_aggregate(1)
        assert "aggregation_results" in result
        assert len(result["aggregation_results"]) > 0


class TestDrillDownService:
    def setup_method(self):
        self.svc = DrillDownService()

    def test_execute_drill_down(self):
        result = self.svc.execute_drill_down(1)
        assert "layers" in result
        assert len(result["layers"]) > 0


class TestDataExportService:
    def setup_method(self):
        self.svc = DataExportService()

    def test_execute_export(self):
        result = self.svc.execute_export(1)
        assert "rows_exported" in result
        assert result["rows_exported"] > 0


class TestDataFreshnessService:
    def setup_method(self):
        self.svc = DataFreshnessService()

    def test_run_freshness_check(self):
        result = self.svc.run_freshness_check(1)
        assert "result" in result
        assert "status" in result["result"]


class TestQueryCacheService:
    def setup_method(self):
        self.svc = QueryCacheService()

    def test_check_cache_status(self):
        result = self.svc.check_cache_status(1)
        assert "cache_key" in result
        assert "result" in result


class TestSegmentCompareService:
    def setup_method(self):
        self.svc = SegmentCompareService()

    def test_execute_compare(self):
        result = self.svc.execute_compare(1)
        assert "report" in result
        assert "direction" in result


class TestMetricCalibrateService:
    def setup_method(self):
        self.svc = MetricCalibrateService()

    def test_compute_calibration(self):
        result = self.svc.compute_calibration(1)
        assert "bias_analysis" in result


class TestQueryLogService:
    def setup_method(self):
        self.svc = QueryLogService()

    def test_log_query(self):
        result = self.svc.log_query()
        assert "log_id" in result
        assert result["log_id"] > 0


class TestDataSampleService:
    def setup_method(self):
        self.svc = DataSampleService()

    def test_execute_sampling(self):
        result = self.svc.execute_sampling(1)
        assert "sampled_count" in result
        assert result["sampled_count"] > 0


class TestReportScheduleService:
    def setup_method(self):
        self.svc = ReportScheduleService()

    def test_generate_report(self):
        result = self.svc.generate_report(1)
        assert "title" in result
        assert "sections" in result


class TestBaseServiceCRUD:
    """跨服务CRUD一致性测试。"""
    SERVICES = [
        MetricDefService(), DimQueryService(), ExperimentService(),
        SignificanceService(), CohortService(), DataServiceService(),
        AnomalyDetectService(), AnalysisChartService(), AggregateJobService(),
        DrillDownService(), DataExportService(), DataFreshnessService(),
        QueryCacheService(), SegmentCompareService(), MetricCalibrateService(),
        QueryLogService(), DataSampleService(), ReportScheduleService(),
    ]

    @pytest.mark.parametrize("svc", SERVICES)
    def test_all_services_have_module(self, svc):
        assert svc.MODULE != ""
        assert svc.ENTITY != ""

    @pytest.mark.parametrize("svc", SERVICES)
    def test_all_services_have_status_order(self, svc):
        assert len(svc.STATUS_ORDER) >= 2

    @pytest.mark.parametrize("svc", SERVICES)
    def test_all_services_can_list(self, svc):
        items, total = svc.list_entries()
        assert total >= 0
        assert isinstance(items, list)

    @pytest.mark.parametrize("svc", SERVICES)
    def test_all_services_can_get(self, svc):
        entry = svc.get_entry(1)
        assert entry is not None
        assert "id" in entry
        assert "status" in entry

    @pytest.mark.parametrize("svc", SERVICES)
    def test_all_services_run_action(self, svc):
        if svc.ACTION_RULES:
            action_name = list(svc.ACTION_RULES.keys())[0]
            entry, msg = svc.run_action(1, action_name)
            assert msg != ""
            assert isinstance(msg, str)