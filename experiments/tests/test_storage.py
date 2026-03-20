"""Tests for metrics storage save/load roundtrip."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch

from metrics.storage import save_snapshots, load_all_results
from metrics.collector import MetricSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_snapshot(timestamp: float, config_id: str = "W1-HS-N1", repetition: int = 1) -> MetricSnapshot:
    return MetricSnapshot(
        timestamp=timestamp,
        config_id=config_id,
        repetition=repetition,
        m1_p95_latency_ms={"filter": 12.5, "join": 20.1},
        m2_slo_compliance={"filter": 0.98, "join": 0.92},
        m3_throughput_eps=1000.0,
        m4_migration_pause_ms=5.0,
        m5_aode_overhead_ms=1.2,
        m6_edge_utilization=0.75,
    )


def _make_snapshot_no_op_types(timestamp: float, config_id: str = "W1-HS-N1", repetition: int = 1) -> MetricSnapshot:
    """Snapshot with empty operator dicts — exercises the _global row path."""
    return MetricSnapshot(
        timestamp=timestamp,
        config_id=config_id,
        repetition=repetition,
        m1_p95_latency_ms={},
        m2_slo_compliance={},
        m3_throughput_eps=500.0,
        m4_migration_pause_ms=0.0,
        m5_aode_overhead_ms=0.0,
        m6_edge_utilization=0.5,
    )


# ---------------------------------------------------------------------------
# save_snapshots tests
# ---------------------------------------------------------------------------

def test_save_snapshots_with_empty_list_returns_none(tmp_path):
    """save_snapshots returns None when the snapshot list is empty."""
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        result = save_snapshots([], "W1-HS-N1", repetition=1)
    assert result is None


def test_save_snapshots_creates_parquet_at_correct_path(tmp_path):
    """save_snapshots writes a file named rep_01.parquet inside config_id directory."""
    snap = _make_snapshot(timestamp=700.0)
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        path = save_snapshots([snap], "W1-HS-N1", repetition=1)
    assert path is not None
    assert path == tmp_path / "W1-HS-N1" / "rep_01.parquet"
    assert path.exists()


def test_save_snapshots_repetition_zero_padding(tmp_path):
    """Repetition number is zero-padded to 2 digits in the filename."""
    snap = _make_snapshot(timestamp=700.0)
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        path = save_snapshots([snap], "W2-B1-N2", repetition=5)
    assert path.name == "rep_05.parquet"


def test_save_snapshots_load_roundtrip_preserves_data(tmp_path):
    """Data written by save_snapshots is recovered identically via load_all_results."""
    snap = _make_snapshot(timestamp=700.0, config_id="W1-HS-N1", repetition=1)
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        save_snapshots([snap], "W1-HS-N1", repetition=1)
        df = load_all_results()

    assert len(df) > 0
    # Both operator rows should be present
    assert set(df["operator_type"].unique()) == {"filter", "join"}
    row = df[df["operator_type"] == "filter"].iloc[0]
    assert row["m3_throughput_eps"] == pytest.approx(1000.0)
    assert row["m4_migration_pause_ms"] == pytest.approx(5.0)
    assert row["m5_aode_overhead_ms"] == pytest.approx(1.2)
    assert row["m6_edge_utilization"] == pytest.approx(0.75)


def test_save_snapshots_roundtrip_global_row(tmp_path):
    """Snapshots without operator types produce a single _global row."""
    snap = _make_snapshot_no_op_types(timestamp=700.0, config_id="W1-HS-N1", repetition=1)
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        save_snapshots([snap], "W1-HS-N1", repetition=1)
        df = load_all_results()

    assert len(df) == 1
    assert df.iloc[0]["operator_type"] == "_global"
    assert df.iloc[0]["m3_throughput_eps"] == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# load_all_results tests
# ---------------------------------------------------------------------------

def test_load_all_results_raises_when_no_results(tmp_path):
    """load_all_results raises FileNotFoundError when no parquet files exist."""
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        with pytest.raises(FileNotFoundError):
            load_all_results()


def test_load_all_results_parses_config_id_columns(tmp_path):
    """load_all_results splits config_id into workload, system, network columns."""
    snap = _make_snapshot(timestamp=700.0, config_id="W2-B2-N3", repetition=1)
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        save_snapshots([snap], "W2-B2-N3", repetition=1)
        df = load_all_results()

    assert "workload" in df.columns
    assert "system" in df.columns
    assert "network" in df.columns
    assert (df["workload"] == "W2").all()
    assert (df["system"] == "B2").all()
    assert (df["network"] == "N3").all()


def test_load_all_results_filters_warmup_period(tmp_path):
    """Rows with timestamp_s < 600 are excluded from load_all_results output."""
    warmup_snap = _make_snapshot(timestamp=300.0, config_id="W1-HS-N1", repetition=1)
    post_snap = _make_snapshot(timestamp=700.0, config_id="W1-HS-N1", repetition=1)
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        save_snapshots([warmup_snap, post_snap], "W1-HS-N1", repetition=1)
        df = load_all_results()

    assert (df["timestamp_s"] >= 600).all(), "Warmup rows (timestamp_s < 600) must be filtered out"


def test_load_all_results_warmup_rows_missing_entirely(tmp_path):
    """When all rows are within warmup period, load_all_results returns empty DataFrame."""
    warmup_snap = _make_snapshot(timestamp=100.0, config_id="W1-HS-N1", repetition=1)
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        save_snapshots([warmup_snap], "W1-HS-N1", repetition=1)
        df = load_all_results()

    assert len(df) == 0


def test_load_all_results_config_id_with_hyphenated_system_name(tmp_path):
    """config_id with n=2 split handles system names that contain hyphens."""
    # e.g. "W1-HybridStream-N1" -> workload=W1, system=HybridStream, network=N1
    snap = _make_snapshot(timestamp=700.0, config_id="W1-HybridStream-N1", repetition=1)
    with patch("metrics.storage.RESULTS_DIR", tmp_path):
        save_snapshots([snap], "W1-HybridStream-N1", repetition=1)
        df = load_all_results()

    assert (df["workload"] == "W1").all()
    assert (df["system"] == "HybridStream").all()
    assert (df["network"] == "N1").all()
