"""Tests for aode.aode.grpc.clients — HEAClient and FlinkConnectorClient."""
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Mock protobuf modules before importing the client module, since the real
# proto stubs do not exist yet.
# ---------------------------------------------------------------------------
_mock_pb2 = MagicMock()
_mock_pb2.TelemetryRequest = lambda **kw: SimpleNamespace(**kw)
_mock_pb2.SnapshotRequest = lambda **kw: SimpleNamespace(**kw)
_mock_pb2.TerminateRequest = lambda **kw: SimpleNamespace(**kw)
_mock_pb2.PlacementDirective = lambda **kw: SimpleNamespace(**kw)
_mock_pb2.RestoreRequest = lambda **kw: SimpleNamespace(**kw)

_mock_pb2_grpc = MagicMock()


@pytest.fixture(autouse=True)
def _patch_proto():
    """Inject mock proto modules into sys.modules for every test."""
    with patch.dict(
        sys.modules,
        {
            "hybridstream": MagicMock(),
            "hybridstream.proto": MagicMock(),
            "hybridstream.proto.hybridstream_pb2": _mock_pb2,
            "hybridstream.proto.hybridstream_pb2_grpc": _mock_pb2_grpc,
        },
    ):
        sys.modules.pop("aode.aode.grpc.clients", None)
        yield


@pytest.fixture
def mock_channel():
    """Return a mock gRPC async channel."""
    channel = AsyncMock()
    channel.close = AsyncMock()
    return channel


@pytest.fixture
def mock_hea_stub():
    """Return a mock HEA gRPC stub with async RPC methods."""
    stub = MagicMock()
    stub.GetTelemetry = AsyncMock(
        return_value=SimpleNamespace(cpu_usage=0.65, memory_usage=0.42, queue_depth=120)
    )
    stub.ApplyPlacement = AsyncMock(
        return_value=SimpleNamespace(success=True)
    )
    stub.TriggerSnapshot = AsyncMock(
        return_value=SimpleNamespace(success=True, snapshot_path="s3://bucket/snap-001")
    )
    stub.TerminateOperator = AsyncMock(
        return_value=SimpleNamespace(success=True, drained=True)
    )
    return stub


@pytest.fixture
def mock_flink_stub():
    """Return a mock Flink connector gRPC stub."""
    stub = MagicMock()
    stub.RestoreOperator = AsyncMock(
        return_value=SimpleNamespace(success=True, restored_keys=42)
    )
    return stub


# ---------------------------------------------------------------------------
# TestHEAClientGetTelemetry
# ---------------------------------------------------------------------------


class TestHEAClientGetTelemetry:
    """Verify get_telemetry calls the stub correctly."""

    @pytest.mark.asyncio
    async def test_calls_get_telemetry_on_stub(self, mock_channel, mock_hea_stub):
        """get_telemetry must invoke GetTelemetry on the underlying stub."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel):
            from aode.aode.grpc.clients import HEAClient

            client = HEAClient(endpoint="edge-node-1:50051")
            await client.connect()
            client._stub = mock_hea_stub

            response = await client.get_telemetry()

            mock_hea_stub.GetTelemetry.assert_awaited_once()
            assert response.cpu_usage == 0.65

    @pytest.mark.asyncio
    async def test_get_telemetry_uses_timeout_5(self, mock_channel, mock_hea_stub):
        """get_telemetry must pass timeout=5 to the stub call."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel):
            from aode.aode.grpc.clients import HEAClient

            client = HEAClient(endpoint="edge-node-1:50051")
            await client.connect()
            client._stub = mock_hea_stub

            await client.get_telemetry()

            call_kwargs = mock_hea_stub.GetTelemetry.call_args
            assert call_kwargs.kwargs.get("timeout") == 5 or (
                len(call_kwargs.args) > 1 and call_kwargs.args[1] == 5
            )


# ---------------------------------------------------------------------------
# TestHEAClientTriggerSnapshot
# ---------------------------------------------------------------------------


class TestHEAClientTriggerSnapshot:
    """Verify trigger_snapshot passes the correct parameters."""

    @pytest.mark.asyncio
    async def test_passes_operator_id_and_migration_seq(
        self, mock_channel, mock_hea_stub
    ):
        """Request must contain operator_id and migration_seq."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel):
            from aode.aode.grpc.clients import HEAClient

            client = HEAClient(endpoint="edge-node-1:50051")
            await client.connect()
            client._stub = mock_hea_stub

            await client.trigger_snapshot(
                operator_id="op-1",
                migration_seq=42,
                drain_offset_map={"partition-0": 1000},
            )

            call_args = mock_hea_stub.TriggerSnapshot.call_args
            request = call_args[0][0] if call_args[0] else call_args[1].get("request")
            assert request.operator_id == "op-1"
            assert request.migration_seq == 42

    @pytest.mark.asyncio
    async def test_trigger_snapshot_uses_timeout_30(
        self, mock_channel, mock_hea_stub
    ):
        """trigger_snapshot must pass timeout=30 to the stub call."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel):
            from aode.aode.grpc.clients import HEAClient

            client = HEAClient(endpoint="edge-node-1:50051")
            await client.connect()
            client._stub = mock_hea_stub

            await client.trigger_snapshot(
                operator_id="op-1",
                migration_seq=1,
                drain_offset_map={},
            )

            call_kwargs = mock_hea_stub.TriggerSnapshot.call_args
            assert call_kwargs.kwargs.get("timeout") == 30 or (
                len(call_kwargs.args) > 1 and call_kwargs.args[1] == 30
            )


