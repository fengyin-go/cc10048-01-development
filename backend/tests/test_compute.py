"""计算引擎单元测试：聚合、T检验、卡方、采样、异常检测、偏差、时效。"""
import math

import pytest

from app.compute import (
    _chi_square_p_value,
    _t_distribution_p_value,
    aggregate,
    anomaly_iqr,
    anomaly_zscore,
    cache_hit_simulation,
    chi_square_test,
    compute_calibrate_bias,
    compute_freshness_delay,
    generate_mock_metric_values,
    random_sample,
    segment_diff_report,
    t_test,
)


class TestAggregate:
    def test_sum(self):
        assert aggregate([1, 2, 3, 4, 5], "sum") == 15.0

    def test_avg(self):
        assert aggregate([1, 2, 3, 4, 5], "mean") == 3.0

    def test_max_min(self):
        assert aggregate([1, 2, 3, 4, 5], "max") == 5.0
        assert aggregate([1, 2, 3, 4, 5], "min") == 1.0

    def test_count_distinct(self):
        assert aggregate([1, 1, 2, 2, 3], "count_distinct") == 3.0

    def test_median_odd(self):
        assert aggregate([1, 2, 3, 4, 5], "median") == 3.0

    def test_median_even(self):
        assert aggregate([1, 2, 3, 4], "median") == 2.5

    def test_stddev(self):
        assert aggregate([1, 2, 3], "stddev") == pytest.approx(1.0, abs=0.01)

    def test_empty(self):
        assert aggregate([], "sum") == 0.0


class TestTTest:
    def test_same_means(self):
        result = t_test([100, 102, 98], [100, 101, 99])
        assert not result["significant"]
        assert result["p_value"] > 0.5

    def test_different_means(self):
        a = [110 + i for i in range(30)]
        b = [100 + i for i in range(30)]
        result = t_test(a, b)
        assert result["significant"]
        assert result["p_value"] < 0.05
        assert result["diff_pct"] > 0

    def test_small_sample(self):
        result = t_test([100], [101, 102])
        assert result["p_value"] == 1.0

    def test_output_fields(self):
        result = t_test([100, 102, 98, 101], [95, 97, 96, 94])
        for key in ["method", "significant", "p_value", "mean_a", "mean_b", "diff_pct", "ci_lower", "ci_upper"]:
            assert key in result


class TestChiSquare:
    def test_fit_good(self):
        result = chi_square_test([50, 30, 20], [50, 30, 20])
        assert not result["significant"]
        assert result["statistic"] == pytest.approx(0.0, abs=0.01)

    def test_empty(self):
        result = chi_square_test([], [])
        assert result["p_value"] == 1.0


class TestRandomSample:
    def test_random_sample(self):
        data = [{"id": i, "val": i} for i in range(100)]
        sampled = random_sample(data, "random", 0.3, seed=42)
        assert len(sampled) == 30
        assert len(sampled) < len(data)

    def test_stratified(self):
        data = [{"id": i, "status": "A" if i < 30 else "B"} for i in range(100)]
        sampled = random_sample(data, "stratified", 0.2, seed=42)
        assert len(sampled) > 0
        # 至少包含A和B分层
        statuses = {s["status"] for s in sampled}
        assert len(statuses) >= 1

    def test_reservoir(self):
        data = [{"id": i} for i in range(100)]
        sampled = random_sample(data, "reservoir", 0.5, seed=42)
        assert len(sampled) == 50

    def test_full_sample(self):
        data = [{"id": i} for i in range(5)]
        sampled = random_sample(data, "random", 1.0, seed=42)
        assert len(sampled) == 5


class TestAnomalyDetection:
    def test_iqr_no_anomaly(self):
        data = [float(i) for i in range(100)]
        result = anomaly_iqr(data)
        assert result["anomaly_count"] == 0

    def test_iqr_with_anomaly(self):
        data = [float(i) for i in range(100)] + [500.0, -100.0]
        result = anomaly_iqr(data)
        assert result["anomaly_count"] >= 1

    def test_zscore_no_anomaly(self):
        data = [float(i) for i in range(100)]
        result = anomaly_zscore(data, threshold=5.0)
        assert result["anomaly_count"] == 0

    def test_zscore_small_data(self):
        result = anomaly_zscore([1.0, 2.0])
        assert result["anomaly_count"] == 0


class TestCalibrateBias:
    def test_positive_bias(self):
        result = compute_calibrate_bias(100.0, 105.0)
        assert result["bias_pct"] == 5.0
        assert result["direction"] == "up"

    def test_negative_bias(self):
        result = compute_calibrate_bias(100.0, 95.0)
        assert result["bias_pct"] == -5.0
        assert result["direction"] == "down"

    def test_zero_original(self):
        result = compute_calibrate_bias(0.0, 5.0)
        assert result["bias_pct"] == float("inf")


class TestFreshness:
    def test_fresh(self):
        from datetime import datetime
        now = datetime.now()
        result = compute_freshness_delay(24, now.isoformat(), now.isoformat())
        assert result["status"] == "及时"

    def test_no_last_check(self):
        result = compute_freshness_delay(24, None)
        assert result["status"] in ("及时", "延迟", "严重延迟")


class TestCacheSimulation:
    def test_cache_key(self):
        result = cache_hit_simulation("test_key", 3600)
        assert result["cache_key"] == "test_key"
        assert "hit" in result
        assert result["size_bytes"] > 0


class TestSegmentDiff:
    def test_report_fields(self):
        report = segment_diff_report([100.0, 102.0], [95.0, 96.0])
        assert "count_a" in report
        assert "count_b" in report
        assert "std_a" in report
        assert "std_b" in report


class TestGenerateMock:
    def test_generate_values(self):
        vals = generate_mock_metric_values(30)
        assert len(vals) == 30
        assert all(isinstance(v, float) for v in vals)


class TestTDistribution:
    def test_large_t(self):
        p = _t_distribution_p_value(10.0, 10)
        assert p < 0.001

    def test_small_t(self):
        p = _t_distribution_p_value(0.01, 30)
        assert p > 0.5


class TestChiSquarePValue:
    def test_no_variation(self):
        p = _chi_square_p_value(0.0, 1)
        assert p >= 0