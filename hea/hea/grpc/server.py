import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import grpc

from . import hybridstream_pb2 as pb2
from . import hybridstream_pb2_grpc as pb2_grpc

from ..execution.engine import OperatorEngine
from ..state.snapshot import create_migration_snapshot
from ..operator_registry import get as get_operator_class
from ..metrics import HEAMetrics
from ..config import HEAConfig
from hybridstream.common.schema_registry import SchemaRegistry
from hybridstream.common.object_store import ObjectStore
from hybridstream.common.snapshot import deserialize

log = logging.getLogger(__name__)


class HEAManagementServicer(pb2_grpc.HEAManagementServicer):

    def __init__(
        self,
        config: HEAConfig,
        engine: OperatorEngine,
        metrics: HEAMetrics,
        schema_registry: SchemaRegistry,
        object_store: ObjectStore,
    ):
        self._config   = config
        self._engine   = engine
        self._metrics  = metrics
        self._registry = schema_registry
        self._store    = object_store

    def GetTelemetry(self, request, context):
        p95 = self._metrics.get_operator_p95()
        return pb2.TelemetryResponse(
            hea_id             = self._config.node_id,
            cpu_utilization    = self._metrics.cpu_utilization,
            memory_utilization = self._metrics.memory_utilization,
            ingest_rate_eps    = self._metrics.ingest_rate_eps,
            operator_p95_ms    = p95,
            timestamp_ms       = int(asyncio.get_event_loop().time() * 1000),
            reachable          = True,
        )

    def ApplyPlacement(self, request, context):
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self._apply_placement_async(request)
            )
            return pb2.PlacementAck(directive_id=request.directive_id, accepted=True)
        except Exception as e:
            log.error("ApplyPlacement error: %s", e)
            return pb2.PlacementAck(directive_id=request.directive_id, accepted=False, error_msg=str(e))

    async def _apply_placement_async(self, request) -> None:
        my_id = self._config.node_id
        for operator_id, tier_id in request.operator_to_tier.items():
            if tier_id == my_id:
                if operator_id not in self._engine._operators:
                    log.info("Instantiating operator %s on %s", operator_id, my_id)
            else:
                if operator_id in self._engine._operators:
                    await self._engine.deregister_operator(operator_id)

    def TriggerSnapshot(self, request, context):
        try:
            operator = self._engine._operators.get(request.operator_id)
            if not operator:
                return pb2.SnapshotResponse(
                    operator_id=request.operator_id,
                    error_msg=f"Operator {request.operator_id} not found on this HEA"
                )
            import json
            drain_offsets = json.loads(request.drain_offset_map) if request.drain_offset_map else {}
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                create_migration_snapshot(
                    operator, self._registry, self._store,
                    request.migration_seq, drain_offsets
                ),
                loop
            )
            object_key, byte_size = future.result(timeout=30)
            return pb2.SnapshotResponse(
                operator_id    = request.operator_id,
                object_key     = object_key,
                byte_size      = byte_size,
                schema_version = 1,
            )
        except Exception as e:
            log.error("TriggerSnapshot error for %s: %s", request.operator_id, e)
            return pb2.SnapshotResponse(operator_id=request.operator_id, error_msg=str(e))

    def TerminateOperator(self, request, context):
        try:
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                self._engine.deregister_operator(request.operator_id, flush_state=request.flush_state),
                loop
            )
            future.result(timeout=10)
            return pb2.TerminateAck(operator_id=request.operator_id, success=True)
        except Exception as e:
            log.error("TerminateOperator error for %s: %s", request.operator_id, e)
            return pb2.TerminateAck(operator_id=request.operator_id, success=False, error_msg=str(e))


async def serve(config: HEAConfig, engine: OperatorEngine, metrics: HEAMetrics,
                schema_registry: SchemaRegistry, object_store: ObjectStore) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    pb2_grpc.add_HEAManagementServicer_to_server(
        HEAManagementServicer(config, engine, metrics, schema_registry, object_store),
        server
    )
    server.add_insecure_port(f"[::]:{config.grpc_port}")
    server.start()
    log.info("HEA gRPC server listening on port %d", config.grpc_port)
    server.wait_for_termination()
