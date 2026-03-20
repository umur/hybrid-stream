import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../hea"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from w3.risk       import RiskCheck
from w3.anomaly    import AnomalyDetector
from w3.stat_agg   import StatAggregator
from w3.compliance import ComplianceLogger


@pytest.mark.asyncio
async def test_risk_check_exceeds_limit():
    op = RiskCheck("risk-credit", "credit")
    result = await op.process({"exposure": 99_999_999.0, "timestamp": 0.0})
    assert result[0]["risk_exceeded"] is True
    assert result[0]["breach_count"] == 1


@pytest.mark.asyncio
async def test_risk_check_under_limit():
    op = RiskCheck("risk-credit", "credit")
    result = await op.process({"exposure": 1.0, "timestamp": 0.0})
    assert result[0]["risk_exceeded"] is False
    assert result[0]["breach_count"] == 0


@pytest.mark.asyncio
async def test_risk_check_exposure_ratio():
    op = RiskCheck("risk-operational", "operational")
    result = await op.process({"exposure": 500_000.0, "timestamp": 0.0})
    assert abs(result[0]["exposure_ratio"] - 0.5) < 0.001


@pytest.mark.asyncio
async def test_risk_check_state_roundtrip():
    op = RiskCheck("risk-market", "market")
    await op.process({"exposure": 999.0, "timestamp": 0.0})
    state = op.get_state()
    op2 = RiskCheck("risk-market", "market")
    op2.restore_state(state)
    assert op2._limit == op._limit
    assert op2._breach_count == op._breach_count


@pytest.mark.asyncio
async def test_anomaly_detector_normal_data():
    op = AnomalyDetector("anomaly-1", "price_deviation")
    for v in [100.0, 102.0, 98.0, 101.0, 99.0]:
        result = await op.process({"value": v, "timestamp": 0.0})
    assert result[0]["is_anomaly"] is False


@pytest.mark.asyncio
async def test_anomaly_detector_extreme_outlier():
    # Use z_threshold=1.5 — EWMA drags mean toward outlier so z ≈ 1.79
    op = AnomalyDetector("anomaly-1", "price_deviation", z_threshold=1.5)
    for v in [100.0] * 100:
        await op.process({"value": v, "timestamp": 0.0})
    result = await op.process({"value": 9999.0, "timestamp": 0.0})
    assert result[0]["is_anomaly"] is True
    assert result[0]["z_score"] > 1.5


@pytest.mark.asyncio
async def test_anomaly_detector_state_roundtrip():
    op = AnomalyDetector("anomaly-1", "price_deviation")
    for v in [100.0, 102.0, 98.0]:
        await op.process({"value": v, "timestamp": 0.0})
    state = op.get_state()
    op2 = AnomalyDetector("anomaly-1", "price_deviation")
    op2.restore_state(state)
    assert abs(op2._ewma_mean - op._ewma_mean) < 1e-9


@pytest.mark.asyncio
async def test_stat_aggregator_welford_mean():
    op = StatAggregator("stat-fx", "fx")
    for i in range(1, 11):
        await op.process({"value": float(i), "timestamp": 0.0})
    assert abs(op._mean - 5.5) < 0.001


@pytest.mark.asyncio
async def test_stat_aggregator_emits_every_500():
    op = StatAggregator("stat-fx", "fx")
    results = []
    for i in range(1000):
        out = await op.process({"value": float(i % 100), "timestamp": 0.0})
        results.extend(out)
    assert len(results) == 2  # emits at 500 and 1000


@pytest.mark.asyncio
async def test_stat_aggregator_state_roundtrip():
    op = StatAggregator("stat-fx", "fx")
    for i in range(10):
        await op.process({"value": float(i), "timestamp": 0.0})
    state = op.get_state()
    op2 = StatAggregator("stat-fx", "fx")
    op2.restore_state(state)
    assert op2._count == op._count
    assert abs(op2._mean - op._mean) < 1e-9


@pytest.mark.asyncio
async def test_compliance_logger_sequence():
    op = ComplianceLogger("compliance-aml", "aml")
    for i in range(5):
        await op.process({"event_type": "trade", "timestamp": float(i)})
    state = op.get_state()
    assert state["log_seq"] == 5
    assert state["event_counts"]["trade"] == 5


@pytest.mark.asyncio
async def test_compliance_logger_multiple_event_types():
    op = ComplianceLogger("compliance-sox", "sox")
    await op.process({"event_type": "trade", "timestamp": 1.0})
    await op.process({"event_type": "order", "timestamp": 2.0})
    await op.process({"event_type": "trade", "timestamp": 3.0})
    state = op.get_state()
    assert state["event_counts"]["trade"] == 2
    assert state["event_counts"]["order"] == 1


