"""Tests for aode.aode.telemetry.collector — TelemetryCollector and HEATelemetry.

All external deps are mocked. Source modules do NOT exist yet (TDD).
Every test has a docstring. Uses @pytest.mark.asyncio for async tests.
"""
import pytest


# ---------------------------------------------------------------------------
# Helper factories (module-level)
# ---------------------------------------------------------------------------
def _make_telemetry(
    hea_id,
    cpu=0.5,
    mem=0.5,
    rtt=10.0,
    ingest=1000.0,
    p95=None,
    ts=1700000000000,
    reachable=True,
    latency=0.0,
):
    """Create an HEATelemetry dataclass with sensible defaults."""
    from aode.aode.telemetry.collector import HEATelemetry

    return HEATelemetry(
        hea_id=hea_id,
        cpu_utilization=cpu,
        memory_utilization=mem,
        rtt_ms=rtt,
        ingest_rate_eps=ingest,
        operator_p95_ms=p95 or {},
        timestamp_ms=ts,
        reachable=reachable,
        collection_latency_ms=latency,
    )


def _make_collector():
    """Create a TelemetryCollector backed by a default AODEConfig."""
    from aode.aode.config import AODEConfig
    from aode.aode.telemetry.collector import TelemetryCollector

    return TelemetryCollector(AODEConfig())


# ---------------------------------------------------------------------------
# TestHEATelemetry (4 tests)
# ---------------------------------------------------------------------------
class TestHEATelemetry:
    """Verify HEATelemetry dataclass field population."""

    def test_all_fields_populated(self):
        """All fields should be accessible after construction."""
        t = _make_telemetry(
            "edge-1",
            cpu=0.45,
            mem=0.60,
            rtt=12.5,
            ingest=5000.0,
            p95={"op-a": 8.2, "op-b": 15.1},
            ts=1700000000000,
            reachable=True,
        )
        assert t.hea_id == "edge-1"
        assert t.cpu_utilization == 0.45
        assert t.memory_utilization == 0.60
        assert t.rtt_ms == 12.5
        assert t.ingest_rate_eps == 5000.0
        assert t.operator_p95_ms == {"op-a": 8.2, "op-b": 15.1}
        assert t.timestamp_ms == 1700000000000
        assert t.reachable is True

    def test_collection_latency_default_zero(self):
        """collection_latency_ms should default to 0.0 when not specified."""
        t = _make_telemetry("edge-1")
        assert t.collection_latency_ms == 0.0

    def test_unreachable_has_reachable_false(self):
        """An unreachable telemetry record should have reachable=False."""
        t = _make_telemetry("edge-down", reachable=False)
        assert t.reachable is False

    def test_custom_collection_latency(self):
        """Explicit collection_latency_ms should be stored."""
        t = _make_telemetry("edge-1", latency=42.5)
        assert t.collection_latency_ms == 42.5


