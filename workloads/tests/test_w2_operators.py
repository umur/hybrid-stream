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
