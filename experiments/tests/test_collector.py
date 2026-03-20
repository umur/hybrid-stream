"""Tests for MetricsCollector."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import time
import pytest
from unittest.mock import patch

from metrics.collector import MetricsCollector, MetricSnapshot


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

def _make_collector(config_id: str = "W1-HS-N1", repetition: int = 1, warmup_s: int = 600) -> MetricsCollector:
    collector = MetricsCollector(config_id=config_id, repetition=repetition, warmup_s=warmup_s)
    # Pin the start time so elapsed arithmetic is deterministic
    collector._start_time = 0.0
    collector._ingest_window_start = 0.0
    return collector


# ---------------------------------------------------------------------------
# record_latency
# ---------------------------------------------------------------------------

def test_record_latency_stores_samples_per_operator_type():
    """record_latency appends latency values into a per-operator list."""
    c = _make_collector()
    c.record_latency("filter", 10.0)
    c.record_latency("filter", 20.0)
    c.record_latency("join", 15.0)

    assert c._latency_samples["filter"] == [10.0, 20.0]
    assert c._latency_samples["join"] == [15.0]


def test_record_latency_without_slo_does_not_populate_slo_counters():
    """record_latency without slo_ms must not touch _slo_counters."""
    c = _make_collector()
    c.record_latency("filter", 10.0)

    assert "filter" not in c._slo_counters


def test_record_latency_tracks_slo_compliance_compliant():
    """Latency at or below slo_ms increments compliant counter."""
    c = _make_collector()
    c.record_latency("filter", 10.0, slo_ms=10.0)  # exactly at SLO boundary — compliant

    compliant, total = c._slo_counters["filter"]
    assert compliant == 1
    assert total == 1


def test_record_latency_tracks_slo_compliance_non_compliant():
    """Latency above slo_ms increments only the total counter."""
    c = _make_collector()
    c.record_latency("filter", 15.0, slo_ms=10.0)

    compliant, total = c._slo_counters["filter"]
    assert compliant == 0
    assert total == 1


def test_record_latency_accumulates_multiple_slo_measurements():
    """Multiple calls accumulate compliant and total counts independently per operator."""
    c = _make_collector()
    c.record_latency("join", 5.0, slo_ms=10.0)   # compliant
    c.record_latency("join", 8.0, slo_ms=10.0)   # compliant
    c.record_latency("join", 12.0, slo_ms=10.0)  # non-compliant

    compliant, total = c._slo_counters["join"]
    assert compliant == 2
    assert total == 3


# ---------------------------------------------------------------------------
# record_ingest
# ---------------------------------------------------------------------------

def test_record_ingest_increments_counter():
    """record_ingest adds n_events to _ingest_count."""
    c = _make_collector()
    c.record_ingest(100)
    c.record_ingest(50)

    assert c._ingest_count == 150


def test_record_ingest_starts_at_zero():
    """_ingest_count begins at 0 before any records are ingested."""
    c = _make_collector()
    assert c._ingest_count == 0


# ---------------------------------------------------------------------------
# record_migration
# ---------------------------------------------------------------------------

def test_record_migration_stores_pause_duration():
    """record_migration appends the pause duration to _migration_times."""
    c = _make_collector()
    c.record_migration(42.5)
    c.record_migration(10.0)

    assert c._migration_times == [42.5, 10.0]


# ---------------------------------------------------------------------------
# record_edge_utilization
# ---------------------------------------------------------------------------

def test_record_edge_utilization_stores_max_of_cpu_and_mem():
    """record_edge_utilization stores max(cpu_frac, mem_frac)."""
    c = _make_collector()
    c.record_edge_utilization(cpu_frac=0.6, mem_frac=0.8)

    assert c._edge_utilizations == [0.8]


def test_record_edge_utilization_stores_cpu_when_higher():
    """record_edge_utilization stores cpu_frac when it exceeds mem_frac."""
    c = _make_collector()
    c.record_edge_utilization(cpu_frac=0.9, mem_frac=0.4)

    assert c._edge_utilizations == [0.9]


def test_record_edge_utilization_stores_equal_values():
    """record_edge_utilization stores the value when cpu == mem."""
    c = _make_collector()
    c.record_edge_utilization(cpu_frac=0.7, mem_frac=0.7)

    assert c._edge_utilizations == [0.7]


# ---------------------------------------------------------------------------
# _build_snapshot
# ---------------------------------------------------------------------------

def test_build_snapshot_computes_m1_p95_latency():
    """_build_snapshot computes the P95 latency per operator type (M1)."""
    c = _make_collector()
    # 20 samples for "filter": P95 of [1..20] sorted = index ceil(20*0.95)-1 = 18 => value 19
    for v in range(1, 21):
        c.record_latency("filter", float(v))

    snap = c._build_snapshot()

    sorted_s = sorted(range(1, 21))
    idx = min(19, max(0, math.ceil(20 * 0.95) - 1))
    expected = float(sorted_s[idx])
    assert snap.m1_p95_latency_ms["filter"] == pytest.approx(expected)


def test_build_snapshot_computes_m2_slo_compliance_ratio():
    """_build_snapshot computes compliance ratio = compliant/total (M2)."""
    c = _make_collector()
    # 3 compliant out of 4
    c.record_latency("filter", 5.0, slo_ms=10.0)
    c.record_latency("filter", 8.0, slo_ms=10.0)
    c.record_latency("filter", 9.0, slo_ms=10.0)
    c.record_latency("filter", 15.0, slo_ms=10.0)

    snap = c._build_snapshot()

    assert snap.m2_slo_compliance["filter"] == pytest.approx(0.75)


def test_build_snapshot_computes_m3_throughput():
    """_build_snapshot computes M3 as events / elapsed window seconds."""
    c = _make_collector()
    c.record_ingest(500)
    # Simulate 5-second window: ingest_window_start=0, "now"=5
    with patch("metrics.collector.time.monotonic", return_value=5.0):
        snap = c._build_snapshot()

    assert snap.m3_throughput_eps == pytest.approx(100.0)


def test_build_snapshot_computes_m4_max_migration_pause():
    """_build_snapshot reports the maximum migration pause (M4)."""
    c = _make_collector()
    c.record_migration(10.0)
    c.record_migration(50.0)
    c.record_migration(25.0)

    snap = c._build_snapshot()

    assert snap.m4_migration_pause_ms == pytest.approx(50.0)


def test_build_snapshot_m4_is_zero_when_no_migrations():
    """_build_snapshot returns M4 = 0.0 when no migrations were recorded."""
    c = _make_collector()
    snap = c._build_snapshot()
    assert snap.m4_migration_pause_ms == pytest.approx(0.0)


def test_build_snapshot_computes_m5_mean_aode_overhead():
    """_build_snapshot computes M5 as mean AODE recalibration overhead."""
    c = _make_collector()
    c.record_aode_overhead(4.0)
    c.record_aode_overhead(6.0)

    snap = c._build_snapshot()

    assert snap.m5_aode_overhead_ms == pytest.approx(5.0)


def test_build_snapshot_computes_m6_mean_edge_utilization():
    """_build_snapshot computes M6 as mean edge resource utilization."""
    c = _make_collector()
    c.record_edge_utilization(0.6, 0.8)  # stores 0.8
    c.record_edge_utilization(0.4, 0.2)  # stores 0.4

    snap = c._build_snapshot()

    assert snap.m6_edge_utilization == pytest.approx(0.6)


def test_build_snapshot_clears_accumulators():
    """_build_snapshot clears all accumulator buffers after producing a snapshot."""
    c = _make_collector()
    c.record_latency("filter", 10.0, slo_ms=20.0)
    c.record_ingest(100)
    c.record_migration(5.0)
    c.record_aode_overhead(2.0)
    c.record_edge_utilization(0.5, 0.3)

    c._build_snapshot()

    assert c._latency_samples == {}
    assert c._slo_counters == {}
    assert c._ingest_count == 0
    assert c._migration_times == []
    assert c._aode_overhead_samples == []
    assert c._edge_utilizations == []


def test_build_snapshot_sets_correct_config_id_and_repetition():
    """_build_snapshot populates config_id and repetition from constructor args."""
    c = _make_collector(config_id="W3-B2-N2", repetition=7)
    snap = c._build_snapshot()

    assert snap.config_id == "W3-B2-N2"
    assert snap.repetition == 7


# ---------------------------------------------------------------------------
# get_snapshots
# ---------------------------------------------------------------------------

def test_get_snapshots_post_warmup_only_filters_warmup_snapshots():
    """get_snapshots(post_warmup_only=True) returns only snapshots with timestamp >= warmup_s."""
    c = _make_collector(warmup_s=600)

    # Directly inject synthetic snapshots with known timestamps
    warmup_snap = MetricSnapshot(timestamp=300.0, config_id="W1-HS-N1", repetition=1)
    post_snap   = MetricSnapshot(timestamp=700.0, config_id="W1-HS-N1", repetition=1)
    c._snapshots = [warmup_snap, post_snap]

    result = c.get_snapshots(post_warmup_only=True)

    assert len(result) == 1
    assert result[0].timestamp == 700.0


def test_get_snapshots_post_warmup_only_excludes_exactly_at_boundary():
    """get_snapshots(post_warmup_only=True) excludes snapshots with timestamp < warmup_s."""
    c = _make_collector(warmup_s=600)
    below = MetricSnapshot(timestamp=599.9, config_id="W1-HS-N1", repetition=1)
    at    = MetricSnapshot(timestamp=600.0, config_id="W1-HS-N1", repetition=1)
    c._snapshots = [below, at]

    result = c.get_snapshots(post_warmup_only=True)

    assert len(result) == 1
    assert result[0].timestamp == 600.0


def test_get_snapshots_default_returns_post_warmup():
    """get_snapshots() with no arguments defaults to post_warmup_only=True."""
    c = _make_collector(warmup_s=600)
    warmup_snap = MetricSnapshot(timestamp=200.0, config_id="W1-HS-N1", repetition=1)
    post_snap   = MetricSnapshot(timestamp=800.0, config_id="W1-HS-N1", repetition=1)
    c._snapshots = [warmup_snap, post_snap]

    result = c.get_snapshots()

    assert all(s.timestamp >= 600 for s in result)


def test_get_snapshots_all_returns_everything():
    """get_snapshots(warmup_only=False, post_warmup_only=False) returns all snapshots."""
    c = _make_collector(warmup_s=600)
    snaps = [
        MetricSnapshot(timestamp=100.0, config_id="W1-HS-N1", repetition=1),
        MetricSnapshot(timestamp=700.0, config_id="W1-HS-N1", repetition=1),
    ]
    c._snapshots = snaps

    result = c.get_snapshots(warmup_only=False, post_warmup_only=False)

    assert len(result) == 2