# ---------------------------------------------------------------------------
# TestGetReachableHeas (4 tests)
# ---------------------------------------------------------------------------
class TestGetReachableHeas:
    """Verify get_reachable_heas filters by reachable flag."""

    def test_filters_unreachable(self):
        """Only reachable HEAs should be returned."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", reachable=True),
            "edge-2": _make_telemetry("edge-2", reachable=False),
            "edge-3": _make_telemetry("edge-3", reachable=True),
        }
        assert sorted(collector.get_reachable_heas()) == ["edge-1", "edge-3"]

    def test_empty_when_all_down(self):
        """Empty list when every HEA is unreachable."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", reachable=False),
            "edge-2": _make_telemetry("edge-2", reachable=False),
        }
        assert collector.get_reachable_heas() == []

    def test_all_reachable_returns_all(self):
        """All HEA ids returned when every node is reachable."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", reachable=True),
            "edge-2": _make_telemetry("edge-2", reachable=True),
        }
        assert sorted(collector.get_reachable_heas()) == ["edge-1", "edge-2"]

    def test_empty_telemetry_returns_empty_list(self):
        """Empty telemetry dict should yield an empty list."""
        collector = _make_collector()
        collector._last_telemetry = {}
        assert collector.get_reachable_heas() == []


# ---------------------------------------------------------------------------
# TestGetTierUtilization (5 tests)
# ---------------------------------------------------------------------------
class TestGetTierUtilization:
    """Verify get_tier_utilization returns correct (cpu, mem) tuple."""

    def test_correct_values_for_reachable(self):
        """Returns actual (cpu, mem) for a reachable HEA."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", cpu=0.35, mem=0.72, reachable=True),
        }
        cpu, mem = collector.get_tier_utilization("edge-1")
        assert cpu == 0.35
        assert mem == 0.72

    def test_unreachable_returns_high_values(self):
        """Returns (0.9, 0.9) for an unreachable HEA."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", cpu=0.3, mem=0.4, reachable=False),
        }
        cpu, mem = collector.get_tier_utilization("edge-1")
        assert cpu == 0.9
        assert mem == 0.9

    def test_unknown_hea_returns_high_values(self):
        """Returns (0.9, 0.9) for an unknown hea_id."""
        collector = _make_collector()
        collector._last_telemetry = {}
        cpu, mem = collector.get_tier_utilization("nonexistent")
        assert cpu == 0.9
        assert mem == 0.9

    def test_high_cpu_low_mem(self):
        """Returns actual values when cpu is high and mem is low."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", cpu=0.95, mem=0.10, reachable=True),
        }
        cpu, mem = collector.get_tier_utilization("edge-1")
        assert cpu == 0.95
        assert mem == 0.10

    def test_low_cpu_high_mem(self):
        """Returns actual values when cpu is low and mem is high."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", cpu=0.05, mem=0.88, reachable=True),
        }
        cpu, mem = collector.get_tier_utilization("edge-1")
        assert cpu == 0.05
        assert mem == 0.88


# ---------------------------------------------------------------------------
# TestGetOperatorLatency (5 tests)
# ---------------------------------------------------------------------------
class TestGetOperatorLatency:
    """Verify get_operator_latency returns max p95 across reachable nodes."""

    def test_single_node_returns_p95(self):
        """Single reachable node returns its p95 for the operator."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", p95={"op-a": 42.0}, reachable=True),
        }
        assert collector.get_operator_latency("op-a") == 42.0

    def test_multiple_nodes_returns_max(self):
        """Returns MAX p95 across multiple reachable nodes."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", p95={"op-a": 5.0}, reachable=True),
            "edge-2": _make_telemetry("edge-2", p95={"op-a": 8.0}, reachable=True),
            "edge-3": _make_telemetry("edge-3", p95={"op-a": 6.5}, reachable=True),
        }
        assert collector.get_operator_latency("op-a") == 8.0

    def test_unknown_operator_returns_none(self):
        """Returns None when operator is not found in any node."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", p95={"op-a": 5.0}, reachable=True),
        }
        assert collector.get_operator_latency("nonexistent-op") is None

    def test_unreachable_nodes_excluded(self):
        """Unreachable nodes should be excluded from the max calculation."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1", p95={"op-a": 5.0}, reachable=True),
            "edge-2": _make_telemetry(
                "edge-2", p95={"op-a": 999.0}, reachable=False
            ),
        }
        assert collector.get_operator_latency("op-a") == 5.0

    def test_empty_telemetry_returns_none(self):
        """Returns None when telemetry dict is empty."""
        collector = _make_collector()
        collector._last_telemetry = {}
        assert collector.get_operator_latency("op-a") is None


# ---------------------------------------------------------------------------
# TestGetLatestTelemetry (3 tests)
# ---------------------------------------------------------------------------
class TestGetLatestTelemetry:
    """Verify get_latest_telemetry returns a safe copy of the internal cache."""

    def test_returns_copy_not_reference(self):
        """Mutating the returned dict must not affect internal state."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1"),
        }
        result = collector.get_latest_telemetry()
        result["injected-key"] = "should-not-leak"
        assert "injected-key" not in collector._last_telemetry

    def test_returns_all_entries(self):
        """All entries in _last_telemetry appear in the returned dict."""
        collector = _make_collector()
        collector._last_telemetry = {
            "edge-1": _make_telemetry("edge-1"),
            "edge-2": _make_telemetry("edge-2"),
            "edge-3": _make_telemetry("edge-3"),
        }
        result = collector.get_latest_telemetry()
        assert set(result.keys()) == {"edge-1", "edge-2", "edge-3"}

    def test_empty_returns_empty_dict(self):
        """Empty internal cache yields an empty dict."""
        collector = _make_collector()
        collector._last_telemetry = {}
        assert collector.get_latest_telemetry() == {}