# ---------------------------------------------------------------------------
# TestHEAClientTerminateOperator
# ---------------------------------------------------------------------------


class TestHEAClientTerminateOperator:
    """Verify terminate_operator passes the flush_state flag."""

    @pytest.mark.asyncio
    async def test_passes_operator_id_and_flush_state(
        self, mock_channel, mock_hea_stub
    ):
        """Request must contain operator_id and flush_state."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel):
            from aode.aode.grpc.clients import HEAClient

            client = HEAClient(endpoint="edge-node-1:50051")
            await client.connect()
            client._stub = mock_hea_stub

            await client.terminate_operator(operator_id="op-2", flush_state=True)

            call_args = mock_hea_stub.TerminateOperator.call_args
            request = call_args[0][0] if call_args[0] else call_args[1].get("request")
            assert request.operator_id == "op-2"
            assert request.flush_state is True

    @pytest.mark.asyncio
    async def test_terminate_operator_uses_timeout_10(
        self, mock_channel, mock_hea_stub
    ):
        """terminate_operator must pass timeout=10 to the stub call."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel):
            from aode.aode.grpc.clients import HEAClient

            client = HEAClient(endpoint="edge-node-1:50051")
            await client.connect()
            client._stub = mock_hea_stub

            await client.terminate_operator(operator_id="op-2", flush_state=False)

            call_kwargs = mock_hea_stub.TerminateOperator.call_args
            assert call_kwargs.kwargs.get("timeout") == 10 or (
                len(call_kwargs.args) > 1 and call_kwargs.args[1] == 10
            )


# ---------------------------------------------------------------------------
# TestHEAClientLifecycle
# ---------------------------------------------------------------------------


class TestHEAClientLifecycle:
    """Verify connect and close manage the gRPC channel."""

    @pytest.mark.asyncio
    async def test_connect_creates_channel(self, mock_channel):
        """connect() must create a gRPC insecure channel to the endpoint."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel) as mock_create:
            from aode.aode.grpc.clients import HEAClient

            client = HEAClient(endpoint="edge-node-1:50051")
            await client.connect()

            mock_create.assert_called_once_with("edge-node-1:50051")

    @pytest.mark.asyncio
    async def test_close_shuts_channel(self, mock_channel):
        """close() must call close() on the underlying channel."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel):
            from aode.aode.grpc.clients import HEAClient

            client = HEAClient(endpoint="edge-node-1:50051")
            await client.connect()
            await client.close()

            mock_channel.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# TestFlinkConnectorClient
# ---------------------------------------------------------------------------


class TestFlinkConnectorClient:
    """Verify FlinkConnectorClient restore_operator and lifecycle."""

    @pytest.mark.asyncio
    async def test_restore_operator_passes_params(self, mock_channel, mock_flink_stub):
        """restore_operator must pass operator_id and snapshot_object_key in request."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel):
            from aode.aode.grpc.clients import FlinkConnectorClient

            client = FlinkConnectorClient(endpoint="flink-cluster:50052")
            await client.connect()
            client._stub = mock_flink_stub

            response = await client.restore_operator(
                operator_id="op-3",
                snapshot_key="snapshots/op-3/seq-5.bin",
            )

            mock_flink_stub.RestoreOperator.assert_awaited_once()
            call_args = mock_flink_stub.RestoreOperator.call_args
            request = call_args[0][0] if call_args[0] else call_args[1].get("request")
            assert request.operator_id == "op-3"
            assert request.snapshot_key == "snapshots/op-3/seq-5.bin"
            assert response.success is True

    @pytest.mark.asyncio
    async def test_connect_creates_channel(self, mock_channel):
        """connect() must create a gRPC insecure channel to the endpoint."""
        with patch("grpc.aio.insecure_channel", return_value=mock_channel) as mock_create:
            from aode.aode.grpc.clients import FlinkConnectorClient

            client = FlinkConnectorClient(endpoint="flink-cluster:50052")
            await client.connect()

            mock_create.assert_called_once_with("flink-cluster:50052")
