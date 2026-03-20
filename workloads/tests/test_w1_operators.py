import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../hea"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from w1.normalizer  import NormalizerOperator
from w1.aggregator  import FeatureAggWindow
from w1.join        import MultiStreamJoin
from w1.classifier  import BinaryClassifier


@pytest.mark.asyncio
async def test_normalizer_output_format():
    op = NormalizerOperator("norm-1", "zone_1")
    result = await op.process({"sensor_value": 50.0, "timestamp": 0.0})
    assert len(result) == 1
    assert "normalized_value" in result[0]
    assert "zone_id" in result[0]
    assert result[0]["zone_id"] == "zone_1"


@pytest.mark.asyncio
async def test_normalizer_state_roundtrip():
    op = NormalizerOperator("norm-1", "zone_1")
    for i in range(100):
        await op.process({"sensor_value": float(i), "timestamp": float(i)})
    state = op.get_state()
    op2 = NormalizerOperator("norm-1", "zone_1")
    op2.restore_state(state)
    assert abs(op2._mean - op._mean) < 1e-9
    assert op2._count == op._count


@pytest.mark.asyncio
async def test_normalizer_zero_variance_safe():
    op = NormalizerOperator("norm-1", "zone_1")
    # Same value repeatedly — variance stays near 0, should not crash
    for _ in range(10):
        result = await op.process({"sensor_value": 5.0, "timestamp": 0.0})
    assert "normalized_value" in result[0]


@pytest.mark.asyncio
async def test_feature_agg_emits_on_interval():
    op = FeatureAggWindow("agg-1", "zone_1", window_size=1000)
    results = []
    for i in range(200):
        out = await op.process({"normalized_value": float(i), "timestamp": float(i)})
        results.extend(out)
    assert len(results) == 2
    assert "agg_mean" in results[0]
    assert "agg_p95"  in results[0]
    assert "agg_min"  in results[0]
    assert "agg_max"  in results[0]


@pytest.mark.asyncio
async def test_feature_agg_state_roundtrip():
    op = FeatureAggWindow("agg-1", "zone_1")
    for i in range(50):
        await op.process({"normalized_value": float(i), "timestamp": float(i)})
    state = op.get_state()
    op2 = FeatureAggWindow("agg-1", "zone_1")
    op2.restore_state(state)
    assert list(op2._window) == list(op._window)


@pytest.mark.asyncio
async def test_multi_join_emits_when_all_zones_present():
    op = MultiStreamJoin("join-1", n_zones=3, window_timeout_ms=5000.0)
    out1 = await op.process({"zone_id": "zone_1", "agg_mean": 1.0, "agg_max": 2.0, "agg_p95": 1.5})
    out2 = await op.process({"zone_id": "zone_2", "agg_mean": 2.0, "agg_max": 3.0, "agg_p95": 2.5})
    out3 = await op.process({"zone_id": "zone_3", "agg_mean": 3.0, "agg_max": 4.0, "agg_p95": 3.5})
    assert len(out1) == 0
    assert len(out2) == 0
    assert len(out3) == 1
    assert "zone_1_mean" in out3[0]
    assert "zones_present" in out3[0]


@pytest.mark.asyncio
async def test_binary_classifier_above_threshold():
    op = BinaryClassifier("clf-1", threshold=0.5)
    record = {"zone_1_max": 0.8, "zone_2_max": 0.9}
    result = await op.process(record)
    assert result[0]["label"] == 1


@pytest.mark.asyncio
async def test_binary_classifier_below_threshold():
    op = BinaryClassifier("clf-1", threshold=0.9)
    record = {"zone_1_max": 0.1, "zone_2_max": 0.2}
    result = await op.process(record)
    assert result[0]["label"] == 0


@pytest.mark.asyncio
async def test_binary_classifier_state_roundtrip():
    op = BinaryClassifier("clf-1", threshold=0.5)
    state = op.get_state()
    op2 = BinaryClassifier("clf-1")
    op2.restore_state(state)
    assert op2._threshold == 0.5