# ---------------------------------------------------------------------------
# TestCollectOne (4 tests)
# ---------------------------------------------------------------------------
class TestCollectOne:
    """Verify _collect_one populates telemetry from a single HEA."""

    @pytest.mark.asyncio
    async def test_success_populates_all_fields(self):
        """Successful collection should populate all HEATelemetry fields."""
        from unittest.mock import AsyncMock, MagicMock, patch

        collector = _make_collector()

        mock_response = MagicMock()
        mock_response.cpu_utilization = 0.45
        mock_response.memory_utilization = 0.60
        mock_response.rtt_ms = 12.5
        mock_response.ingest_rate_eps = 5000.0
        mock_response.operator_p95_ms = {"op-a": 8.2}

        mock_stub = AsyncMock()
        mock_stub.CollectTelemetry = AsyncMock(return_value=mock_response)

        with patch.object(collector, "_get_stub", return_value=mock_stub):
            result = await collector._collect_one("edge-1")

        assert result.hea_id == "edge-1"
        assert result.cpu_utilization == 0.45
        assert result.memory_utilization == 0.60
        assert result.rtt_ms == 12.5
        assert result.ingest_rate_eps == 5000.0
        assert result.reachable is True

    @pytest.mark.asyncio
    async def test_unreachable_returns_reachable_false(self):
        """Failed collection should mark the HEA as unreachable."""
        from unittest.mock import AsyncMock, patch

        collector = _make_collector()

        mock_stub = AsyncMock()
        mock_stub.CollectTelemetry = AsyncMock(side_effect=Exception("timeout"))

        with patch.object(collector, "_get_stub", return_value=mock_stub):
            result = await collector._collect_one("edge-down")

        assert result.reachable is False

    @pytest.mark.asyncio
    async def test_unreachable_has_high_rtt(self):
        """Unreachable HEA should report rtt_ms=1000.0."""
        from unittest.mock import AsyncMock, patch

        collector = _make_collector()

        mock_stub = AsyncMock()
        mock_stub.CollectTelemetry = AsyncMock(side_effect=Exception("timeout"))

        with patch.object(collector, "_get_stub", return_value=mock_stub):
            result = await collector._collect_one("edge-down")

        assert result.rtt_ms == 1000.0

    @pytest.mark.asyncio
    async def test_unreachable_has_zero_utilization(self):
        """Unreachable HEA should report cpu=0.0 and mem=0.0."""
        from unittest.mock import AsyncMock, patch

        collector = _make_collector()

        mock_stub = AsyncMock()
        mock_stub.CollectTelemetry = AsyncMock(side_effect=Exception("timeout"))

        with patch.object(collector, "_get_stub", return_value=mock_stub):
            result = await collector._collect_one("edge-down")

        assert result.cpu_utilization == 0.0
        assert result.memory_utilization == 0.0


