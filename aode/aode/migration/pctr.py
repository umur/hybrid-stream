import asyncio
import logging
import json
import time
from typing import Dict, Optional, List
from enum import Enum

from ..config import AODEConfig

log = logging.getLogger(__name__)


class MigrationPhase(Enum):
    PHASE_1_DRAIN   = "drain"
    PHASE_2_SNAP    = "snapshot"
    PHASE_3_RESTORE = "restore"
    PHASE_4_TERM    = "terminate"


class PCTRMigration:
    def __init__(
        self,
        migration_id: str,
        operator_id: str,
        source_tier: str,
        target_tier: str,
        config: AODEConfig,
        hea_clients: Dict,
        flink_client,
        object_store,
    ) -> None:
        self.migration_id = migration_id
        self.operator_id = operator_id
        self.source_tier = source_tier
        self.target_tier = target_tier
        self._config = config
        self._hea_clients = hea_clients
        self._flink_client = flink_client
        self._object_store = object_store

        self.phase = MigrationPhase.PHASE_1_DRAIN
        self.start_time = time.monotonic()
        self.drain_offset_map: Dict[int, int] = {}
        self.snapshot_object_key: Optional[str] = None
        self.snapshot_size: int = 0
        self.completed: bool = False
        self.error: Optional[str] = None

    async def execute(self) -> bool:
        try:
            await self._phase_1_drain()
            await self._phase_2_snapshot()
            await self._phase_3_restore()
            await self._phase_4_terminate()
            self.completed = True
            return True
        except Exception as e:
            self.error = str(e)
            return False

    async def _phase_1_drain(self) -> None:
        self.phase = MigrationPhase.PHASE_1_DRAIN
        source_client = self._hea_clients.get(self.source_tier)
        if not source_client:
            raise ValueError(f"No HEA client for source tier: {self.source_tier}")
        response = await source_client.drain_operator(operator_id=self.operator_id)
        self.drain_offset_map = dict(getattr(response, 'offset_map', {}))

    async def _phase_2_snapshot(self) -> None:
        self.phase = MigrationPhase.PHASE_2_SNAP
        source_client = self._hea_clients.get(self.source_tier)
        if not source_client:
            raise ValueError(f"No HEA client for source tier: {self.source_tier}")
        migration_seq = int(time.time())
        response = await source_client.trigger_snapshot(
            operator_id=self.operator_id,
            migration_seq=migration_seq,
            drain_offset_map=json.dumps(self.drain_offset_map),
        )
        if response.error_msg:
            raise RuntimeError(f"Snapshot failed: {response.error_msg}")
        self.snapshot_object_key = response.object_key
        self.snapshot_size = response.byte_size

    async def _phase_3_restore(self) -> None:
        self.phase = MigrationPhase.PHASE_3_RESTORE
        if self.target_tier == "cloud":
            await self._flink_client.restore_operator(
                operator_id=self.operator_id,
                snapshot_key=self.snapshot_object_key,
            )
        else:
            target_client = self._hea_clients.get(self.target_tier)
            if not target_client:
                raise ValueError(f"No HEA client for target tier: {self.target_tier}")
            await asyncio.sleep(0.1)

    async def _phase_4_terminate(self) -> None:
        self.phase = MigrationPhase.PHASE_4_TERM
        source_client = self._hea_clients.get(self.source_tier)
        if not source_client:
            raise ValueError(f"No HEA client for source tier: {self.source_tier}")
        response = await source_client.terminate_operator(
            operator_id=self.operator_id,
            flush_state=True,
        )
        if not response.success:
            raise RuntimeError(f"Termination failed: {response.error_msg}")

    def get_status(self) -> Dict:
        elapsed = time.monotonic() - self.start_time
        return {
            "migration_id": self.migration_id,
            "operator_id": self.operator_id,
            "source_tier": self.source_tier,
            "target_tier": self.target_tier,
            "phase": self.phase.value,
            "elapsed_s": round(elapsed, 2),
            "snapshot_size": self.snapshot_size,
            "completed": self.completed,
            "error": self.error,
        }


class PCTROrchestrator:
    def __init__(self, config: AODEConfig, hea_clients: Dict, flink_client, object_store) -> None:
        self._config = config
        self._hea_clients = hea_clients
        self._flink_client = flink_client
        self._object_store = object_store
        self._active_migrations: Dict[str, PCTRMigration] = {}
        self._migration_counter: int = 0

    async def migrate_operator(self, operator_id: str, source_tier: str, target_tier: str) -> str:
        if operator_id in self._active_migrations:
            raise ValueError(f"Operator {operator_id} is already being migrated")
        self._migration_counter += 1
        migration_id = f"migration-{self._migration_counter:04d}"
        migration = PCTRMigration(
            migration_id=migration_id,
            operator_id=operator_id,
            source_tier=source_tier,
            target_tier=target_tier,
            config=self._config,
            hea_clients=self._hea_clients,
            flink_client=self._flink_client,
            object_store=self._object_store,
        )
        self._active_migrations[operator_id] = migration
        asyncio.create_task(self._execute_migration(migration))
        return migration_id

    async def _execute_migration(self, migration: PCTRMigration) -> None:
        try:
            timeout = self._config.migration_timeout_s
            await asyncio.wait_for(migration.execute(), timeout=timeout)
        except asyncio.TimeoutError:
            migration.error = f"Migration timed out after {timeout}s"
        finally:
            self._active_migrations.pop(migration.operator_id, None)

    def get_migration_status(self, operator_id: str) -> Optional[Dict]:
        migration = self._active_migrations.get(operator_id)
        return migration.get_status() if migration else None

    def list_active_migrations(self) -> List[Dict]:
        return [m.get_status() for m in self._active_migrations.values()]
