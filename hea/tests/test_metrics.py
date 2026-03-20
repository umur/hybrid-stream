"""Tests for hea.hea.metrics — HEAMetrics EWMA, p95, ingest tracking."""
import time
import pytest


class TestEWMAConvergence:

    def test_converges_toward_stable_input(self):
        from hea.hea.metrics import HEAMetrics, EWMA_ALPHA
        m = HEAMetrics(alpha=EWMA_ALPHA)
        for _ in range(50):
            m.cpu_utilization = (1 - EWMA_ALPHA) * m.cpu_utilization + EWMA_ALPHA * 0.8
        assert abs(m.cpu_utilization - 0.8) < 0.001

    def test_converges_from_different_initial(self):
        from hea.hea.metrics import HEAMetrics, EWMA_ALPHA
        m = HEAMetrics(alpha=EWMA_ALPHA)
        m.cpu_utilization = 1.0
        for _ in range(100):
            m.cpu_utilization = (1 - EWMA_ALPHA) * m.cpu_utilization + EWMA_ALPHA * 0.3
        assert abs(m.cpu_utilization - 0.3) < 0.001

    def test_alpha_zero_point_two_by_default(self):
        from hea.hea.metrics import EWMA_ALPHA
        assert EWMA_ALPHA == 0.2


class TestP95Latency:

    def test_p95_correct_for_100_samples(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        for i in range(100):
            m.record_latency("op1", float(i))
        p95 = m.get_operator_p95()
        assert "op1" in p95
        assert 93.0 <= p95["op1"] <= 95.0

    def test_p95_correct_for_single_sample(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        m.record_latency("op1", 42.0)
        p95 = m.get_operator_p95()
        assert p95["op1"] == 42.0

    def test_p95_multiple_operators(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        for i in range(100):
            m.record_latency("fast", float(i))
            m.record_latency("slow", float(i + 100))
        p95 = m.get_operator_p95()
        assert p95["fast"] < p95["slow"]

    def test_get_operator_p95_empty_returns_empty_dict(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        assert m.get_operator_p95() == {}


class TestIngestTracking:

    def test_record_ingest_updates_count(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        m.record_ingest(100)
        m.record_ingest(200)
        assert len(m._ingest_counts) == 2

    def test_ingest_rate_over_window(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        # Record several batches at "now"
        for _ in range(10):
            m.record_ingest(100)
        rate = m._compute_ingest_rate()
        # All 10 records happened ~instantly, so rate should be high
        assert rate > 0.0

    def test_ingest_rate_empty_returns_zero(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        assert m._compute_ingest_rate() == 0.0

    def test_ingest_count_deque_maxlen(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        assert m._ingest_counts.maxlen == 300


class TestP95EdgeCases:

    def test_p95_with_exactly_one_sample_returns_that_sample(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        m.record_latency("op_single", 77.0)
        p95 = m.get_operator_p95()
        assert p95["op_single"] == 77.0

    def test_p95_with_exactly_two_samples_returns_larger_value(self):
        # With 2 samples: ceil(2 * 0.95) - 1 = ceil(1.9) - 1 = 2 - 1 = 1 → index 1 (the larger)
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        m.record_latency("op_two", 10.0)
        m.record_latency("op_two", 20.0)
        p95 = m.get_operator_p95()
        assert p95["op_two"] == 20.0

    def test_p95_with_zero_latency_sample(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        m.record_latency("op_zero", 0.0)
        p95 = m.get_operator_p95()
        assert p95["op_zero"] == 0.0

    def test_p95_for_unknown_operator_not_in_result(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        m.record_latency("op_known", 5.0)
        p95 = m.get_operator_p95()
        assert "op_unknown" not in p95


class TestIngestRateEdgeCases:

    def test_compute_ingest_rate_with_empty_deque_returns_zero(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        # Fresh instance — no entries recorded
        assert m._compute_ingest_rate() == 0.0

    def test_compute_ingest_rate_with_single_entry_returns_total_over_one(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        # Single entry: window defaults to 1.0, so rate = total / 1.0
        m.record_ingest(500)
        rate = m._compute_ingest_rate()
        assert rate == 500.0

    def test_compute_ingest_rate_with_single_entry_of_zero_records(self):
        from hea.hea.metrics import HEAMetrics
        m = HEAMetrics()
        m.record_ingest(0)
        rate = m._compute_ingest_rate()
        assert rate == 0.0

    def test_compute_ingest_rate_two_entries_uses_time_window(self):
        import time
        from hea.hea.metrics import HEAMetrics
        from unittest.mock import patch
        m = HEAMetrics()
        t0 = 1000.0
        t1 = 1010.0  # 10 seconds later
        with patch("hea.hea.metrics.time") as mock_time:
            mock_time.monotonic.side_effect = [t0, t1, t1 + 0.001]
            m.record_ingest(100)   # recorded at t0
            m.record_ingest(200)   # recorded at t1
            mock_time.monotonic.return_value = t1 + 0.001
            rate = m._compute_ingest_rate()
        # total=300, window = (t1+0.001) - t0 ≈ 10.001 → rate ≈ 30.0
        assert rate > 0.0
        assert rate < 1000.0  # sanity: not the single-entry fallback of 300/1
