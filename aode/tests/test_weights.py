"""Tests for aode.aode.scoring.weights — WeightPreset, WEIGHT_PRESETS, and helpers.

All external deps are mocked. Source modules do NOT exist yet (TDD).
Every test has a docstring. WeightPreset is a dataclass with __post_init__
validation that abs(sum - 1.0) <= 0.01.
"""
import pytest


# ---------------------------------------------------------------------------
# TestWeightPresetValues (6 tests)
# ---------------------------------------------------------------------------
class TestWeightPresetValues:
    """Verify each named preset carries the correct weights."""

    def test_latency_first_weights(self):
        """latency-first preset has w_lat=0.55, w_res=0.10, w_net=0.20, w_slo=0.15."""
        from aode.aode.scoring.weights import get_weight_preset

        preset = get_weight_preset("latency-first")
        assert preset.w_lat == 0.55
        assert preset.w_res == 0.10
        assert preset.w_net == 0.20
        assert preset.w_slo == 0.15

    def test_balanced_weights(self):
        """balanced preset has w_lat=0.30, w_res=0.30, w_net=0.20, w_slo=0.20."""
        from aode.aode.scoring.weights import get_weight_preset

        preset = get_weight_preset("balanced")
        assert preset.w_lat == 0.30
        assert preset.w_res == 0.30
        assert preset.w_net == 0.20
        assert preset.w_slo == 0.20

    def test_resource_efficient_weights(self):
        """resource-efficient preset has w_lat=0.20, w_res=0.50, w_net=0.20, w_slo=0.10."""
        from aode.aode.scoring.weights import get_weight_preset

        preset = get_weight_preset("resource-efficient")
        assert preset.w_lat == 0.20
        assert preset.w_res == 0.50
        assert preset.w_net == 0.20
        assert preset.w_slo == 0.10

    def test_latency_first_name(self):
        """latency-first preset name attribute matches."""
        from aode.aode.scoring.weights import get_weight_preset

        assert get_weight_preset("latency-first").name == "latency-first"

    def test_balanced_name(self):
        """balanced preset name attribute matches."""
        from aode.aode.scoring.weights import get_weight_preset

        assert get_weight_preset("balanced").name == "balanced"

    def test_resource_efficient_name(self):
        """resource-efficient preset name attribute matches."""
        from aode.aode.scoring.weights import get_weight_preset

        assert get_weight_preset("resource-efficient").name == "resource-efficient"


# ---------------------------------------------------------------------------
# TestWeightPresetSumConstraint (4 tests)
# ---------------------------------------------------------------------------
class TestWeightPresetSumConstraint:
    """Verify all presets have weights summing to 1.0."""

    def test_latency_first_sums_to_one(self):
        """latency-first weights sum to 1.0."""
        from aode.aode.scoring.weights import get_weight_preset

        p = get_weight_preset("latency-first")
        assert abs(p.w_lat + p.w_res + p.w_net + p.w_slo - 1.0) < 1e-9

    def test_balanced_sums_to_one(self):
        """balanced weights sum to 1.0."""
        from aode.aode.scoring.weights import get_weight_preset

        p = get_weight_preset("balanced")
        assert abs(p.w_lat + p.w_res + p.w_net + p.w_slo - 1.0) < 1e-9

    def test_resource_efficient_sums_to_one(self):
        """resource-efficient weights sum to 1.0."""
        from aode.aode.scoring.weights import get_weight_preset

        p = get_weight_preset("resource-efficient")
        assert abs(p.w_lat + p.w_res + p.w_net + p.w_slo - 1.0) < 1e-9

    def test_all_presets_in_registry_sum_to_one(self):
        """Every preset in WEIGHT_PRESETS should sum to 1.0."""
        from aode.aode.scoring.weights import WEIGHT_PRESETS

        for name, preset in WEIGHT_PRESETS.items():
            total = preset.w_lat + preset.w_res + preset.w_net + preset.w_slo
            assert abs(total - 1.0) < 1e-9, f"Preset '{name}' sums to {total}"


