"""Tests for aode.aode.scoring.algorithm — ScoringAlgorithm and find_optimal_placement.

All external deps are mocked. Source modules do NOT exist yet (TDD).
Every test has a docstring. Uses numpy (importorskip) and unittest.mock.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

np = pytest.importorskip("numpy")


# ---------------------------------------------------------------------------
# Mock helper
# ---------------------------------------------------------------------------
def _mock_telemetry(cpu=0.5, mem=0.5, rtt_ms=10.0, operator_p95=None, reachable_heas=None):
    """Create a mock TelemetryCollector with preset return values."""
    mock = MagicMock()
    mock.get_tier_utilization.return_value = (cpu, mem)
    mock.get_operator_latency.side_effect = lambda op: (operator_p95 or {}).get(op)

    tel_map = {}
    for hea_id in (reachable_heas or []):
        tel_map[hea_id] = SimpleNamespace(
            hea_id=hea_id,
            cpu_utilization=cpu,
            memory_utilization=mem,
            rtt_ms=rtt_ms,
            reachable=True,
        )
    mock.get_latest_telemetry.return_value = tel_map
    return mock


# ---------------------------------------------------------------------------
# TestComputeScoresShape (3 tests)
# ---------------------------------------------------------------------------
class TestComputeScoresShape:
    """Verify compute_scores returns ndarray with correct shape."""

    def test_shape_3x2(self):
        """3 operators x 2 tiers should produce (3, 2) array."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry()
        scorer = ScoringAlgorithm(config, telemetry)

        operators = ["op-a", "op-b", "op-c"]
        tiers = ["edge-1", "cloud"]
        slo_map = {"op-a": 20.0, "op-b": 50.0, "op-c": 100.0}
        lambda_map = {"op-a": "critical", "op-b": "standard", "op-c": "batch"}

        scores = scorer.compute_scores(operators, tiers, slo_map, lambda_map)
        assert isinstance(scores, np.ndarray)
        assert scores.shape == (3, 2)

    def test_shape_1x1(self):
        """1 operator x 1 tier should produce (1, 1) array."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry()
        scorer = ScoringAlgorithm(config, telemetry)

        scores = scorer.compute_scores(
            ["op-a"], ["edge-1"], {"op-a": 50.0}, {"op-a": "standard"}
        )
        assert scores.shape == (1, 1)

    def test_shape_4x5_w1_workload(self):
        """4 operators x 5 tiers (W1 workload) should produce (4, 5) array."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        tiers = ["edge-1", "edge-2", "edge-3", "edge-4", "cloud"]
        telemetry = _mock_telemetry(reachable_heas=tiers)
        scorer = ScoringAlgorithm(config, telemetry)

        operators = ["op-a", "op-b", "op-c", "op-d"]
        slo_map = {op: 100.0 for op in operators}
        lambda_map = {op: "standard" for op in operators}

        scores = scorer.compute_scores(operators, tiers, slo_map, lambda_map)
        assert scores.shape == (4, 5)


