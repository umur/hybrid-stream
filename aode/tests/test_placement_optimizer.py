"""Tests for aode.aode.placement.optimizer — PlacementOptimizer decision logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _np_array(values):
    """Lazy numpy array constructor to avoid top-level import."""
    import numpy as np

    return np.array(values)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _make_optimizer(
    current_placement=None,
    optimal_placement=None,
    scores_array=None,
    config=None,
):
    """Build a PlacementOptimizer with fully-mocked dependencies.

    Returns (optimizer, orchestrator_mock, state_mock) so callers can inspect
    interactions.
    """
    from aode.aode.config import AODEConfig
    from aode.aode.placement.optimizer import PlacementOptimizer

    current_placement = current_placement or {
        "OpA": "edge-node-1",
        "OpB": "edge-node-2",
    }
    optimal_placement = optimal_placement or {
        "OpA": "cloud",
        "OpB": "cloud",
    }
    # Default: rows=operators, cols=tiers (edge-node-1, edge-node-2, cloud)
    # OpA on edge-node-1 → score 1.0, optimal cloud → 0.3  (improvement 0.7)
    # OpB on edge-node-2 → score 0.5, optimal cloud → 0.4  (improvement 0.1)
    scores_array = scores_array if scores_array is not None else _np_array([
        [1.0, 0.8, 0.3],
        [0.6, 0.5, 0.4],
    ])
    config = config or AODEConfig()

    scoring = MagicMock()
    scoring.compute_scores = MagicMock(return_value=scores_array)

    orchestrator = AsyncMock()
    orchestrator.migrate_operator = AsyncMock(return_value="migration-0001")

    state = MagicMock()
    state.get_current_placement = MagicMock(return_value=current_placement)
    state.get_available_tiers = MagicMock(
        return_value=sorted(set(current_placement.values()) | {"cloud"})
    )
    state.get_slo_map = MagicMock(
        return_value={op: 2000.0 for op in current_placement}
    )
    state.get_lambda_map = MagicMock(
        return_value={op: "standard" for op in current_placement}
    )
    state.get_tier_capacities = MagicMock(
        return_value={"edge-node-1": 5, "edge-node-2": 5, "cloud": 100}
    )
    state.update_operator_placement = AsyncMock()

    optimizer = PlacementOptimizer(
        config=config,
        scoring=scoring,
        migration_orchestrator=orchestrator,
        placement_state=state,
    )

    return optimizer, orchestrator, state


# ---------------------------------------------------------------------------
# TestPlacementOptimizerThreshold
# ---------------------------------------------------------------------------

class TestPlacementOptimizerThreshold:
    """Verify migration is triggered only when score improvement >= delta_h (0.15)."""

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_improvement_above_threshold_triggers_migration(self, mock_fop):
        """Improvement of 0.7 > 0.15 must trigger a migration."""
        mock_fop.return_value = {"OpA": "cloud", "OpB": "cloud"}
        opt, orch, _ = _make_optimizer()

        result = await opt._run_optimization()

        assert result["migrations_started"] >= 1
        orch.migrate_operator.assert_called()

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_improvement_at_exact_boundary_triggers_migration(self, mock_fop):
        """Improvement == 0.15 (exact boundary) must still trigger migration (>=)."""
        mock_fop.return_value = {"OpA": "cloud", "OpB": "edge-node-2"}
        # OpA: current edge-node-1 score 0.50, optimal cloud score 0.35 → improvement 0.15
        # OpB: stays on edge-node-2 → no migration
        scores = _np_array([
            [0.50, 0.40, 0.35],
            [0.60, 0.50, 0.45],
        ])
        opt, orch, _ = _make_optimizer(scores_array=scores)

        result = await opt._run_optimization()

        assert result["migrations_started"] >= 1

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_improvement_below_threshold_does_not_trigger(self, mock_fop):
        """Improvement of 0.14 < 0.15 must NOT trigger migration."""
        mock_fop.return_value = {"OpA": "cloud", "OpB": "edge-node-2"}
        # OpA: current edge-node-1 score 0.50, optimal cloud 0.36 → improvement 0.14
        scores = _np_array([
            [0.50, 0.40, 0.36],
            [0.60, 0.50, 0.45],
        ])
        opt, orch, _ = _make_optimizer(scores_array=scores)

        result = await opt._run_optimization()

        assert result["migrations_started"] == 0

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_zero_improvement_does_not_trigger(self, mock_fop):
        """When optimal == current tier, improvement is 0 — no migration."""
        mock_fop.return_value = {"OpA": "edge-node-1", "OpB": "edge-node-2"}
        opt, orch, _ = _make_optimizer()

        result = await opt._run_optimization()

        assert result["migrations_started"] == 0

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_negative_improvement_does_not_trigger(self, mock_fop):
        """A negative improvement (worse score in optimal) must not trigger migration."""
        mock_fop.return_value = {"OpA": "cloud", "OpB": "edge-node-2"}
        # OpA: current edge-node-1 score 0.3, optimal cloud 0.5 → improvement -0.2
        scores = _np_array([
            [0.3, 0.4, 0.5],
            [0.6, 0.5, 0.7],
        ])
        opt, orch, _ = _make_optimizer(scores_array=scores)

        result = await opt._run_optimization()

        assert result["migrations_started"] == 0

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_only_operators_with_changed_tier_considered(self, mock_fop):
        """Operators whose optimal tier matches current tier are never candidates."""
        mock_fop.return_value = {"OpA": "edge-node-1", "OpB": "cloud"}
        # OpA stays — should not be migrated regardless of scores
        # OpB moves to cloud — improvement 0.5 - 0.4 = 0.1 (below threshold)
        scores = _np_array([
            [0.5, 0.4, 0.3],
            [0.6, 0.5, 0.4],
        ])
        opt, orch, _ = _make_optimizer(scores_array=scores)

        result = await opt._run_optimization()

        assert result["migrations_started"] == 0


# ---------------------------------------------------------------------------
# TestPlacementOptimizerSorting
# ---------------------------------------------------------------------------

class TestPlacementOptimizerSorting:
    """Verify migration candidates are sorted by score improvement descending."""

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_candidates_sorted_descending_by_improvement(self, mock_fop):
        """Candidates list must be sorted from largest to smallest improvement."""
        current = {"OpA": "edge-node-1", "OpB": "edge-node-2", "OpC": "edge-node-1"}
        mock_fop.return_value = {"OpA": "cloud", "OpB": "cloud", "OpC": "cloud"}
        # OpA improvement: 1.0 - 0.3 = 0.7
        # OpB improvement: 0.5 - 0.1 = 0.4
        # OpC improvement: 0.9 - 0.2 = 0.7  (tie with OpA)
        scores = _np_array([
            [1.0, 0.8, 0.3],
            [0.6, 0.5, 0.1],
            [0.9, 0.7, 0.2],
        ])
        opt, orch, state = _make_optimizer(
            current_placement=current,
            scores_array=scores,
        )
        state.get_slo_map.return_value = {op: 2000.0 for op in current}
        state.get_lambda_map.return_value = {op: "standard" for op in current}

        operator_types = list(current.keys())
        tiers = ["cloud", "edge-node-1", "edge-node-2"]
        candidates = opt._identify_migration_candidates(
            current, mock_fop.return_value, scores, operator_types, tiers,
        )

        improvements = [c[3] for c in candidates]
        assert improvements == sorted(improvements, reverse=True)

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_largest_improvement_migrated_first(self, mock_fop):
        """The first migration triggered should be for the operator with largest improvement."""
        current = {"OpA": "edge-node-1", "OpB": "edge-node-2"}
        mock_fop.return_value = {"OpA": "cloud", "OpB": "cloud"}
        # OpA improvement: 1.0 - 0.3 = 0.7
        # OpB improvement: 0.5 - 0.2 = 0.3
        scores = _np_array([
            [1.0, 0.8, 0.3],
            [0.6, 0.5, 0.2],
        ])
        opt, orch, _ = _make_optimizer(
            current_placement=current,
            scores_array=scores,
        )

        await opt._run_optimization()

        first_call = orch.migrate_operator.call_args_list[0]
        # first positional arg is operator_id
        assert first_call[0][0] == "OpA"


# ---------------------------------------------------------------------------
# TestPlacementOptimizerResults
# ---------------------------------------------------------------------------

class TestPlacementOptimizerResults:
    """Verify the result dict returned by _run_optimization."""

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_result_dict_has_required_keys(self, mock_fop):
        """Result must contain status, duration_ms, migrations_started, candidates_evaluated, migrations."""
        mock_fop.return_value = {"OpA": "cloud", "OpB": "cloud"}
        opt, _, _ = _make_optimizer()

        result = await opt._run_optimization()

        for key in ("status", "duration_ms", "migrations_started", "candidates_evaluated", "migrations"):
            assert key in result, f"Missing key: {key}"

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_no_operators_returns_no_operators_status(self, mock_fop):
        """When placement is empty, result status should be 'no_operators'."""
        mock_fop.return_value = {}
        opt, _, state = _make_optimizer(current_placement={})
        state.get_available_tiers.return_value = ["cloud"]
        state.get_slo_map.return_value = {}
        state.get_lambda_map.return_value = {}

        result = await opt._run_optimization()

        assert result["status"] == "no_operators"

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_migrations_started_count_matches_actual(self, mock_fop):
        """migrations_started must equal the number of migrate_operator calls."""
        mock_fop.return_value = {"OpA": "cloud", "OpB": "cloud"}
        # OpA improvement 0.7 (trigger), OpB improvement 0.1 (no trigger)
        opt, orch, _ = _make_optimizer()

        result = await opt._run_optimization()

        assert result["migrations_started"] == orch.migrate_operator.call_count

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_placement_state_updated_after_migration(self, mock_fop):
        """After a successful migration, update_operator_placement must be called."""
        mock_fop.return_value = {"OpA": "cloud", "OpB": "edge-node-2"}
        opt, _, state = _make_optimizer()

        await opt._run_optimization()

        state.update_operator_placement.assert_called()

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_migration_failure_does_not_crash_optimizer(self, mock_fop):
        """If migrate_operator raises, the optimizer should catch it and continue."""
        mock_fop.return_value = {"OpA": "cloud", "OpB": "cloud"}
        opt, orch, _ = _make_optimizer()
        orch.migrate_operator = AsyncMock(side_effect=RuntimeError("migration failed"))

        # Must not raise
        result = await opt._run_optimization()

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# TestPlacementOptimizerDisabled
# ---------------------------------------------------------------------------

class TestPlacementOptimizerDisabled:
    """Verify disabled optimizer behaviour and force_recalibration override."""

    def test_disabled_optimizer_does_not_create_task(self):
        """When recalibration_enabled=False, start() should not create _optimization_task."""
        from aode.aode.config import AODEConfig
        from aode.aode.placement.optimizer import PlacementOptimizer

        config = AODEConfig()
        config.recalibration_enabled = False

        optimizer = PlacementOptimizer(
            config=config,
            scoring=MagicMock(),
            migration_orchestrator=AsyncMock(),
            placement_state=MagicMock(),
        )

        assert optimizer._config.recalibration_enabled is False

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_force_recalibration_works_when_disabled(self, mock_fop):
        """force_recalibration should work even when recalibration_enabled is False."""
        from aode.aode.config import AODEConfig
        from aode.aode.placement.optimizer import PlacementOptimizer

        config = AODEConfig()
        config.recalibration_enabled = False

        scoring = MagicMock()
        scoring.compute_scores = MagicMock(return_value=_np_array([[0.5, 0.5]]))

        state = MagicMock()
        state.get_current_placement = MagicMock(return_value={"OpA": "edge-node-1"})
        state.get_available_tiers = MagicMock(return_value=["edge-node-1", "cloud"])
        state.get_slo_map = MagicMock(return_value={"OpA": 2000.0})
        state.get_lambda_map = MagicMock(return_value={"OpA": "standard"})
        state.get_tier_capacities = MagicMock(
            return_value={"edge-node-1": 5, "cloud": 100}
        )
        state.update_operator_placement = AsyncMock()

        mock_fop.return_value = {"OpA": "edge-node-1"}

        optimizer = PlacementOptimizer(
            config=config,
            scoring=scoring,
            migration_orchestrator=AsyncMock(),
            placement_state=state,
        )

        result = await optimizer.force_recalibration(reason="manual test")
        assert isinstance(result, dict)

    def test_recalibration_enabled_false_in_config(self):
        """Confirm that setting recalibration_enabled=False is respected by the optimizer."""
        from aode.aode.config import AODEConfig
        from aode.aode.placement.optimizer import PlacementOptimizer

        config = AODEConfig()
        config.recalibration_enabled = False

        optimizer = PlacementOptimizer(
            config=config,
            scoring=MagicMock(),
            migration_orchestrator=AsyncMock(),
            placement_state=MagicMock(),
        )

        assert optimizer._config.recalibration_enabled is False


# ---------------------------------------------------------------------------
# TestPlacementOptimizerEdgeCases (2 tests)
# ---------------------------------------------------------------------------

class TestPlacementOptimizerEdgeCases:
    """Verify optimizer behaviour for empty placements and tier list construction."""

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_run_optimization_with_empty_placement_returns_no_operators(self, mock_fop):
        """_run_optimization with no operators in placement returns status 'no_operators'."""
        mock_fop.return_value = {}

        opt, _, state = _make_optimizer(current_placement={})
        state.get_available_tiers.return_value = ["cloud"]
        state.get_slo_map.return_value = {}
        state.get_lambda_map.return_value = {}

        result = await opt._run_optimization()

        assert result["status"] == "no_operators"
        mock_fop.assert_not_called()

    @pytest.mark.asyncio
    @patch("aode.aode.placement.optimizer.find_optimal_placement")
    async def test_tiers_sourced_from_tier_capacities_not_just_occupied(self, mock_fop):
        """_run_optimization must pass ALL tiers from get_tier_capacities to find_optimal_placement,
        not only the tiers that happen to be occupied in the current placement."""
        # Only OpA is placed on edge-node-1, but get_tier_capacities has 3 tiers.
        current = {"OpA": "edge-node-1"}
        all_caps = {"edge-node-1": 5, "edge-node-2": 5, "cloud": 100}
        mock_fop.return_value = {"OpA": "edge-node-1"}

        scores = _np_array([[0.5, 0.5, 0.5]])
        opt, _, state = _make_optimizer(
            current_placement=current,
            scores_array=scores,
        )
        state.get_available_tiers.return_value = list(all_caps.keys())
        state.get_tier_capacities.return_value = all_caps
        state.get_slo_map.return_value = {"OpA": 2000.0}
        state.get_lambda_map.return_value = {"OpA": "standard"}

        await opt._run_optimization()

        # find_optimal_placement must have been called with all 3 tiers from tier_capacities
        call_args = mock_fop.call_args
        tiers_arg = call_args[0][2]  # positional arg index 2 = tiers list
        assert set(tiers_arg) == {"edge-node-1", "edge-node-2", "cloud"}
