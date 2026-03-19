import struct
import pytest
import os
import msgpack
from hybridstream.common.schema_registry import SchemaRegistry
from hybridstream.common.snapshot import serialize, deserialize, MAGIC

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "../../schema-registry/schemas")


def _registry() -> SchemaRegistry:
    return SchemaRegistry(local_schema_dir=SCHEMA_DIR)


# --- Fixture data for all 11 operator types ---

OPERATOR_STATES = {
    "NormalizerOperator": {
        "kafka_offset_map": {0: 1000, 1: 2000},
        "watermark_ms": 1700000000000,
        "scale_factors": {"temp": 0.01, "vibration": 0.001},
    },
    "FeatureAggWindow": {
        "window_buffers": [("key1", 1700000000000, [1.0, 2.0, 3.0])],
        "accumulators": {"sum": 6.0, "count": 3.0},
        "watermark_ms": 1700000000000,
        "pending_timers": [1700000030000, 1700000060000],
        "kafka_offset_map": {0: 500},
    },
    "MultiStreamJoin": {
        "left_buffer": [("k1", 1700000000000, b"\x01\x02")],
        "right_buffer": [("k2", 1700000001000, b"\x03\x04")],
        "window_size_ms": 5000,
        "watermark_ms": 1700000000000,
        "kafka_offset_map": {0: 100, 1: 200},
        "pending_timers": [1700000005000],
    },
    "BinaryClassifier": {
        "model_weights": b"\x00\x01\x02\x03\x04\x05",
        "feature_names": ["temp", "vibration", "pressure"],
        "watermark_ms": 1700000000000,
        "kafka_offset_map": {0: 3000},
    },
    "VehicleDetector": {
        "detection_state": {"intersection_A": 12, "intersection_B": 7},
        "watermark_ms": 1700000000000,
        "kafka_offset_map": {0: 400},
    },
    "ZoneAggregator": {
        "zone_id": "zone_north",
        "flow_counters": {"int_A": 1200, "int_B": 800},
        "window_buffers": [(1700000000000, 45), (1700000010000, 52)],
        "watermark_ms": 1700000000000,
        "kafka_offset_map": {0: 600},
    },
    "PatternDetector": {
        "pattern_state": {"zone_north": [(1700000000000, 45.0), (1700000010000, 52.0)]},
        "active_matches": [{"zone_north": 1700000000000}],
        "watermark_ms": 1700000000000,
        "pending_timers": [1700000060000],
        "kafka_offset_map": {0: 700},
    },
    "RiskCheck": {
        "rule_id": "max_position_size",
        "position_cache": {"AAPL": 10000.0, "GOOGL": 5000.0},
        "watermark_ms": 1700000000000,
        "kafka_offset_map": {0: 800},
    },
    "AnomalyDetector": {
        "baseline_stats": {"AAPL": (150.25, 2.3), "GOOGL": (2800.0, 15.0)},
        "alert_cooldown": {"AAPL": 1700000000000},
        "watermark_ms": 1700000000000,
        "kafka_offset_map": {0: 900},
    },
    "StatAggregator": {
        "accumulators": {"latency": [1.0, 2.0, 3.0], "throughput": [100.0, 200.0]},
        "window_buffers": [("latency", 1700000000000, 1.5)],
        "watermark_ms": 1700000000000,
        "pending_timers": [1700000030000],
        "kafka_offset_map": {0: 1000},
    },
    "ComplianceLogger": {
        "pending_records": [b"\x01\x02\x03", b"\x04\x05\x06"],
        "sequence_counter": 42,
        "watermark_ms": 1700000000000,
        "kafka_offset_map": {0: 1100},
    },
}


# --- Original tests (updated for HSMP header) ---

def test_normalizer_roundtrip():
    registry = _registry()
    state = OPERATOR_STATES["NormalizerOperator"]
    raw = serialize("NormalizerOperator", state, registry)
    restored = deserialize(raw, registry)
    assert restored["watermark_ms"] == state["watermark_ms"]
    assert restored["scale_factors"] == state["scale_factors"]


def test_schema_version_in_header():
    registry = _registry()
    state = {"kafka_offset_map": {0: 1}, "watermark_ms": 0, "scale_factors": {}}
    raw = serialize("NormalizerOperator", state, registry)
    # Check binary header
    assert raw[:4] == MAGIC
    version = struct.unpack(">H", raw[4:6])[0]
    assert version == 1
    # Check msgpack payload
    doc = msgpack.unpackb(raw[6:], raw=False, strict_map_key=False)
    assert doc["schema_version"] == 1
    assert doc["operator_class"] == "NormalizerOperator"


# --- Roundtrip tests for all 11 operator types ---

@pytest.mark.parametrize("op_class", list(OPERATOR_STATES.keys()))
def test_roundtrip_all_operators(op_class: str):
    registry = _registry()
    state = OPERATOR_STATES[op_class]
    raw = serialize(op_class, state, registry)
    restored = deserialize(raw, registry)
    # All fields from the schema must be present
    schema = registry.get_schema(op_class)
    for field_def in schema["fields"]:
        name = field_def["name"]
        assert name in restored, f"Missing field {name} in restored state for {op_class}"
    # watermark_ms is in every operator
    assert restored["watermark_ms"] == state["watermark_ms"]
    # kafka_offset_map is in every operator
    assert restored["kafka_offset_map"] == state["kafka_offset_map"]


# --- HSMP magic bytes tests ---

def test_hsmp_magic_bytes_present():
    registry = _registry()
    state = OPERATOR_STATES["NormalizerOperator"]
    raw = serialize("NormalizerOperator", state, registry)
    assert raw[0:4] == b"\x48\x53\x4d\x50"


def test_hsmp_schema_version_at_bytes_4_5():
    registry = _registry()
    state = OPERATOR_STATES["BinaryClassifier"]
    raw = serialize("BinaryClassifier", state, registry)
    version = struct.unpack(">H", raw[4:6])[0]
    assert version == 1


def test_hsmp_payload_starts_at_byte_6():
    registry = _registry()
    state = OPERATOR_STATES["VehicleDetector"]
    raw = serialize("VehicleDetector", state, registry)
    payload = raw[6:]
    doc = msgpack.unpackb(payload, raw=False, strict_map_key=False)
    assert doc["operator_class"] == "VehicleDetector"


# --- Error handling tests ---

def test_deserialize_raises_on_corrupted_magic_bytes():
    registry = _registry()
    state = OPERATOR_STATES["NormalizerOperator"]
    raw = serialize("NormalizerOperator", state, registry)
    # Corrupt magic bytes
    corrupted = b"\x00\x00\x00\x00" + raw[4:]
    with pytest.raises(ValueError, match="Invalid snapshot magic bytes"):
        deserialize(corrupted, registry)


def test_deserialize_raises_on_truncated_data():
    registry = _registry()
    with pytest.raises(ValueError, match="too short"):
        deserialize(b"\x48\x53", registry)


def test_deserialize_raises_on_unknown_operator_class():
    registry = _registry()
    # Build a valid header + payload with unknown operator class
    doc = {"schema_version": 1, "operator_class": "NonExistentOperator"}
    payload = msgpack.packb(doc, use_bin_type=True)
    header = MAGIC + struct.pack(">H", 1)
    raw = header + payload
    with pytest.raises(KeyError, match="Schema not found"):
        deserialize(raw, registry)