# ---------------------------------------------------------------------------
# TestComputeScoresValues (2 tests)
# ---------------------------------------------------------------------------
class TestComputeScoresValues:
    """Verify computed score values are valid."""

    def test_all_values_non_negative(self):
        """All scores in the matrix should be >= 0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 5.0, "op-b": 10.0})
        scorer = ScoringAlgorithm(config, telemetry)

        scores = scorer.compute_scores(
            ["op-a", "op-b"],
            ["edge-1", "cloud"],
            {"op-a": 50.0, "op-b": 100.0},
            {"op-a": "critical", "op-b": "standard"},
        )
        assert np.all(scores >= 0.0)

    def test_scores_are_float(self):
        """Score array dtype should be a float type."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry()
        scorer = ScoringAlgorithm(config, telemetry)

        scores = scorer.compute_scores(
            ["op-a"], ["edge-1"], {"op-a": 50.0}, {"op-a": "standard"}
        )
        assert np.issubdtype(scores.dtype, np.floating)

    def test_critical_scores_differ_from_batch(self):
        """Critical and batch lambda classes should produce different scores."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 10.0})
        scorer = ScoringAlgorithm(config, telemetry)

        scores_critical = scorer.compute_scores(
            ["op-a"], ["edge-1"], {"op-a": 50.0}, {"op-a": "critical"}
        )
        scores_batch = scorer.compute_scores(
            ["op-a"], ["edge-1"], {"op-a": 50.0}, {"op-a": "batch"}
        )
        assert scores_critical[0, 0] != scores_batch[0, 0]

    def test_higher_utilization_increases_score(self):
        """Higher resource utilization should increase the total score."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        tel_low = _mock_telemetry(cpu=0.2, mem=0.2)
        tel_high = _mock_telemetry(cpu=0.8, mem=0.8)

        scorer_low = ScoringAlgorithm(config, tel_low)
        scorer_high = ScoringAlgorithm(config, tel_high)

        s_low = scorer_low.compute_scores(
            ["op-a"], ["edge-1"], {"op-a": 100.0}, {"op-a": "standard"}
        )
        s_high = scorer_high.compute_scores(
            ["op-a"], ["edge-1"], {"op-a": 100.0}, {"op-a": "standard"}
        )
        assert s_high[0, 0] > s_low[0, 0]

    def test_slo_violation_increases_score(self):
        """An SLO violation should increase the total score vs no violation."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        tel_ok = _mock_telemetry(operator_p95={"op-a": 5.0})
        tel_bad = _mock_telemetry(operator_p95={"op-a": 50.0})

        scorer_ok = ScoringAlgorithm(config, tel_ok)
        scorer_bad = ScoringAlgorithm(config, tel_bad)

        s_ok = scorer_ok.compute_scores(
            ["op-a"], ["edge-1"], {"op-a": 20.0}, {"op-a": "standard"}
        )
        s_bad = scorer_bad.compute_scores(
            ["op-a"], ["edge-1"], {"op-a": 20.0}, {"op-a": "standard"}
        )
        assert s_bad[0, 0] > s_ok[0, 0]

    def test_cloud_tier_has_zero_network_cost_in_scores(self):
        """Cloud tier should contribute 0 network cost to the total score."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(rtt_ms=100.0, reachable_heas=["edge-1"])
        scorer = ScoringAlgorithm(config, telemetry)

        scores = scorer.compute_scores(
            ["op-a"], ["edge-1", "cloud"], {"op-a": 1000.0}, {"op-a": "standard"}
        )
        # Cloud (index 1) should have lower score than edge with 100ms RTT
        assert scores[0, 1] < scores[0, 0]


# ---------------------------------------------------------------------------
# TestPhiRes (6 tests)
# ---------------------------------------------------------------------------
class TestPhiRes:
    """Verify phi_res follows kappa * rho / (1 - rho) curve."""

    def test_rho_zero_gives_zero(self):
        """rho=0.0 should produce phi_res=0.0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(cpu=0.0, mem=0.0)
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_res("edge-1")
        assert abs(result - 0.0) < 1e-6

    def test_rho_0_5_gives_2_0(self):
        """rho=0.5 -> kappa*0.5/(1-0.5) = 2.0*0.5/0.5 = 2.0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(cpu=0.5, mem=0.5)
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_res("edge-1")
        assert abs(result - 2.0) < 1e-6

    def test_rho_0_8_gives_8_0(self):
        """rho=0.8 -> kappa*0.8/(1-0.8) = 2.0*0.8/0.2 = 8.0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(cpu=0.8, mem=0.7)
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_res("edge-1")
        assert abs(result - 8.0) < 1e-6

    def test_rho_0_1_gives_correct_value(self):
        """rho=0.1 -> kappa*0.1/0.9 = 2.0*0.1/0.9."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(cpu=0.1, mem=0.1)
        scorer = ScoringAlgorithm(config, telemetry)

        expected = 2.0 * 0.1 / 0.9
        result = scorer._compute_phi_res("edge-1")
        assert abs(result - expected) < 1e-6

    def test_rho_0_99_capped_large_but_finite(self):
        """rho=0.99 should produce a large but finite value (capped at 0.99)."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(cpu=0.99, mem=0.99)
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_res("edge-1")
        expected = 2.0 * 0.99 / 0.01  # 198.0
        assert abs(result - expected) < 1e-3
        assert result < float("inf")

    def test_rho_1_0_capped_at_0_99(self):
        """rho=1.0 should be capped at 0.99 internally, yielding 198.0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(cpu=1.0, mem=1.0)
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_res("edge-1")
        expected = 2.0 * 0.99 / 0.01  # 198.0
        assert abs(result - expected) < 1e-3


