import sys

import grpc
from typing import Optional

pb2 = sys.modules.get("hybridstream.proto.hybridstream_pb2") or __import__(
    "hybridstream.proto.hybridstream_pb2", fromlist=["hybridstream_pb2"]
)
pb2_grpc = sys.modules.get("hybridstream.proto.hybridstream_pb2_grpc") or __import__(
    "hybridstream.proto.hybridstream_pb2_grpc", fromlist=["hybridstream_pb2_grpc"]
)


class HEAClient:
    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub = None

    async def connect(self) -> None:
        self._channel = grpc.aio.insecure_channel(self._endpoint)
        self._stub = pb2_grpc.HEAManagementStub(self._channel)

    async def close(self) -> None:
        if self._channel:
            await self._channel.close()

    async def get_telemetry(self):
        request = pb2.TelemetryRequest()
        return await self._stub.GetTelemetry(request, timeout=5)

    async def apply_placement(self, directive_id: str, operator_to_tier: dict):
        request = pb2.PlacementDirective(
            directive_id=directive_id,
            operator_to_tier=operator_to_tier,
        )
        return await self._stub.ApplyPlacement(request, timeout=10)

    async def trigger_snapshot(self, operator_id: str, migration_seq: int, drain_offset_map):
        request = pb2.SnapshotRequest(
            operator_id=operator_id,
            migration_seq=migration_seq,
            drain_offset_map=drain_offset_map,
        )
        return await self._stub.TriggerSnapshot(request, timeout=30)

    async def terminate_operator(self, operator_id: str, flush_state: bool = True):
        request = pb2.TerminateRequest(
            operator_id=operator_id,
            flush_state=flush_state,
        )
        return await self._stub.TerminateOperator(request, timeout=10)


class FlinkConnectorClient:
    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub = None

    async def connect(self) -> None:
        self._channel = grpc.aio.insecure_channel(self._endpoint)
        self._stub = pb2_grpc.FlinkConnectorStub(self._channel)

    async def close(self) -> None:
        if self._channel:
            await self._channel.close()

    async def restore_operator(self, operator_id: str, snapshot_key: str):
        request = pb2.RestoreRequest(
            operator_id=operator_id,
            snapshot_key=snapshot_key,
        )
        return await self._stub.RestoreOperator(request, timeout=60)
