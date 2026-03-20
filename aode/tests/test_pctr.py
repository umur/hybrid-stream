"""Tests for aode.aode.migration.pctr — PCTR migration phases and orchestrator."""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_hea_client():
    """Return a mock HEA gRPC client with default successful responses."""
    snapshot_resp = MagicMock(object_key="snap-123", byte_size=1024, error_msg="")
    terminate_resp = MagicMock(success=True, error_msg="")
    drain_resp = MagicMock(success=True, error_msg="", offset_map={"partition-0": 42})

    client = AsyncMock()
    client.trigger_snapshot = AsyncMock(return_value=snapshot_resp)
    client.terminate_operator = AsyncMock(return_value=terminate_resp)
    client.drain_operator = AsyncMock(return_value=drain_resp)
    return client


def _mock_flink_client():
    """Return a mock Flink REST client with default successful responses."""
    client = AsyncMock()
    client.restore_operator = AsyncMock()
    return client


def _make_migration(
    hea_clients=None,
    flink_client=None,
    object_store=None,
    source_tier="edge-node-1",
    target_tier="cloud",
    migration_id="mig-001",
    operator_id="VehicleDetector",
):
    """Build a PCTRMigration with fully-mocked dependencies."""
    from aode.aode.config import AODEConfig
    from aode.aode.migration.pctr import PCTRMigration

    default_hea = _mock_hea_client()
    hea_clients = hea_clients or {source_tier: default_hea, "cloud": default_hea}
    flink_client = flink_client or _mock_flink_client()
    object_store = object_store or MagicMock()

    return PCTRMigration(
        migration_id=migration_id,
        operator_id=operator_id,
        source_tier=source_tier,
        target_tier=target_tier,
        config=AODEConfig(),
        hea_clients=hea_clients,
        flink_client=flink_client,
        object_store=object_store,
    )


# ---------------------------------------------------------------------------
# TestMigrationPhaseEnum
# ---------------------------------------------------------------------------

class TestMigrationPhaseEnum:
    """Verify MigrationPhase enum values match the PCTR protocol spec."""

    def test_phase_1_drain_value(self):
        """PHASE_1_DRAIN should have string value 'drain'."""
        from aode.aode.migration.pctr import MigrationPhase

        assert MigrationPhase.PHASE_1_DRAIN.value == "drain"

    def test_phase_2_snap_value(self):
        """PHASE_2_SNAP should have string value 'snapshot'."""
        from aode.aode.migration.pctr import MigrationPhase

        assert MigrationPhase.PHASE_2_SNAP.value == "snapshot"

    def test_phase_3_restore_value(self):
        """PHASE_3_RESTORE should have string value 'restore'."""
        from aode.aode.migration.pctr import MigrationPhase

        assert MigrationPhase.PHASE_3_RESTORE.value == "restore"

    def test_phase_4_term_value(self):
        """PHASE_4_TERM should have string value 'terminate'."""
        from aode.aode.migration.pctr import MigrationPhase

        assert MigrationPhase.PHASE_4_TERM.value == "terminate"


# ---------------------------------------------------------------------------
# TestPCTRMigrationInit
# ---------------------------------------------------------------------------

class TestPCTRMigrationInit:
    """Verify PCTRMigration fields are correctly initialised."""

    def test_migration_id_assigned(self):
        """migration_id should be stored as-is."""
        m = _make_migration(migration_id="mig-042")
        assert m.migration_id == "mig-042"

    def test_operator_id_assigned(self):
        """operator_id should be stored as-is."""
        m = _make_migration(operator_id="ZoneAggregator")
        assert m.operator_id == "ZoneAggregator"

    def test_source_tier_assigned(self):
        """source_tier should reflect the constructor argument."""
        m = _make_migration(source_tier="edge-node-2")
        assert m.source_tier == "edge-node-2"

    def test_target_tier_assigned(self):
        """target_tier should reflect the constructor argument."""
        m = _make_migration(target_tier="edge-node-3")
        assert m.target_tier == "edge-node-3"

    def test_initial_phase_is_drain(self):
        """A fresh migration should start in PHASE_1_DRAIN."""
        from aode.aode.migration.pctr import MigrationPhase

        m = _make_migration()
        assert m.phase == MigrationPhase.PHASE_1_DRAIN


# ---------------------------------------------------------------------------
# TestPCTRMigrationExecute
# ---------------------------------------------------------------------------