# ---------------------------------------------------------------------------
# TestRegisterHea (3 tests)
# ---------------------------------------------------------------------------
class TestRegisterHea:
    """Verify register_hea adds a placeholder entry and is idempotent."""

    def test_register_hea_adds_placeholder_entry(self):
        """Calling register_hea with a new id must add a key to _last_telemetry."""
        collector = _make_collector()
        # Clear any endpoints registered by AODEConfig defaults
        collector._last_telemetry.clear()

        collector.register_hea("new-edge-5")

        assert "new-edge-5" in collector._last_telemetry

    def test_register_hea_placeholder_is_unreachable(self):
        """The placeholder entry created by register_hea must have reachable=False."""
        collector = _make_collector()
        collector._last_telemetry.clear()

        collector.register_hea("new-edge-5")

        assert collector._last_telemetry["new-edge-5"].reachable is False

    def test_register_hea_is_idempotent(self):
        """Calling register_hea twice for the same id must not overwrite an existing entry."""
        collector = _make_collector()
        collector._last_telemetry.clear()

        collector.register_hea("new-edge-5")
        # Manually set a field so we can detect if it gets overwritten
        collector._last_telemetry["new-edge-5"].cpu_utilization = 0.77
        collector.register_hea("new-edge-5")

        assert collector._last_telemetry["new-edge-5"].cpu_utilization == 0.77


# ---------------------------------------------------------------------------
# TestTelemetryCollectorInit (2 tests)
# ---------------------------------------------------------------------------
class TestTelemetryCollectorInit:
    """Verify __init__ registers all HEAs listed in config.hea_endpoints."""

    def test_init_registers_heas_from_config_endpoints(self):
        """Every host in config.hea_endpoints should appear in _last_telemetry after init."""
        from aode.aode.config import AODEConfig
        from aode.aode.telemetry.collector import TelemetryCollector

        config = AODEConfig()
        # Default config has 4 HEA endpoints: edge-node-1..4:50051
        collector = TelemetryCollector(config)

        expected_ids = {ep.split(":")[0] for ep in config.hea_endpoints}
        assert expected_ids.issubset(set(collector._last_telemetry.keys()))

    def test_init_registered_heas_start_unreachable(self):
        """HEAs registered during __init__ must start as unreachable placeholders."""
        from aode.aode.config import AODEConfig
        from aode.aode.telemetry.collector import TelemetryCollector

        config = AODEConfig()
        collector = TelemetryCollector(config)

        for ep in config.hea_endpoints:
            hea_id = ep.split(":")[0]
            assert collector._last_telemetry[hea_id].reachable is False


# ---------------------------------------------------------------------------
# TestCollectAll (2 tests)
# ---------------------------------------------------------------------------
class TestCollectAll:
    """Verify _collect_all iterates over all registered HEAs."""

    @pytest.mark.asyncio
    async def test_collect_all_calls_collect_one_for_each_registered_hea(self):
        """_collect_all must invoke _collect_one once per entry in _last_telemetry."""
        from unittest.mock import AsyncMock, patch

        collector = _make_collector()
        # Seed two specific HEAs
        collector._last_telemetry.clear()
        collector.register_hea("edge-a")
        collector.register_hea("edge-b")

        collected = []

        async def fake_collect_one(hea_id):
            collected.append(hea_id)
            return _make_telemetry(hea_id)

        with patch.object(collector, "_collect_one", side_effect=fake_collect_one):
            await collector._collect_all()

        assert sorted(collected) == ["edge-a", "edge-b"]

    @pytest.mark.asyncio
    async def test_collect_all_updates_last_telemetry(self):
        """After _collect_all, _last_telemetry must contain fresh records for each HEA."""
        from unittest.mock import AsyncMock, patch

        collector = _make_collector()
        collector._last_telemetry.clear()
        collector.register_hea("edge-x")

        fresh = _make_telemetry("edge-x", cpu=0.42, reachable=True)

        async def fake_collect_one(hea_id):
            return fresh

        with patch.object(collector, "_collect_one", side_effect=fake_collect_one):
            await collector._collect_all()

        assert collector._last_telemetry["edge-x"].cpu_utilization == 0.42