# ---------------------------------------------------------------------------
# TestPhiLat (4 tests)
# ---------------------------------------------------------------------------
class TestPhiLat:
    """Verify lambda-class weighting: critical=3.0, standard=1.0, batch=0.1."""

    def test_critical_greater_than_standard_greater_than_batch(self):
        """critical > standard > batch for the same operator and tier."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 5.0})
        scorer = ScoringAlgorithm(config, telemetry)

        critical = scorer._compute_phi_lat("op-a", "edge-1", "critical")
        standard = scorer._compute_phi_lat("op-a", "edge-1", "standard")
        batch = scorer._compute_phi_lat("op-a", "edge-1", "batch")

        assert critical > standard > batch

    def test_critical_multiplier_is_3_0(self):
        """critical / standard ratio should be 3.0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 5.0})
        scorer = ScoringAlgorithm(config, telemetry)

        critical = scorer._compute_phi_lat("op-a", "edge-1", "critical")
        standard = scorer._compute_phi_lat("op-a", "edge-1", "standard")

        assert abs(critical / standard - 3.0) < 1e-6

    def test_standard_multiplier_is_1_0(self):
        """standard / batch ratio should be 10.0 (1.0 / 0.1)."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 5.0})
        scorer = ScoringAlgorithm(config, telemetry)

        standard = scorer._compute_phi_lat("op-a", "edge-1", "standard")
        batch = scorer._compute_phi_lat("op-a", "edge-1", "batch")

        assert abs(standard / batch - 10.0) < 1e-6

    def test_batch_multiplier_is_0_1(self):
        """batch weight is 0.1 so batch = 0.1 * observed_latency."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 10.0})
        scorer = ScoringAlgorithm(config, telemetry)

        batch = scorer._compute_phi_lat("op-a", "edge-1", "batch")
        # batch = 0.1 * 10.0 = 1.0
        assert abs(batch - 1.0) < 1e-6

    def test_unknown_operator_uses_default_latency(self):
        """Unknown operator (no p95 data) should use 1.0 as default observed latency."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={})
        scorer = ScoringAlgorithm(config, telemetry)

        # standard weight=1.0, default observed=1.0 -> 1.0 * 1.0 = 1.0
        result = scorer._compute_phi_lat("unknown-op", "edge-1", "standard")
        assert abs(result - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# TestPhiNet (3 tests)
# ---------------------------------------------------------------------------
class TestPhiNet:
    """Verify network cost: 0 for cloud, rtt_ms for edge, 1000 if unreachable."""

    def test_cloud_returns_zero(self):
        """Cloud tier should always return 0.0 network cost."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(rtt_ms=15.0)
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_net("cloud")
        assert result == 0.0

    def test_edge_returns_rtt_ms(self):
        """Edge tier should return the observed rtt_ms."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(rtt_ms=15.0, reachable_heas=["edge-1"])
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_net("edge-1")
        assert result == 15.0

    def test_unreachable_returns_1000(self):
        """Unreachable tier should return 1000.0 network cost."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        # No reachable HEAs — edge-unreachable is not in the telemetry map
        telemetry = _mock_telemetry(rtt_ms=10.0, reachable_heas=[])
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_net("edge-unreachable")
        assert result == 1000.0