class TestPCTRMigrationExecute:
    """Verify the four-phase PCTR execution lifecycle."""

    @pytest.mark.asyncio
    async def test_phases_execute_in_order(self):
        """The four internal _phase_* methods must run drain -> snapshot -> restore -> terminate."""
        call_order = []

        hea = AsyncMock()
        hea.drain_operator = AsyncMock(
            side_effect=lambda *a, **kw: (
                call_order.append("drain"),
                MagicMock(success=True, error_msg="", offset_map={"p0": 10}),
            )[-1]
        )
        hea.trigger_snapshot = AsyncMock(
            side_effect=lambda *a, **kw: (
                call_order.append("snapshot"),
                MagicMock(object_key="snap-123", byte_size=1024, error_msg=""),
            )[-1]
        )
        hea.terminate_operator = AsyncMock(
            side_effect=lambda *a, **kw: (
                call_order.append("terminate"),
                MagicMock(success=True, error_msg=""),
            )[-1]
        )

        flink = AsyncMock()
        flink.restore_operator = AsyncMock(
            side_effect=lambda *a, **kw: call_order.append("restore")
        )

        clients = {"edge-node-1": hea, "cloud": hea}
        m = _make_migration(hea_clients=clients, flink_client=flink)

        await m.execute()

        assert call_order == ["drain", "snapshot", "restore", "terminate"]

    @pytest.mark.asyncio
    async def test_completed_true_on_success(self):
        """After a successful execute(), completed must be True."""
        m = _make_migration()
        await m.execute()
        assert m.completed is True

    @pytest.mark.asyncio
    async def test_error_none_on_success(self):
        """After a successful execute(), error must remain None."""
        m = _make_migration()
        await m.execute()
        assert m.error is None

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        """execute() returns True when all four phases succeed."""
        m = _make_migration()
        result = await m.execute()
        assert result is True

    @pytest.mark.asyncio
    async def test_snapshot_failure_sets_error_and_returns_false(self):
        """If phase 2 (snapshot) raises, error is set and execute() returns False."""
        hea = _mock_hea_client()
        hea.trigger_snapshot = AsyncMock(side_effect=RuntimeError("snapshot boom"))

        clients = {"edge-node-1": hea, "cloud": hea}
        m = _make_migration(hea_clients=clients)

        result = await m.execute()

        assert result is False
        assert m.error is not None
        assert "snapshot boom" in m.error

    @pytest.mark.asyncio
    async def test_terminate_failure_sets_error_and_returns_false(self):
        """If phase 4 (terminate) raises, error is set and execute() returns False."""
        hea = _mock_hea_client()
        hea.terminate_operator = AsyncMock(
            return_value=MagicMock(success=False, error_msg="terminate refused")
        )

        clients = {"edge-node-1": hea, "cloud": hea}
        m = _make_migration(hea_clients=clients)

        result = await m.execute()

        assert result is False
        assert m.error is not None

    @pytest.mark.asyncio
    async def test_snapshot_metadata_stored_after_phase_2(self):
        """snapshot_object_key and snapshot_size must be populated after phase 2."""
        m = _make_migration()
        await m.execute()

        assert m.snapshot_object_key == "snap-123"
        assert m.snapshot_size == 1024

    def test_get_status_returns_all_required_keys(self):
        """get_status() must return a dict with all nine documented keys."""
        m = _make_migration()
        status = m.get_status()

        required_keys = {
            "migration_id",
            "operator_id",
            "source_tier",
            "target_tier",
            "phase",
            "elapsed_s",
            "snapshot_size",
            "completed",
            "error",
        }
        assert required_keys.issubset(status.keys())


# ---------------------------------------------------------------------------
# TestPCTROrchestrator
# ---------------------------------------------------------------------------

class TestPCTROrchestrator:
    """Verify PCTROrchestrator manages concurrent migrations."""

    def _make_orchestrator(self):
        """Build a PCTROrchestrator with fully-mocked dependencies."""
        from aode.aode.config import AODEConfig
        from aode.aode.migration.pctr import PCTROrchestrator

        hea = _mock_hea_client()
        hea_clients = {
            "edge-node-1": hea,
            "edge-node-2": hea,
            "cloud": hea,
        }

        return PCTROrchestrator(
            config=AODEConfig(),
            hea_clients=hea_clients,
            flink_client=_mock_flink_client(),
            object_store=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_migrate_operator_returns_migration_id_string(self):
        """migrate_operator must return a non-empty string migration id."""
        orch = self._make_orchestrator()
        mid = await orch.migrate_operator("VehicleDetector", "edge-node-1", "cloud")

        assert isinstance(mid, str)
        assert len(mid) > 0

    @pytest.mark.asyncio
    async def test_raises_value_error_on_duplicate_concurrent_migration(self):
        """Starting a second migration for the same operator must raise ValueError."""
        orch = self._make_orchestrator()
        await orch.migrate_operator("VehicleDetector", "edge-node-1", "cloud")

        with pytest.raises(ValueError):
            await orch.migrate_operator("VehicleDetector", "edge-node-1", "cloud")

    def test_list_active_migrations_empty_initially(self):
        """A fresh orchestrator should have no active migrations."""
        orch = self._make_orchestrator()
        assert orch.list_active_migrations() == []

    @pytest.mark.asyncio
    async def test_list_active_migrations_returns_correct_count(self):
        """After two migrate_operator calls, list_active_migrations should have 2 entries."""
        orch = self._make_orchestrator()
        await orch.migrate_operator("VehicleDetector", "edge-node-1", "cloud")
        await orch.migrate_operator("ZoneAggregator", "edge-node-2", "cloud")

        active = orch.list_active_migrations()
        assert isinstance(active, list)
        assert len(active) == 2

    def test_get_migration_status_returns_none_for_unknown(self):
        """Querying an operator with no active migration should return None."""
        orch = self._make_orchestrator()
        assert orch.get_migration_status("NonExistentOp") is None

    @pytest.mark.asyncio
    async def test_migration_counter_increments(self):
        """First migration id is 'migration-0001', second is 'migration-0002'."""
        orch = self._make_orchestrator()

        mid1 = await orch.migrate_operator("VehicleDetector", "edge-node-1", "cloud")
        mid2 = await orch.migrate_operator("ZoneAggregator", "edge-node-2", "cloud")

        assert mid1 == "migration-0001"
        assert mid2 == "migration-0002"

    @pytest.mark.asyncio
    async def test_allows_re_migration_after_completion(self):
        """Once a migration is removed from _active_migrations the same operator can be migrated again."""
        orch = self._make_orchestrator()

        await orch.migrate_operator("VehicleDetector", "edge-node-1", "cloud")

        # Simulate completion by removing the operator from _active_migrations
        orch._active_migrations.pop("VehicleDetector", None)

        # Should not raise
        mid = await orch.migrate_operator("VehicleDetector", "edge-node-1", "cloud")
        assert isinstance(mid, str)
