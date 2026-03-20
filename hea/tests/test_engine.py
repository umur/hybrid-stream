"""Tests for hea.hea.execution.engine — OperatorEngine."""
import asyncio
import pytest
import msgpack
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


def _make_io_operator(op_id="io_op", op_type="IOOp"):
    from hea.hea.execution.base_operator import BaseOperator

    class IOOp(BaseOperator):
        operator_id = op_id
        operator_type = op_type

        def __init__(self):
            self.processed = []

        async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
            self.processed.append(record)
            return [{"out": True}]

        def get_state(self) -> dict[str, Any]:
            return {}

        def restore_state(self, state: dict[str, Any]) -> None:
            pass

    return IOOp()


def _make_cpu_operator(op_id="cpu_op", op_type="CPUOp"):
    from hea.hea.execution.base_operator import BaseOperator
    from hea.hea.execution.decorators import cpu_bound

    @cpu_bound
    class CPUOp(BaseOperator):
        operator_id = op_id
        operator_type = op_type

        async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
            return [{"result": sum(record.values())}]

        def get_state(self) -> dict[str, Any]:
            return {}

        def restore_state(self, state: dict[str, Any]) -> None:
            pass

    return CPUOp()


def _make_engine():
    from hea.hea.execution.engine import OperatorEngine
    config = MagicMock(
        kafka_bootstrap="localhost:9092",
        kafka_batch_size=500,
        kafka_group_prefix="test",
        backpressure_high_water=6,
        backpressure_low_water=2,
        node_id="test-node",
    )
    metrics = MagicMock()
    bridge = MagicMock()
    bridge.send = AsyncMock()
    return OperatorEngine(config, metrics, bridge), config, metrics, bridge


class TestRegisterOperator:

    @pytest.mark.asyncio
    async def test_register_adds_to_operators_dict(self):
        engine, *_ = _make_engine()
        await engine.start()

        op = _make_io_operator()
        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op, ["input-topic"], ["output-topic"])

        assert "io_op" in engine._operators
        assert engine._operators["io_op"] is op
        await engine.stop()

    @pytest.mark.asyncio
    async def test_register_sets_output_routes(self):
        engine, *_ = _make_engine()
        await engine.start()

        op = _make_io_operator()
        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op, ["in"], ["out1", "out2"])

        assert engine._output_routes["io_op"] == ["out1", "out2"]
        await engine.stop()

    @pytest.mark.asyncio
    async def test_register_sets_topic_bindings(self):
        engine, *_ = _make_engine()
        await engine.start()

        op = _make_io_operator()
        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op, ["topic-a", "topic-b"], [])

        assert "io_op" in engine._topic_bindings["topic-a"]
        assert "io_op" in engine._topic_bindings["topic-b"]
        await engine.stop()


class TestDeregisterOperator:

    @pytest.mark.asyncio
    async def test_deregister_removes_from_operators(self):
        engine, *_ = _make_engine()
        await engine.start()

        op = _make_io_operator()
        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op, ["in"], ["out"])
        await engine.deregister_operator("io_op")

        assert "io_op" not in engine._operators
        await engine.stop()

    @pytest.mark.asyncio
    async def test_deregister_nonexistent_is_noop(self):
        engine, *_ = _make_engine()
        await engine.start()
        await engine.deregister_operator("ghost_op")  # should not raise
        await engine.stop()


class TestDeserializeRecord:

    def test_unpacks_msgpack_correctly(self):
        from hea.hea.execution.engine import OperatorEngine
        data = {"key": "value", "count": 42}
        packed = msgpack.packb(data, use_bin_type=True)
        result = OperatorEngine._deserialize_record(packed)
        assert result == data

    def test_handles_nested_structures(self):
        from hea.hea.execution.engine import OperatorEngine
        data = {"nested": {"a": [1, 2, 3]}, "flag": True}
        packed = msgpack.packb(data, use_bin_type=True)
        result = OperatorEngine._deserialize_record(packed)
        assert result == data


class TestCpuBoundDetection:

    def test_cpu_bound_operator_detected(self):
        from hea.hea.execution.decorators import is_cpu_bound
        op = _make_cpu_operator()
        assert is_cpu_bound(type(op)) is True

    def test_io_bound_operator_not_cpu_bound(self):
        from hea.hea.execution.decorators import is_cpu_bound
        op = _make_io_operator()
        assert is_cpu_bound(type(op)) is False

    @pytest.mark.asyncio
    async def test_cpu_bound_op_gets_worker_queue(self):
        engine, *_ = _make_engine()
        await engine.start()

        op = _make_cpu_operator()
        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op, ["in"], ["out"])

        assert "cpu_op" in engine._worker_queues
        await engine.stop()