# ---------------------------------------------------------------------------
# TestPhiSlo (7 tests)
# ---------------------------------------------------------------------------
class TestPhiSlo:
    """Verify SLO penalty: 0 when no violation, M*(observed-slo)/slo when violated."""

    def test_no_violation_returns_zero(self):
        """Observed < SLO should return 0.0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 8.0})
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_slo("op-a", "edge-1", 20.0)
        assert result == 0.0

    def test_exact_at_slo_returns_zero(self):
        """Observed == SLO should return 0.0 (no violation)."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 20.0})
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_slo("op-a", "edge-1", 20.0)
        assert result == 0.0

    def test_1ms_above_slo(self):
        """1ms above SLO gives M * (1 / slo)."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 21.0})
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_slo("op-a", "edge-1", 20.0)
        expected = 10 * (21.0 - 20.0) / 20.0  # 10 * 0.05 = 0.5
        assert abs(result - expected) < 1e-6

    def test_2x_slo_gives_m_times_1(self):
        """Observed = 2*SLO gives M * (slo / slo) = M * 1.0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 40.0})
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_slo("op-a", "edge-1", 20.0)
        expected = 10 * (40.0 - 20.0) / 20.0  # 10 * 1.0 = 10.0
        assert abs(result - expected) < 1e-6

    def test_3x_slo_gives_m_times_2(self):
        """Observed = 3*SLO gives M * (2*slo / slo) = M * 2.0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(operator_p95={"op-a": 60.0})
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_slo("op-a", "edge-1", 20.0)
        expected = 10 * (60.0 - 20.0) / 20.0  # 10 * 2.0 = 20.0
        assert abs(result - expected) < 1e-6

    def test_none_slo_uses_3600s_nominal(self):
        """slo_ms=None (batch) should use 3600000ms as nominal SLO."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        # observed = 5.0, nominal SLO = 3600000 -> no violation
        telemetry = _mock_telemetry(operator_p95={"op-a": 5.0})
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_slo("op-a", "edge-1", None)
        assert result == 0.0

    def test_violation_is_continuous_not_binary(self):
        """Penalty should scale continuously with the degree of violation."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry_small = _mock_telemetry(operator_p95={"op-a": 25.0})
        telemetry_large = _mock_telemetry(operator_p95={"op-a": 50.0})

        scorer_small = ScoringAlgorithm(config, telemetry_small)
        scorer_large = ScoringAlgorithm(config, telemetry_large)

        result_small = scorer_small._compute_phi_slo("op-a", "edge-1", 20.0)
        result_large = scorer_large._compute_phi_slo("op-a", "edge-1", 20.0)

        assert result_large > result_small > 0.0


# ---------------------------------------------------------------------------
# TestFindOptimalPlacement (5 tests)
# ---------------------------------------------------------------------------
class TestFindOptimalPlacement:
    """Verify find_optimal_placement returns valid operator-to-tier mapping."""

    def test_returns_all_operators(self):
        """Every operator should appear in the placement dict."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm, find_optimal_placement

        config = AODEConfig()
        telemetry = _mock_telemetry(cpu=0.3, mem=0.3, rtt_ms=5.0)
        scorer = ScoringAlgorithm(config, telemetry)

        operators = ["op-a", "op-b"]
        tiers = ["edge-1", "cloud"]
        slo_map = {"op-a": 50.0, "op-b": 100.0}
        lambda_map = {"op-a": "critical", "op-b": "batch"}

        scores = scorer.compute_scores(operators, tiers, slo_map, lambda_map)
        placement = find_optimal_placement(
            scores, operators, tiers, {"edge-1": 5, "cloud": 100}
        )
        assert set(placement.keys()) == {"op-a", "op-b"}

    def test_respects_tier_capacities(self):
        """Operators should not exceed tier capacity limits."""
        from aode.aode.scoring.algorithm import find_optimal_placement

        # 3 operators, tier-0 capacity=1 -> at most 1 in tier-0
        scores = np.array([[1.0, 5.0], [1.0, 5.0], [1.0, 5.0]])
        operators = ["op-a", "op-b", "op-c"]
        tiers = ["edge-1", "cloud"]
        tier_capacities = {"edge-1": 1, "cloud": 100}

        placement = find_optimal_placement(scores, operators, tiers, tier_capacities)
        edge_count = sum(1 for t in placement.values() if t == "edge-1")
        assert edge_count <= 1

    def test_fallback_to_cloud(self):
        """When edge capacity is 0, all operators go to cloud."""
        from aode.aode.scoring.algorithm import find_optimal_placement

        scores = np.array([[1.0, 2.0], [1.0, 2.0]])
        operators = ["op-a", "op-b"]
        tiers = ["edge-1", "cloud"]
        tier_capacities = {"edge-1": 0, "cloud": 100}

        placement = find_optimal_placement(scores, operators, tiers, tier_capacities)
        for op in operators:
            assert placement[op] == "cloud"

    def test_assigns_lowest_cost_tier(self):
        """Each operator should be assigned to its lowest-cost tier."""
        from aode.aode.scoring.algorithm import find_optimal_placement

        # op-a prefers tier 0 (edge-1), op-b prefers tier 1 (cloud)
        scores = np.array([[1.0, 10.0], [10.0, 1.0]])
        operators = ["op-a", "op-b"]
        tiers = ["edge-1", "cloud"]
        tier_capacities = {"edge-1": 5, "cloud": 5}

        placement = find_optimal_placement(scores, operators, tiers, tier_capacities)
        assert placement["op-a"] == "edge-1"
        assert placement["op-b"] == "cloud"

    def test_full_w1_workload_4x5_shape(self):
        """W1 workload: 4 operators across 5 tiers should all be placed."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm, find_optimal_placement

        config = AODEConfig()
        tiers = ["edge-1", "edge-2", "edge-3", "edge-4", "cloud"]
        telemetry = _mock_telemetry(cpu=0.3, mem=0.3, rtt_ms=5.0, reachable_heas=tiers)
        scorer = ScoringAlgorithm(config, telemetry)

        operators = ["op-a", "op-b", "op-c", "op-d"]
        slo_map = {op: 100.0 for op in operators}
        lambda_map = {"op-a": "critical", "op-b": "critical", "op-c": "standard", "op-d": "batch"}

        scores = scorer.compute_scores(operators, tiers, slo_map, lambda_map)
        tier_capacities = {t: 5 for t in tiers}
        placement = find_optimal_placement(scores, operators, tiers, tier_capacities)

        assert set(placement.keys()) == set(operators)
        for tier in placement.values():
            assert tier in tiers


# ---------------------------------------------------------------------------
# TestScoringEdgeCases (5 tests) — edge-case inputs
# ---------------------------------------------------------------------------
class TestScoringEdgeCases:
    """Verify scoring algorithm handles degenerate and edge-case inputs correctly."""

    def test_all_zero_weights_produce_zero_scores(self):
        """All-zero weights should produce an all-zero score matrix."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm
        from aode.aode.scoring.weights import create_custom_preset

        config = AODEConfig()
        telemetry = _mock_telemetry(cpu=0.5, mem=0.5, rtt_ms=10.0)
        scorer = ScoringAlgorithm(config, telemetry)
        # Inject a zero-weight preset directly (bypassing sum validation via negative trick)
        # We patch the weights directly on the scorer instance.
        from aode.aode.scoring.weights import WeightPreset
        scorer._weights = WeightPreset.__new__(WeightPreset)
        scorer._weights.name = "zero"
        scorer._weights.w_lat = 0.0
        scorer._weights.w_res = 0.0
        scorer._weights.w_net = 0.0
        scorer._weights.w_slo = 0.0

        scores = scorer.compute_scores(
            ["op-a"], ["edge-1"], {"op-a": 50.0}, {"op-a": "standard"}
        )
        assert np.all(scores == 0.0)

    def test_negative_rho_clamped_to_zero_by_max_cpu_mem(self):
        """Negative telemetry values: rho is max(cpu, mem) — max(-0.1, -0.2) = -0.1,
        which is < 0.99 cap, so the formula runs without error and returns a finite value."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        telemetry = _mock_telemetry(cpu=-0.1, mem=-0.2)
        scorer = ScoringAlgorithm(config, telemetry)

        # Should not raise; result is finite (negative rho still < 0.99 cap)
        result = scorer._compute_phi_res("edge-1")
        assert result < float("inf")
        assert result == result  # not NaN

    def test_phi_res_rho_exactly_0_99_cap(self):
        """When rho exactly equals the 0.99 cap the formula yields kappa*0.99/0.01 = 198.0."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        # cpu=0.99 so rho=0.99, which equals the cap — no further clamping needed.
        telemetry = _mock_telemetry(cpu=0.99, mem=0.0)
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_res("edge-1")
        expected = 2.0 * 0.99 / (1.0 - 0.99)  # 198.0
        assert abs(result - expected) < 1e-3

    def test_phi_slo_with_extremely_small_slo(self):
        """SLO of 0.001 ms with observed latency 1.0 ms should produce a very large penalty."""
        from aode.aode.config import AODEConfig
        from aode.aode.scoring.algorithm import ScoringAlgorithm

        config = AODEConfig()
        # observed = 1.0ms (default when p95 is missing), slo = 0.001ms
        telemetry = _mock_telemetry(operator_p95={"op-a": 1.0})
        scorer = ScoringAlgorithm(config, telemetry)

        result = scorer._compute_phi_slo("op-a", "edge-1", 0.001)
        # penalty = M * (1.0 - 0.001) / 0.001 = 10 * 999 = 9990.0
        expected = 10 * (1.0 - 0.001) / 0.001
        assert abs(result - expected) < 1e-3

    def test_find_optimal_placement_all_tiers_at_capacity_falls_back_to_cloud(self):
        """When all non-cloud tiers are at capacity=0, every operator lands on cloud."""
        from aode.aode.scoring.algorithm import find_optimal_placement

        scores = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        operators = ["op-a", "op-b"]
        tiers = ["edge-1", "edge-2", "cloud"]
        # Edge tiers at capacity 0, cloud has unlimited room.
        tier_capacities = {"edge-1": 0, "edge-2": 0, "cloud": 100}

        placement = find_optimal_placement(scores, operators, tiers, tier_capacities)

        for op in operators:
            assert placement[op] == "cloud"
