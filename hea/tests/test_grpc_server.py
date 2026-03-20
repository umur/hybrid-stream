"""Tests for hea.hea.grpc.server — HEAManagementServicer with mocked deps."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any


def _make_operator(op_id="op1"):
    from hea.hea.execution.base_operator import BaseOperator

    class FakeOp(BaseOperator):
        operator_id = op_id
        operator_type = "FakeOp"

        async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
            return []

        def get_state(self) -> dict[str, Any]:
            return {"count": 10}

        def restore_state(self, state: dict[str, Any]) -> None:
            pass

    return FakeOp()


def _make_servicer(operators=None):
    """Create a HEAManagementServicer with fully mocked dependencies."""
    from hea.hea.grpc.server import HEAManagementServicer

    config = MagicMock()
    config.node_id = "test-node-1"

    metrics = MagicMock()
    metrics.cpu_utilization = 0.45
    metrics.memory_utilization = 0.60
    metrics.ingest_rate_eps = 1500.0
    metrics.get_operator_p95.return_value = {"op1": 12.5}

    engine = MagicMock()
    engine._operators = operators or {}
    engine.deregister_operator = AsyncMock()

    schema_registry = MagicMock()
    object_store = MagicMock()

    servicer = HEAManagementServicer(
        config=config,
        engine=engine,
        metrics=metrics,
        schema_registry=schema_registry,
        object_store=object_store,
    )
    return servicer, config, engine, metrics


# --- Mock protobuf message classes ---

class MockTelemetryResponse:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockPlacementAck:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockSnapshotResponse:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockTerminateAck:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestGetTelemetry:

    def test_returns_all_required_fields(self):
        servicer, config, engine, metrics = _make_servicer()

        mock_pb2 = MagicMock()
        mock_pb2.TelemetryResponse = MockTelemetryResponse

        with patch("hea.hea.grpc.server.pb2", mock_pb2), \
             patch("hea.hea.grpc.server.asyncio") as mock_asyncio:
            mock_loop = MagicMock()
            mock_loop.time.return_value = 1000.0
            mock_asyncio.get_event_loop.return_value = mock_loop

            result = servicer.GetTelemetry(MagicMock(), MagicMock())

        assert result.hea_id == "test-node-1"
        assert result.cpu_utilization == 0.45
        assert result.memory_utilization == 0.60
        assert result.ingest_rate_eps == 1500.0

    def test_includes_operator_p95(self):
        servicer, *_ = _make_servicer()
        mock_pb2 = MagicMock()
        mock_pb2.TelemetryResponse = MockTelemetryResponse

        with patch("hea.hea.grpc.server.pb2", mock_pb2), \
             patch("hea.hea.grpc.server.asyncio") as mock_asyncio:
            mock_loop = MagicMock()
            mock_loop.time.return_value = 1000.0
            mock_asyncio.get_event_loop.return_value = mock_loop

            result = servicer.GetTelemetry(MagicMock(), MagicMock())

        assert result.operator_p95_ms == {"op1": 12.5}

    def test_returns_timestamp(self):
        servicer, *_ = _make_servicer()
        mock_pb2 = MagicMock()
        mock_pb2.TelemetryResponse = MockTelemetryResponse

        with patch("hea.hea.grpc.server.pb2", mock_pb2), \
             patch("hea.hea.grpc.server.time") as mock_time:
            mock_time.time.return_value = 5.5

            result = servicer.GetTelemetry(MagicMock(), MagicMock())

        assert result.timestamp_ms == 5500


class TestTriggerSnapshot:

    def test_returns_object_key_and_byte_size(self):
        op = _make_operator("snap_op")
        servicer, *_ = _make_servicer(operators={"snap_op": op})

        request = MagicMock()
        request.operator_id = "snap_op"
        request.migration_seq = 1
        request.drain_offset_map = '{"0": 100}'

        mock_pb2 = MagicMock()
        mock_pb2.SnapshotResponse = MockSnapshotResponse

        mock_future = MagicMock()
        mock_future.result.return_value = ("snap_op/1/snapshot.msgpack", 512)

        with patch("hea.hea.grpc.server.pb2", mock_pb2), \
             patch("hea.hea.grpc.server.asyncio") as mock_asyncio, \
             patch("hea.hea.grpc.server.create_migration_snapshot") as mock_snapshot:
            mock_loop = MagicMock()
            mock_asyncio.get_event_loop.return_value = mock_loop
            mock_asyncio.run_coroutine_threadsafe.return_value = mock_future

            result = servicer.TriggerSnapshot(request, MagicMock())

        assert result.object_key == "snap_op/1/snapshot.msgpack"
        assert result.byte_size == 512
        assert result.schema_version == 1

    def test_returns_error_for_unknown_operator(self):
        servicer, *_ = _make_servicer(operators={})

        request = MagicMock()
        request.operator_id = "nonexistent"

        mock_pb2 = MagicMock()
        mock_pb2.SnapshotResponse = MockSnapshotResponse

        with patch("hea.hea.grpc.server.pb2", mock_pb2):
            result = servicer.TriggerSnapshot(request, MagicMock())

        assert "not found" in result.error_msg


class TestTerminateOperator:

    def test_returns_success_for_known_operator(self):
        op = _make_operator("term_op")
        servicer, _, engine, _ = _make_servicer(operators={"term_op": op})

        request = MagicMock()
        request.operator_id = "term_op"
        request.flush_state = True

        mock_pb2 = MagicMock()
        mock_pb2.TerminateAck = MockTerminateAck

        mock_future = MagicMock()
        mock_future.result.return_value = None

        with patch("hea.hea.grpc.server.pb2", mock_pb2), \
             patch("hea.hea.grpc.server.asyncio") as mock_asyncio:
            mock_loop = MagicMock()
            mock_asyncio.get_event_loop.return_value = mock_loop
            mock_asyncio.run_coroutine_threadsafe.return_value = mock_future

            result = servicer.TerminateOperator(request, MagicMock())

        assert result.success is True
        assert result.operator_id == "term_op"

    def test_returns_failure_on_exception(self):
        servicer, _, engine, _ = _make_servicer(operators={})

        request = MagicMock()
        request.operator_id = "fail_op"
        request.flush_state = True

        mock_pb2 = MagicMock()
        mock_pb2.TerminateAck = MockTerminateAck

        mock_future = MagicMock()
        mock_future.result.side_effect = RuntimeError("deregister failed")

        with patch("hea.hea.grpc.server.pb2", mock_pb2), \
             patch("hea.hea.grpc.server.asyncio") as mock_asyncio:
            mock_loop = MagicMock()
            mock_asyncio.get_event_loop.return_value = mock_loop
            mock_asyncio.run_coroutine_threadsafe.return_value = mock_future

            result = servicer.TerminateOperator(request, MagicMock())

        assert result.success is False


class TestApplyPlacement:

    def test_returns_accepted_true(self):
        servicer, *_ = _make_servicer()

        request = MagicMock()
        request.directive_id = "dir-001"
        request.operator_to_tier = {}

        mock_pb2 = MagicMock()
        mock_pb2.PlacementAck = MockPlacementAck

        with patch("hea.hea.grpc.server.pb2", mock_pb2), \
             patch("hea.hea.grpc.server.asyncio") as mock_asyncio:
            mock_loop = MagicMock()
            mock_asyncio.get_event_loop.return_value = mock_loop

            result = servicer.ApplyPlacement(request, MagicMock())

        assert result.accepted is True
        assert result.directive_id == "dir-001"