class TestStartStopLifecycle:

    @pytest.mark.asyncio
    async def test_start_creates_process_pool(self):
        engine, *_ = _make_engine()
        assert engine._pool is None
        await engine.start()
        assert engine._pool is not None
        await engine.stop()

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self):
        engine, *_ = _make_engine()
        assert engine._running is False
        await engine.start()
        assert engine._running is True
        await engine.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self):
        engine, *_ = _make_engine()
        await engine.start()
        await engine.stop()
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_stop_shuts_down_pool(self):
        engine, *_ = _make_engine()
        await engine.start()
        pool = engine._pool
        await engine.stop()
        # After shutdown, the pool's _broken flag is set or it is no longer accepting
        assert pool._broken or pool._shutdown_thread


class TestDeregisterOperatorNoOp:

    @pytest.mark.asyncio
    async def test_deregister_nonexistent_operator_does_not_raise(self):
        engine, *_ = _make_engine()
        await engine.start()
        # Should complete without raising any exception
        await engine.deregister_operator("does_not_exist")
        await engine.stop()

    @pytest.mark.asyncio
    async def test_deregister_nonexistent_operator_leaves_state_intact(self):
        engine, *_ = _make_engine()
        await engine.start()

        op = _make_io_operator()
        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op, ["in"], ["out"])

        # Deregister a ghost; real operator must survive
        await engine.deregister_operator("ghost_op")
        assert "io_op" in engine._operators
        await engine.stop()


class TestDeserializeRecordValid:

    def test_deserializes_simple_dict(self):
        from hea.hea.execution.engine import OperatorEngine
        payload = {"sensor": "s01", "value": 3.14}
        packed = __import__("msgpack").packb(payload, use_bin_type=True)
        result = OperatorEngine._deserialize_record(packed)
        assert result == payload

    def test_deserializes_integer_values(self):
        from hea.hea.execution.engine import OperatorEngine
        payload = {"count": 0, "offset": 9_999_999}
        packed = __import__("msgpack").packb(payload, use_bin_type=True)
        result = OperatorEngine._deserialize_record(packed)
        assert result["count"] == 0
        assert result["offset"] == 9_999_999

    def test_deserializes_boolean_values(self):
        from hea.hea.execution.engine import OperatorEngine
        payload = {"active": True, "error": False}
        packed = __import__("msgpack").packb(payload, use_bin_type=True)
        result = OperatorEngine._deserialize_record(packed)
        assert result["active"] is True
        assert result["error"] is False


class TestRegisterOperatorCallsOnStart:

    @pytest.mark.asyncio
    async def test_register_calls_on_start(self):
        engine, *_ = _make_engine()
        await engine.start()

        op = _make_io_operator()
        op.on_start = MagicMock()

        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op, ["in"], ["out"])

        op.on_start.assert_called_once()
        await engine.stop()

    @pytest.mark.asyncio
    async def test_register_multiple_operators_each_calls_on_start(self):
        engine, *_ = _make_engine()
        await engine.start()

        op1 = _make_io_operator("op1", "IOOp1")
        op2 = _make_io_operator("op2", "IOOp2")
        op1.on_start = MagicMock()
        op2.on_start = MagicMock()

        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op1, ["in"], ["out"])
            await engine.register_operator(op2, ["in"], ["out"])

        op1.on_start.assert_called_once()
        op2.on_start.assert_called_once()
        await engine.stop()


class TestBackpressure:

    @pytest.mark.asyncio
    async def test_queue_depth_above_high_water_pauses_consumer(self):
        engine, config, _, _ = _make_engine()
        config.backpressure_high_water = 3
        config.backpressure_low_water = 1
        await engine.start()

        op = _make_cpu_operator()
        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op, ["test-topic"], ["out"])

        # Manually fill the worker queue beyond high_water
        q = engine._worker_queues["cpu_op"]
        for i in range(5):
            await q.put(("dummy", {}, 0, 0))

        # Mock the consumer
        mock_consumer = MagicMock()
        mock_consumer.pause = MagicMock()
        mock_consumer.stop = AsyncMock()
        mock_consumer.assignment = MagicMock(return_value=set())
        engine._consumers["test-topic"] = mock_consumer

        await engine._check_backpressure("test-topic")

        mock_consumer.pause.assert_called_once()
        assert "test-topic" in engine._paused_topics
        await engine.stop()

    @pytest.mark.asyncio
    async def test_queue_depth_below_low_water_resumes_consumer(self):
        engine, config, _, _ = _make_engine()
        config.backpressure_high_water = 3
        config.backpressure_low_water = 1
        await engine.start()

        op = _make_cpu_operator()
        with patch.object(engine, "_start_consumer", new_callable=AsyncMock):
            await engine.register_operator(op, ["test-topic"], ["out"])

        # Simulate already paused state with empty queue
        engine._paused_topics.add("test-topic")
        mock_consumer = MagicMock()
        mock_consumer.resume = MagicMock()
        mock_consumer.stop = AsyncMock()
        mock_consumer.assignment = MagicMock(return_value=set())
        engine._consumers["test-topic"] = mock_consumer

        # Queue is empty (depth 0 < low_water 1)
        await engine._check_backpressure("test-topic")

        mock_consumer.resume.assert_called_once()
        assert "test-topic" not in engine._paused_topics
        await engine.stop()