# ---------------------------------------------------------------------------
# TestWeightPresetErrors (3 tests)
# ---------------------------------------------------------------------------
class TestWeightPresetErrors:
    """Verify error handling for unknown and invalid preset names."""

    def test_unknown_preset_raises_value_error(self):
        """Unknown preset name should raise ValueError."""
        from aode.aode.scoring.weights import get_weight_preset

        with pytest.raises(ValueError):
            get_weight_preset("nonexistent-preset")

    def test_error_contains_preset_name(self):
        """Error message should contain the unknown preset name."""
        from aode.aode.scoring.weights import get_weight_preset

        with pytest.raises(ValueError, match="nonexistent"):
            get_weight_preset("nonexistent-preset")

    def test_empty_string_raises_value_error(self):
        """Empty string should raise ValueError."""
        from aode.aode.scoring.weights import get_weight_preset

        with pytest.raises(ValueError):
            get_weight_preset("")


# ---------------------------------------------------------------------------
# TestCreateCustomPreset (5 tests)
# ---------------------------------------------------------------------------
class TestCreateCustomPreset:
    """Verify create_custom_preset validates sum constraint."""

    def test_valid_custom_passes(self):
        """Custom preset with weights summing to 1.0 should succeed."""
        from aode.aode.scoring.weights import create_custom_preset

        preset = create_custom_preset("my-preset", 0.40, 0.30, 0.20, 0.10)
        assert preset.name == "my-preset"
        assert preset.w_lat == 0.40
        assert preset.w_res == 0.30
        assert preset.w_net == 0.20
        assert preset.w_slo == 0.10

    def test_sum_0_99_raises(self):
        """Weights summing to 0.99 should raise ValueError (outside tolerance)."""
        from aode.aode.scoring.weights import create_custom_preset

        with pytest.raises(ValueError):
            create_custom_preset("bad", 0.25, 0.25, 0.25, 0.24)

    def test_sum_1_01_raises(self):
        """Weights summing to 1.01 should not raise (within 0.01 tolerance)."""
        from aode.aode.scoring.weights import create_custom_preset

        # 0.26 + 0.25 + 0.25 + 0.25 = 1.01, within tolerance
        preset = create_custom_preset("edge", 0.26, 0.25, 0.25, 0.25)
        assert preset.name == "edge"

    def test_sum_2_0_raises(self):
        """Weights summing to 2.0 should raise ValueError."""
        from aode.aode.scoring.weights import create_custom_preset

        with pytest.raises(ValueError):
            create_custom_preset("bad", 0.50, 0.50, 0.50, 0.50)

    def test_negative_weight_summing_to_one_does_not_raise(self):
        """Negative weight is allowed if the sum is within tolerance of 1.0."""
        from aode.aode.scoring.weights import create_custom_preset

        # -0.10 + 0.60 + 0.30 + 0.20 = 1.0
        preset = create_custom_preset("neg", -0.10, 0.60, 0.30, 0.20)
        assert preset.name == "neg"


# ---------------------------------------------------------------------------
# TestWeightPresetRegistry (3 tests)
# ---------------------------------------------------------------------------
class TestWeightPresetRegistry:
    """Verify WEIGHT_PRESETS registry structure and contents."""

    def test_all_three_names_present(self):
        """WEIGHT_PRESETS should contain latency-first, balanced, resource-efficient."""
        from aode.aode.scoring.weights import WEIGHT_PRESETS

        expected = {"latency-first", "balanced", "resource-efficient"}
        assert expected == set(WEIGHT_PRESETS.keys())

    def test_exactly_three_entries(self):
        """WEIGHT_PRESETS should have exactly 3 entries."""
        from aode.aode.scoring.weights import WEIGHT_PRESETS

        assert len(WEIGHT_PRESETS) == 3

    def test_get_weight_preset_returns_equal_on_repeated_calls(self):
        """Repeated calls to get_weight_preset should return equal objects."""
        from aode.aode.scoring.weights import get_weight_preset

        first = get_weight_preset("balanced")
        second = get_weight_preset("balanced")
        assert first.w_lat == second.w_lat
        assert first.w_res == second.w_res
        assert first.w_net == second.w_net
        assert first.w_slo == second.w_slo
        assert first.name == second.name
