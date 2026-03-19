import pytest
import os
from hybridstream.common.schema_registry import SchemaRegistry
from hybridstream.common.snapshot import serialize, deserialize

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "../../schema-registry/schemas")


def test_normalizer_roundtrip():
    registry = SchemaRegistry(local_schema_dir=SCHEMA_DIR)
    state = {
        "kafka_offset_map": {0: 1000, 1: 2000},
        "watermark_ms": 1700000000000,
        "scale_factors": {"temp": 0.01, "vibration": 0.001},
    }
    raw = serialize("NormalizerOperator", state, registry)
    restored = deserialize(raw, registry)
    assert restored["watermark_ms"] == state["watermark_ms"]
    assert restored["scale_factors"] == state["scale_factors"]


def test_schema_version_in_header():
    registry = SchemaRegistry(local_schema_dir=SCHEMA_DIR)
    import msgpack
    state = {"kafka_offset_map": {0: 1}, "watermark_ms": 0, "scale_factors": {}}
    raw = serialize("NormalizerOperator", state, registry)
    doc = msgpack.unpackb(raw, raw=False, strict_map_key=False)
    assert doc["schema_version"] == 1
    assert doc["operator_class"] == "NormalizerOperator"
