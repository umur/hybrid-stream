import logging
from hybridstream.common.schema_registry import SchemaRegistry
from hybridstream.common.snapshot import serialize
from hybridstream.common.object_store import ObjectStore
from ..execution.base_operator import BaseOperator

log = logging.getLogger(__name__)


async def create_migration_snapshot(
    operator: BaseOperator,
    schema_registry: SchemaRegistry,
    object_store: ObjectStore,
    migration_seq: int,
    drain_offset_map: dict[int, int],
) -> tuple[str, int]:
    state = operator.get_state()
    state["kafka_offset_map"] = drain_offset_map

    msgpack_bytes = serialize(operator.operator_type, state, schema_registry)

    object_key = f"{operator.operator_id}/{migration_seq}/snapshot.msgpack"
    byte_size = await object_store.upload(object_key, msgpack_bytes)

    log.info(
        "Snapshot created for %s: key=%s size=%d bytes",
        operator.operator_id, object_key, byte_size
    )
    return object_key, byte_size
