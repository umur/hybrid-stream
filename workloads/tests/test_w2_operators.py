import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../hea"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from w2.detector  import VehicleDetector
from w2.zone_agg  import ZoneAggregator
from w2.pattern   import PatternDetector


@pytest.mark.asyncio
async def test_vehicle_detector_detects():
    op = VehicleDetector("det-0", "sensor_0000")
    # Feed enough events to push EWMA above threshold
    for _ in range(20):
        result = await op.process({"occupancy": 0.9, "speed_kmh": 80.0, "timestamp": 0.0})
    assert result[0]["vehicle_detected"] is True
    assert result[0]["ewma_occupancy"] > 0.15


@pytest.mark.asyncio
async def test_vehicle_detector_no_detection():
    op = VehicleDetector("det-0", "sensor_0000")
    result = await op.process({"occupancy": 0.0, "speed_kmh": 0.0, "timestamp": 0.0})
    assert result[0]["vehicle_detected"] is False


@pytest.mark.asyncio
async def test_vehicle_detector_state_roundtrip():
    op = VehicleDetector("det-0", "sensor_0000")
    for _ in range(10):
        await op.process({"occupancy": 0.5, "speed_kmh": 60.0, "timestamp": 1.0})
    state = op.get_state()
    op2 = VehicleDetector("det-0", "sensor_0000")
    op2.restore_state(state)
    assert abs(op2._ewma_occ - op._ewma_occ) < 1e-9
    assert op2._detection_count == op._detection_count


@pytest.mark.asyncio
async def test_zone_agg_no_emit_before_interval():
    op = ZoneAggregator("agg-zone_01", "zone_01")
    results = []
    for i in range(10):
        out = await op.process({
            "sensor_id": f"sensor_{i:04d}",
            "vehicle_detected": True,
            "timestamp": 0.0,
        })
        results.extend(out)
    # emit_interval is 5s — no time has passed in test
    assert len(results) == 0
    assert op._zone_total == 10


@pytest.mark.asyncio
async def test_zone_agg_state_roundtrip():
    op = ZoneAggregator("agg-zone_01", "zone_01")
    for i in range(5):
        await op.process({"sensor_id": f"sensor_{i}", "vehicle_detected": True})
    state = op.get_state()
    op2 = ZoneAggregator("agg-zone_01", "zone_01")
    op2.restore_state(state)
    assert op2._zone_total == op._zone_total
    assert op2._sensor_counts == op._sensor_counts


@pytest.mark.asyncio
async def test_pattern_detector_triggers_on_3_congested_zones():
    op = PatternDetector("pd-1", congestion_threshold=0.5)
    # Feed 3 zones with high density
    for zone in ["zone_01", "zone_02", "zone_03"]:
        result = await op.process({"zone_id": zone, "density": 0.9, "timestamp": 0.0})
    assert len(result) == 1
    assert result[0]["pattern_type"] == "congestion_wave"
    assert result[0]["severity"] >= 3


@pytest.mark.asyncio
async def test_pattern_detector_no_trigger_below_threshold():
    op = PatternDetector("pd-1", congestion_threshold=0.8)
    for zone in ["zone_01", "zone_02"]:
        result = await op.process({"zone_id": zone, "density": 0.9, "timestamp": 0.0})
    # Only 2 zones, need >= 3
    assert len(result) == 0


@pytest.mark.asyncio
async def test_pattern_detector_state_roundtrip():
    op = PatternDetector("pd-1")
    await op.process({"zone_id": "zone_01", "density": 0.5, "timestamp": 0.0})
    state = op.get_state()
    op2 = PatternDetector("pd-1")
    op2.restore_state(state)
    assert "zone_01" in op2._zone_history


# ---------------------------------------------------------------------------
# ZoneAggregator — emit after timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zone_agg_emits_after_timeout():
    """Advancing time past emit_interval triggers an emit on the next record."""
    from unittest.mock import patch

    op = ZoneAggregator("agg-zone_02", "zone_02")

    # Freeze initial time so _last_emit_ts is set to t0
    t0 = 1000.0
    with patch("w2.zone_agg.time") as mock_time:
        mock_time.monotonic.return_value = t0
        mock_time.time.return_value = t0
        # Build internal state: _last_emit_ts = t0
        op._last_emit_ts = t0

        # Advance monotonic clock past emit_interval (5 s)
        mock_time.monotonic.return_value = t0 + 6.0
        mock_time.time.return_value = t0 + 6.0

        result = await op.process({
            "sensor_id": "sensor_0000",
            "vehicle_detected": True,
            "timestamp": t0 + 6.0,
        })

    assert len(result) == 1
    assert result[0]["zone_id"] == "zone_02"
    assert "total_detections" in result[0]
    assert "density" in result[0]


# ---------------------------------------------------------------------------
# ZoneAggregator — state roundtrip type preservation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zone_agg_state_roundtrip_preserves_sensor_counts_types():
    """After restore_state, sensor_counts must have str keys and int values."""
    op = ZoneAggregator("agg-zone_03", "zone_03")
    for i in range(3):
        await op.process({
            "sensor_id": f"sensor_{i:04d}",
            "vehicle_detected": True,
        })

    state = op.get_state()
    # Simulate serialisation round-trip that might coerce keys (e.g. JSON)
    state["sensor_counts"] = {str(k): int(v) for k, v in state["sensor_counts"].items()}

    op2 = ZoneAggregator("agg-zone_03", "zone_03")
    op2.restore_state(state)

    for key, val in op2._sensor_counts.items():
        assert isinstance(key, str), f"Expected str key, got {type(key)}"
        assert isinstance(val, int), f"Expected int value, got {type(val)}"


# ---------------------------------------------------------------------------
# PatternDetector — state roundtrip preserves deques with correct maxlen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pattern_detector_state_roundtrip_preserves_zone_history_deques():
    """zone_history entries must be deques with maxlen=20 after restore_state."""
    import collections
    op = PatternDetector("pd-2")
    for density in [0.3, 0.6, 0.9]:
        await op.process({"zone_id": "zone_05", "density": density, "timestamp": 0.0})

    state = op.get_state()
    op2 = PatternDetector("pd-2")
    op2.restore_state(state)

    hist = op2._zone_history["zone_05"]
    assert isinstance(hist, collections.deque)
    assert hist.maxlen == 20
    assert list(hist) == [0.3, 0.6, 0.9]


# ---------------------------------------------------------------------------
# PatternDetector — congestion trigger boundary conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pattern_detector_exactly_3_congested_zones_triggers_incident():
    """Exactly 3 zones above threshold must produce exactly one incident record."""
    op = PatternDetector("pd-3", congestion_threshold=0.5)
    results = []
    for zone in ["zone_A", "zone_B", "zone_C"]:
        out = await op.process({"zone_id": zone, "density": 0.8, "timestamp": 0.0})
        results.extend(out)

    assert len(results) == 1
    assert results[0]["pattern_type"] == "congestion_wave"
    assert results[0]["severity"] == 3


@pytest.mark.asyncio
async def test_pattern_detector_exactly_2_congested_zones_does_not_trigger():
    """Exactly 2 zones above threshold must NOT emit an incident."""
    op = PatternDetector("pd-4", congestion_threshold=0.5)
    results = []
    for zone in ["zone_X", "zone_Y"]:
        out = await op.process({"zone_id": zone, "density": 0.9, "timestamp": 0.0})
        results.extend(out)

    assert len(results) == 0
