"""Tests for aode.aode.placement.state — PlacementState cache and SLO/lambda maps."""
import pytest
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# TestPlacementStateCache
# ---------------------------------------------------------------------------

class TestPlacementStateCache:
    """Verify PlacementState caches operator placements and syncs with etcd."""

    def _make_state(self, etcd_client=None):
        """Build a PlacementState with a mocked etcd client."""
        from aode.aode.placement.state import PlacementState

        etcd_client = etcd_client or self._default_etcd_client()
        return PlacementState(etcd_client=etcd_client)

    def _default_etcd_client(self):
        """Return a mock EtcdClient with default no-op responses."""
        client = AsyncMock()
        client.put = AsyncMock()
        client.get = AsyncMock(return_value=None)
        client.delete = AsyncMock()
        client.get_dict = AsyncMock(return_value={})
        return client

    @pytest.mark.asyncio
    async def test_update_operator_placement_updates_cache(self):
        """After update_operator_placement the cache must reflect the new tier."""
        etcd = self._default_etcd_client()
        state = self._make_state(etcd_client=etcd)

        await state.update_operator_placement("VehicleDetector", "cloud")

        placement = state.get_current_placement()
        assert placement["VehicleDetector"] == "cloud"

    @pytest.mark.asyncio
    async def test_update_operator_placement_calls_etcd_put(self):
        """update_operator_placement must persist the value via etcd.put."""
        etcd = self._default_etcd_client()
        state = self._make_state(etcd_client=etcd)

        await state.update_operator_placement("VehicleDetector", "cloud")

        etcd.put.assert_called_once()
        call_args = etcd.put.call_args
        # The key should contain the operator name
        assert "VehicleDetector" in str(call_args)

    def test_get_current_placement_returns_independent_copy(self):
        """Mutating the returned dict must not affect the internal cache."""
        state = self._make_state()
        state._cache = {"VehicleDetector": "edge-node-1"}

        placement = state.get_current_placement()
        placement["VehicleDetector"] = "cloud"

        assert state._cache["VehicleDetector"] == "edge-node-1"

    def test_get_operators_on_tier_filters_correctly(self):
        """get_operators_on_tier must return only operators placed on the given tier."""
        state = self._make_state()
        state._cache = {
            "VehicleDetector": "edge-node-1",
            "ZoneAggregator": "edge-node-1",
            "PatternDetector": "cloud",
        }

        edge_ops = state.get_operators_on_tier("edge-node-1")
        assert sorted(edge_ops) == ["VehicleDetector", "ZoneAggregator"]

        cloud_ops = state.get_operators_on_tier("cloud")
        assert cloud_ops == ["PatternDetector"]

    def test_get_operators_on_tier_empty_for_unknown(self):
        """Querying a tier with no operators must return an empty list."""
        state = self._make_state()
        state._cache = {"VehicleDetector": "edge-node-1"}

        result = state.get_operators_on_tier("edge-node-99")
        assert result == []


# ---------------------------------------------------------------------------
# TestPlacementStateRemove
# ---------------------------------------------------------------------------

class TestPlacementStateRemove:
    """Verify remove_operator deletes from both cache and etcd."""

    def _make_state(self):
        """Build a PlacementState with a mocked etcd client."""
        from aode.aode.placement.state import PlacementState

        etcd = AsyncMock()
        etcd.put = AsyncMock()
        etcd.delete = AsyncMock()
        state = PlacementState(etcd_client=etcd)
        state._cache = {"VehicleDetector": "edge-node-1"}
        return state, etcd

    @pytest.mark.asyncio
    async def test_remove_operator_removes_from_cache(self):
        """After remove_operator the key must be absent from the cache."""
        state, _ = self._make_state()

        await state.remove_operator("VehicleDetector")

        assert "VehicleDetector" not in state._cache

    @pytest.mark.asyncio
    async def test_remove_operator_calls_etcd_delete(self):
        """remove_operator must call etcd.delete for persistence."""
        state, etcd = self._make_state()

        await state.remove_operator("VehicleDetector")

        etcd.delete.assert_called_once()


# ---------------------------------------------------------------------------
# TestPlacementStateSLOMap
# ---------------------------------------------------------------------------

class TestPlacementStateSLOMap:
    """Verify SLO map contains correct latency targets for all 11 operator types."""

    def _make_state(self):
        """Build a PlacementState with a mocked etcd client."""
        from aode.aode.placement.state import PlacementState

        return PlacementState(etcd_client=AsyncMock())

    def test_slo_map_has_11_entries(self):
        """The SLO map must contain exactly 11 operator types."""
        state = self._make_state()
        slo = state.get_slo_map()
        assert len(slo) == 11

    def test_batch_operators_have_no_slo(self):
        """Batch operators (ZoneAggregator, StatAggregator, ComplianceLogger) have None SLO."""
        state = self._make_state()
        slo = state.get_slo_map()

        assert slo["ZoneAggregator"] is None
        assert slo["StatAggregator"] is None
        assert slo["ComplianceLogger"] is None

    def test_critical_operators_slo_values(self):
        """Critical operators have tight latency SLOs: RiskCheck=1.0, AnomalyDetector=5.0, BinaryClassifier=5.0."""
        state = self._make_state()
        slo = state.get_slo_map()

        assert slo["RiskCheck"] == 1.0
        assert slo["AnomalyDetector"] == 5.0
        assert slo["BinaryClassifier"] == 5.0

    def test_standard_operators_slo_values(self):
        """Standard operators have documented SLO values matching state.py source."""
        state = self._make_state()
        slo = state.get_slo_map()

        assert slo["VehicleDetector"] == 2000.0
        # PatternDetector has no real-time SLO in the current implementation
        assert slo["PatternDetector"] is None
        assert slo["NormalizerOperator"] == 5.0
        assert slo["FeatureAggWindow"] == 5.0
        assert slo["MultiStreamJoin"] == 5.0


