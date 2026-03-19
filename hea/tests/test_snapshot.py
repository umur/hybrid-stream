"""Tests for hea.hea.state.snapshot — create_migration_snapshot."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


def _make_operator(op_id: str = "op1", op_type: str = "FilterOperator", state: dict | None = None):
    """Create a mock operator with controllable state."""
    from hea.hea.execution.base_operator import BaseOperator

    state = state or {"window_size": 100, "threshold": 0.5}

    class FakeOp(BaseOperator):
        operator_id = op_id
        operator_type = op_type

        async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
            return []

        def get_state(self) -> dict[str, Any]:
            return dict(state)

        def restore_state(self, s: dict[str, Any]) -> None:
            pass

    return FakeOp()


@pytest.fixture
def mock_schema_registry():
    registry = MagicMock()
    registry.get_schema.return_value = {
        "schema_version": 1,
        "operator_class": "FilterOperator",
        "fields": [
            {"name": "window_size", "type": "int"},
            {"name": "threshold", "type": "float"},
            {"name": "kafka_offset_map", "type": "map"},
        ],
    }
    return registry


@pytest.fixture
def mock_object_store():
    store = AsyncMock()
    store.upload = AsyncMock(return_value=256)
    return store


class TestCreateMigrationSnapshot:

    @pytest.mark.asyncio
    async def test_serializes_state_with_kafka_offsets(self, mock_schema_registry, mock_object_store):
        from hea.hea.state.snapshot import create_migration_snapshot

        op = _make_operator()
        drain_offsets = {0: 1000, 1: 2000}

        object_key, byte_size = await create_migration_snapshot(
            operator=op,
            schema_registry=mock_schema_registry,
            object_store=mock_object_store,
            migration_seq=1,
            drain_offset_map=drain_offsets,
        )

        assert object_key == "op1/1/snapshot.msgpack"
        assert byte_size == 256

    @pytest.mark.asyncio
    async def test_upload_called_with_correct_key(self, mock_schema_registry, mock_object_store):
        from hea.hea.state.snapshot import create_migration_snapshot

        op = _make_operator(op_id="myop", op_type="FilterOperator")

        await create_migration_snapshot(
            operator=op,
            schema_registry=mock_schema_registry,
            object_store=mock_object_store,
            migration_seq=42,
            drain_offset_map={},
        )

        mock_object_store.upload.assert_called_once()
        call_args = mock_object_store.upload.call_args
        assert call_args[0][0] == "myop/42/snapshot.msgpack"

    @pytest.mark.asyncio
    async def test_output_has_hsmp_magic_bytes(self, mock_schema_registry, mock_object_store):
        from hea.hea.state.snapshot import create_migration_snapshot
        from hybridstream.common.snapshot import MAGIC

        uploaded_bytes = None

        async def capture_upload(key, data):
            nonlocal uploaded_bytes
            uploaded_bytes = data
            return len(data)

        mock_object_store.upload = AsyncMock(side_effect=capture_upload)

        op = _make_operator()
        await create_migration_snapshot(
            operator=op,
            schema_registry=mock_schema_registry,
            object_store=mock_object_store,
            migration_seq=1,
            drain_offset_map={},
        )

        assert uploaded_bytes is not None
        assert uploaded_bytes[:4] == MAGIC

    @pytest.mark.asyncio
    async def test_state_lossless_roundtrip(self, mock_schema_registry, mock_object_store):
        from hea.hea.state.snapshot import create_migration_snapshot
        from hybridstream.common.snapshot import deserialize

        uploaded_bytes = None

        async def capture_upload(key, data):
            nonlocal uploaded_bytes
            uploaded_bytes = data
            return len(data)

        mock_object_store.upload = AsyncMock(side_effect=capture_upload)

        original_state = {"window_size": 100, "threshold": 0.5}
        op = _make_operator(state=original_state)
        drain_offsets = {0: 500}

        await create_migration_snapshot(
            operator=op,
            schema_registry=mock_schema_registry,
            object_store=mock_object_store,
            migration_seq=1,
            drain_offset_map=drain_offsets,
        )

        assert uploaded_bytes is not None
        restored = deserialize(uploaded_bytes, mock_schema_registry)
        assert restored["window_size"] == 100
        assert restored["threshold"] == 0.5
        assert restored["kafka_offset_map"] == drain_offsets

    @pytest.mark.asyncio
    async def test_drain_offset_embedded_in_state(self, mock_schema_registry, mock_object_store):
        from hea.hea.state.snapshot import create_migration_snapshot
        from hybridstream.common.snapshot import serialize

        captured_args = {}

        def mock_serialize(op_type, state, registry):
            captured_args["state"] = dict(state)
            return b"\x48\x53\x4d\x50\x00\x01" + b"\x80"

        with patch("hea.hea.state.snapshot.serialize", side_effect=mock_serialize):
            op = _make_operator()
            await create_migration_snapshot(
                operator=op,
                schema_registry=mock_schema_registry,
                object_store=mock_object_store,
                migration_seq=1,
                drain_offset_map={0: 999},
            )

        assert captured_args["state"]["kafka_offset_map"] == {0: 999}
