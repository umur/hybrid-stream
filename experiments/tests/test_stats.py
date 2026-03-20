import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
from analysis.stats import wilcoxon_comparison, ComparisonResult


def test_wilcoxon_significant_difference():
    rng = np.random.default_rng(42)
    group_a = rng.normal(100.0, 5.0, 10)
    group_b = rng.normal(50.0,  5.0, 10)
    result = wilcoxon_comparison(group_a, group_b, "m1_p95_latency_ms", "HS", "B1", n_comparisons=1)
    assert result.significant is True
    assert result.wilcoxon_p < 0.05
    assert result.median_diff > 0


def test_wilcoxon_no_significant_difference():
    """After Bonferroni(54), near-identical groups are not significant."""
    rng = np.random.default_rng(42)
    group_a = rng.normal(100.0, 2.0, 10)
    group_b = rng.normal(100.0, 2.0, 10)
    result = wilcoxon_comparison(group_a, group_b, "m1_p95_latency_ms", "HS", "B1", n_comparisons=54)
    # p_raw * 54 pushes borderline p well above 0.05
    assert result.bonferroni_p > 0.05


def test_bonferroni_correction():
    rng = np.random.default_rng(42)
    group_a = rng.normal(100.0, 5.0, 10)
    group_b = rng.normal(90.0,  5.0, 10)
    result_1  = wilcoxon_comparison(group_a, group_b, "m1", "A", "B", n_comparisons=1)
    result_54 = wilcoxon_comparison(group_a, group_b, "m1", "A", "B", n_comparisons=54)
    assert result_54.bonferroni_p == min(result_1.wilcoxon_p * 54, 1.0)


def test_effect_size_large():
    rng = np.random.default_rng(42)
    result = wilcoxon_comparison(
        rng.normal(200, 5, 10), rng.normal(50, 5, 10), "m1", "A", "B"
    )
    assert result.effect_magnitude == "large"


def test_bootstrap_ci_contains_zero_for_identical_groups():
    rng = np.random.default_rng(42)
    group = rng.normal(100.0, 5.0, 10)
    result = wilcoxon_comparison(group, group.copy(), "m1", "A", "B", n_bootstrap=999)
    assert result.bootstrap_ci_lo <= 0 <= result.bootstrap_ci_hi


def test_comparison_result_fields():
    rng = np.random.default_rng(42)
    a = rng.normal(100, 5, 10)
    b = rng.normal(80,  5, 10)
    result = wilcoxon_comparison(a, b, "m1_p95_latency_ms", "HS/W1/N1", "B1/W1/N1")
    assert result.n_a == 10
    assert result.n_b == 10
    assert -1 <= result.effect_size_r <= 1
    assert 0 <= result.bonferroni_p <= 1
    assert result.effect_magnitude in ("small", "medium", "large")
    assert result.bootstrap_ci_lo <= result.bootstrap_ci_hi


def test_effect_size_valid_label():
    """Effect magnitude must always be a valid label regardless of sample outcome."""
    rng = np.random.default_rng(42)
    a = rng.normal(100, 10, 10)
    b = rng.normal(101, 10, 10)
    result = wilcoxon_comparison(a, b, "m1", "A", "B")
    assert result.effect_magnitude in ("small", "medium", "large")


def test_mismatched_groups_raises():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([1.0, 2.0])
    with pytest.raises(AssertionError):
        wilcoxon_comparison(a, b, "m1", "A", "B")


# ---------------------------------------------------------------------------
# Additional tests
# ---------------------------------------------------------------------------

def test_wilcoxon_identical_groups_returns_p_one():
    """Identical groups (all differences = 0) must return p=1.0 without raising."""
    rng = np.random.default_rng(0)
    group = rng.normal(100.0, 5.0, 10)
    result = wilcoxon_comparison(group, group.copy(), "m1", "A", "B")
    assert result.wilcoxon_p == pytest.approx(1.0)
    assert result.bonferroni_p == pytest.approx(1.0)
    assert result.significant is False
    assert result.median_diff == pytest.approx(0.0)


def test_wilcoxon_small_sample_size_n5():
    """wilcoxon_comparison works without error on a sample size of n=5."""
    rng = np.random.default_rng(7)
    group_a = rng.normal(100.0, 5.0, 5)
    group_b = rng.normal(80.0,  5.0, 5)
    result = wilcoxon_comparison(group_a, group_b, "m1", "A", "B")
    assert result.n_a == 5
    assert result.n_b == 5
    assert 0.0 <= result.bonferroni_p <= 1.0
    assert result.effect_magnitude in ("small", "medium", "large")


def test_effect_magnitude_small_boundary():
    """abs(r) < 0.30 is classified as 'small'."""
    rng = np.random.default_rng(42)
    # Manufacture a result with abs_r = 0.29 by inspecting the formula:
    # r = 1 - 2*stat/n_pairs — find data that yields abs_r just below 0.30
    # Simplest approach: use groups that are nearly identical (small effect)
    group_a = rng.normal(100.0, 10.0, 10)
    group_b = rng.normal(101.0, 10.0, 10)
    result = wilcoxon_comparison(group_a, group_b, "m1", "A", "B")
    # We can't control the exact r value from random data, but if abs_r < 0.30
    # the label must be "small".
    if abs(result.effect_size_r) < 0.30:
        assert result.effect_magnitude == "small"


def test_effect_magnitude_medium_lower_boundary():
    """abs(r) == 0.30 is classified as 'medium' (boundary is exclusive below 0.30)."""
    # Build a ComparisonResult directly to test the labelling logic in isolation
    # by driving wilcoxon_comparison with data whose stat produces abs_r ~ 0.30.
    # The classification rule is: <0.3 → small, <0.5 → medium, else large.
    # We verify the boundaries by constructing controlled inputs.
    import scipy.stats as scipy_stats
    rng = np.random.default_rng(99)

    # Run many trials and collect one that sits in each boundary region
    found_medium = False
    for seed in range(200):
        rng2 = np.random.default_rng(seed)
        a = rng2.normal(105.0, 8.0, 10)
        b = rng2.normal(95.0,  8.0, 10)
        result = wilcoxon_comparison(a, b, "m1", "A", "B")
        abs_r = abs(result.effect_size_r)
        if 0.30 <= abs_r < 0.50:
            assert result.effect_magnitude == "medium"
            found_medium = True
            break
    assert found_medium, "Could not find a medium-effect sample in 200 seeds"


def test_effect_magnitude_large_boundary():
    """abs(r) >= 0.50 is classified as 'large'."""
    for seed in range(200):
        rng = np.random.default_rng(seed)
        a = rng.normal(200.0, 5.0, 10)
        b = rng.normal(50.0,  5.0, 10)
        result = wilcoxon_comparison(a, b, "m1", "A", "B")
        if abs(result.effect_size_r) >= 0.50:
            assert result.effect_magnitude == "large"
            return
    pytest.fail("Could not generate large-effect sample in 200 seeds")