@pytest.mark.asyncio
async def test_anomaly_detector_zscore_computed_against_previous_mean():
    """z-score must use prev_mean (before the EWMA update), not the updated mean."""
    op = AnomalyDetector("anomaly-2", "price_deviation", z_threshold=100.0)
    # Warm up: drive mean close to 100.0
    for _ in range(200):
        await op.process({"value": 100.0, "timestamp": 0.0})

    prev_mean_before = op._ewma_mean  # should be ~100.0
    result = await op.process({"value": 9999.0, "timestamp": 0.0})

    # If z were computed against the *updated* mean it would be slightly smaller;
    # computed against prev_mean the distance is (9999 - ~100) / std
    z_in_output = result[0]["z_score"]
    std = result[0]["ewma_std"]

    expected_z = abs(9999.0 - prev_mean_before) / std if std > 0 else 0.0
    assert abs(z_in_output - round(expected_z, 4)) < 1e-3


@pytest.mark.asyncio
async def test_anomaly_detector_state_roundtrip_preserves_recent_zscores_deque():
    """recent_zscores must be restored as a deque with maxlen=100."""
    import collections
    op = AnomalyDetector("anomaly-3", "vol_surface")
    for v in [100.0, 102.0, 98.0, 105.0, 95.0]:
        await op.process({"value": v, "timestamp": 0.0})

    state = op.get_state()
    op2 = AnomalyDetector("anomaly-3", "vol_surface")
    op2.restore_state(state)

    assert isinstance(op2._recent_zscores, collections.deque)
    assert op2._recent_zscores.maxlen == 100
    assert list(op2._recent_zscores) == list(op._recent_zscores)


@pytest.mark.asyncio
async def test_risk_check_negative_exposure_clamped_to_zero():
    """A negative exposure value must be clamped to 0 and not exceed the limit."""
    op = RiskCheck("risk-settlement", "settlement")
    result = await op.process({"exposure": -500_000.0, "timestamp": 0.0})

    assert result[0]["exposure"] == 0.0
    assert result[0]["risk_exceeded"] is False
    assert result[0]["exposure_ratio"] == 0.0
    assert result[0]["breach_count"] == 0


@pytest.mark.asyncio
async def test_risk_check_state_roundtrip_is_lossless():
    """get_state → restore_state must reproduce identical processing behaviour."""
    op = RiskCheck("risk-model", "model")
    # Create some state: process a few records, one of which breaches
    await op.process({"exposure": 500_000.0, "timestamp": 0.0})
    await op.process({"exposure": 2_000_000.0, "timestamp": 1.0})  # exceeds model limit 1.5M

    state = op.get_state()
    op2 = RiskCheck("risk-model", "model")
    op2.restore_state(state)

    assert op2._limit == op._limit
    assert op2._breach_count == op._breach_count
    assert op2._total_checked == op._total_checked
    assert op2._risk_category == op._risk_category

    # Verify continued behaviour is identical
    r1 = await op.process({"exposure": 750_000.0, "timestamp": 2.0})
    r2 = await op2.process({"exposure": 750_000.0, "timestamp": 2.0})
    assert r1[0]["risk_exceeded"] == r2[0]["risk_exceeded"]
    assert r1[0]["breach_count"] == r2[0]["breach_count"]
    assert abs(r1[0]["exposure_ratio"] - r2[0]["exposure_ratio"]) < 1e-9


@pytest.mark.asyncio
async def test_risk_check_zero_limit_from_corrupted_state_returns_zero_ratio():
    """When _limit is restored as 0 (corrupted state), exposure_ratio must be 0.0."""
    op = RiskCheck("risk-liquidity", "liquidity")
    # Corrupt the state: set limit to 0
    op.restore_state({
        "risk_category": "liquidity",
        "limit": 0.0,
        "breach_count": 0,
        "total_checked": 0,
    })

    result = await op.process({"exposure": 500_000.0, "timestamp": 0.0})
    # exposure / limit would be division by zero — must fall back to 0.0
    assert result[0]["exposure_ratio"] == 0.0


@pytest.mark.asyncio
async def test_compliance_logger_state_roundtrip():
    op = ComplianceLogger("compliance-gdpr", "gdpr")
    for i in range(3):
        await op.process({"event_type": "data_access", "timestamp": float(i)})
    state = op.get_state()
    op2 = ComplianceLogger("compliance-gdpr", "gdpr")
    op2.restore_state(state)
    assert op2._log_seq == op._log_seq
    assert op2._event_counts == op._event_counts