# ---------------------------------------------------------------------------
# TestPlacementStateLambdaMap
# ---------------------------------------------------------------------------

class TestPlacementStateLambdaMap:
    """Verify lambda-class map contains correct classes for all 11 operator types."""

    def _make_state(self):
        """Build a PlacementState with a mocked etcd client."""
        from aode.aode.placement.state import PlacementState

        return PlacementState(etcd_client=AsyncMock())

    def test_lambda_map_has_11_entries(self):
        """The lambda map must contain exactly 11 operator types."""
        state = self._make_state()
        lm = state.get_lambda_map()
        assert len(lm) == 11

    def test_critical_operators_lambda_class(self):
        """RiskCheck, AnomalyDetector, BinaryClassifier must be 'critical'."""
        state = self._make_state()
        lm = state.get_lambda_map()

        assert lm["RiskCheck"] == "critical"
        assert lm["AnomalyDetector"] == "critical"
        assert lm["BinaryClassifier"] == "critical"

    def test_batch_operators_lambda_class(self):
        """ZoneAggregator, StatAggregator, ComplianceLogger must be 'batch'."""
        state = self._make_state()
        lm = state.get_lambda_map()

        assert lm["ZoneAggregator"] == "batch"
        assert lm["StatAggregator"] == "batch"
        assert lm["ComplianceLogger"] == "batch"

    def test_standard_operators_lambda_class(self):
        """VehicleDetector, PatternDetector, NormalizerOperator, FeatureAggWindow, MultiStreamJoin must be 'standard'."""
        state = self._make_state()
        lm = state.get_lambda_map()

        assert lm["VehicleDetector"] == "standard"
        assert lm["PatternDetector"] == "standard"
        assert lm["NormalizerOperator"] == "standard"
        assert lm["FeatureAggWindow"] == "standard"
        assert lm["MultiStreamJoin"] == "standard"


# ---------------------------------------------------------------------------
# TestPlacementStateTierCapacities
# ---------------------------------------------------------------------------

class TestPlacementStateTierCapacities:
    """Verify tier capacity map contains all 5 tiers with correct values."""

    def _make_state(self):
        """Build a PlacementState with a mocked etcd client."""
        from aode.aode.placement.state import PlacementState

        return PlacementState(etcd_client=AsyncMock())

    def test_all_five_tiers_present(self):
        """Tier capacities must include edge-node-1 through edge-node-4 and cloud."""
        state = self._make_state()
        caps = state.get_tier_capacities()

        expected_tiers = {"edge-node-1", "edge-node-2", "edge-node-3", "edge-node-4", "cloud"}
        assert set(caps.keys()) == expected_tiers

    def test_capacity_values(self):
        """Cloud has capacity 100; each edge node has capacity 5."""
        state = self._make_state()
        caps = state.get_tier_capacities()

        assert caps["cloud"] == 100
        for i in range(1, 5):
            assert caps[f"edge-node-{i}"] == 5


# ---------------------------------------------------------------------------
# TestGetAvailableTiers (2 tests)
# ---------------------------------------------------------------------------

class TestGetAvailableTiers:
    """Verify get_available_tiers returns all tiers from tier_capacities."""

    def _make_state(self):
        from aode.aode.placement.state import PlacementState

        return PlacementState(etcd_client=AsyncMock())

    def test_get_available_tiers_returns_all_five_tiers(self):
        """get_available_tiers must return all 5 tiers regardless of cache contents."""
        state = self._make_state()
        # Only one operator is placed — available tiers must still list all 5.
        state._cache = {"VehicleDetector": "edge-node-1"}

        tiers = state.get_available_tiers()

        expected = {"edge-node-1", "edge-node-2", "edge-node-3", "edge-node-4", "cloud"}
        assert set(tiers) == expected

    def test_get_available_tiers_returns_all_tiers_when_cache_empty(self):
        """get_available_tiers must return all 5 tiers even when no operators are placed."""
        state = self._make_state()
        state._cache = {}

        tiers = state.get_available_tiers()

        expected = {"edge-node-1", "edge-node-2", "edge-node-3", "edge-node-4", "cloud"}
        assert set(tiers) == expected


# ---------------------------------------------------------------------------
# TestSloMapActualValues (4 tests)
# ---------------------------------------------------------------------------

class TestSloMapActualValues:
    """Verify get_slo_map returns the actual values defined in the source."""

    def _make_state(self):
        from aode.aode.placement.state import PlacementState

        return PlacementState(etcd_client=AsyncMock())

    def test_normalizer_operator_slo_is_5(self):
        """NormalizerOperator SLO must be 5.0 ms as defined in state.py."""
        state = self._make_state()
        assert state.get_slo_map()["NormalizerOperator"] == 5.0

    def test_feature_agg_window_slo_is_5(self):
        """FeatureAggWindow SLO must be 5.0 ms as defined in state.py."""
        state = self._make_state()
        assert state.get_slo_map()["FeatureAggWindow"] == 5.0

    def test_multi_stream_join_slo_is_5(self):
        """MultiStreamJoin SLO must be 5.0 ms as defined in state.py."""
        state = self._make_state()
        assert state.get_slo_map()["MultiStreamJoin"] == 5.0

    def test_pattern_detector_slo_is_none(self):
        """PatternDetector has no real-time SLO; its value must be None."""
        state = self._make_state()
        assert state.get_slo_map()["PatternDetector"] is None
