"""领域服务注册表：通用资源路由按模块 key 分派到独立业务服务。"""
from __future__ import annotations

from app.services.base import BaseModuleService
from app.services.metric_def import MetricDefService
from app.services.dim_query import DimQueryService
from app.services.experiment import ExperimentService
from app.services.significance import SignificanceService
from app.services.cohort import CohortService
from app.services.data_service import DataServiceService
from app.services.anomaly_detect import AnomalyDetectService
from app.services.analysis_chart import AnalysisChartService
from app.services.aggregate_job import AggregateJobService
from app.services.drill_down import DrillDownService
from app.services.data_export import DataExportService
from app.services.data_freshness import DataFreshnessService
from app.services.query_cache import QueryCacheService
from app.services.segment_compare import SegmentCompareService
from app.services.metric_calibrate import MetricCalibrateService
from app.services.query_log import QueryLogService
from app.services.data_sample import DataSampleService
from app.services.report_schedule import ReportScheduleService

SERVICES: dict[str, BaseModuleService] = {
    "metric_def": MetricDefService(),
    "dim_query": DimQueryService(),
    "experiment": ExperimentService(),
    "significance": SignificanceService(),
    "cohort": CohortService(),
    "data_service": DataServiceService(),
    "anomaly_detect": AnomalyDetectService(),
    "analysis_chart": AnalysisChartService(),
    "aggregate_job": AggregateJobService(),
    "drill_down": DrillDownService(),
    "data_export": DataExportService(),
    "data_freshness": DataFreshnessService(),
    "query_cache": QueryCacheService(),
    "segment_compare": SegmentCompareService(),
    "metric_calibrate": MetricCalibrateService(),
    "query_log": QueryLogService(),
    "data_sample": DataSampleService(),
    "report_schedule": ReportScheduleService(),
}


def service_for(module: str) -> BaseModuleService | None:
    return SERVICES.get(module)
