import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor

from . import hybridstream_pb2 as pb2
from . import hybridstream_pb2_grpc as pb2_grpc

log = logging.getLogger(__name__)


class AODEManagementServicer:
    def __init__(self, optimizer, placement_state, migration_orchestrator, scoring_algorithm) -> None:
        self._optimizer = optimizer
        self._placement = placement_state
        self._migration = migration_orchestrator
        self._scoring = scoring_algorithm

    def GetStatus(self, request, context):
        current_placement = self._placement.get_current_placement()
        optimizer_status = self._optimizer.get_status()
        active_migrations = self._migration.list_active_migrations()

        return pb2.AODEStatusResponse(
            instance_id="aode-1",
            is_leader=True,
            operators_managed=len(current_placement),
            active_migrations=len(active_migrations),
            last_recalibration_ago_s=optimizer_status.get("last_run_ago_s", 0),
            uptime_s=0,
        )

    def TriggerRecalibration(self, request, context):
        try:
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                self._optimizer.force_recalibration(reason=getattr(request, 'reason', None) or "manual"),
                loop
            )
            result = future.result(timeout=30)

            return pb2.RecalibrationResponse(
                success=True,
                migrations_started=result.get("migrations_started", 0),
                duration_ms=result.get("duration_ms", 0),
            )
        except Exception as e:
            log.error("TriggerRecalibration error: %s", e)
            return pb2.RecalibrationResponse(
                success=False,
                error_msg=str(e),
            )

    def UpdateWeights(self, request, context):
        try:
            self._scoring.set_weights(request.preset_name)
            return pb2.WeightUpdateResponse(success=True)
        except Exception as e:
            return pb2.WeightUpdateResponse(success=False, error_msg=str(e))

    def GetPlacementState(self, request, context):
        placement = self._placement.get_current_placement()
        return pb2.PlacementStateResponse(operator_to_tier=placement)


async def serve_management_api(port, optimizer, placement_state, migration_orchestrator, scoring_algorithm):
    import grpc
    server = grpc.aio.server(ThreadPoolExecutor(max_workers=1))
    pb2_grpc.add_AODEManagementServicer_to_server(
        AODEManagementServicer(optimizer, placement_state, migration_orchestrator, scoring_algorithm),
        server
    )
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    await server.wait_for_termination()
