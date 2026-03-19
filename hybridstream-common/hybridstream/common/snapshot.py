import struct
import msgpack
from .schema_registry import SchemaRegistry

# Snapshot binary format:
# Bytes [0..3]: magic bytes 0x48 0x53 0x4D 0x50 ("HSMP")
# Bytes [4..5]: schema_version as uint16 big-endian
# Bytes [6..]:  MessagePack payload
MAGIC = b"\x48\x53\x4d\x50"


def serialize(operator_class: str, state: dict, registry: SchemaRegistry) -> bytes:
    """
    Serialize operator state dict to snapshot bytes.
    Format: HSMP magic (4B) + schema_version (2B BE) + MessagePack payload.
    """
    schema = registry.get_schema(operator_class)
    version = schema["schema_version"]
    doc = {"schema_version": version, "operator_class": operator_class}
    for field_def in schema["fields"]:
        name = field_def["name"]
        doc[name] = state.get(name)
    payload = msgpack.packb(doc, use_bin_type=True)
    header = MAGIC + struct.pack(">H", version)
    return header + payload


def deserialize(data: bytes, registry: SchemaRegistry) -> dict:
    """
    Deserialize snapshot bytes to state dict.
    Validates HSMP magic bytes, reads schema_version from header,
    then unpacks MessagePack payload.
    """
    if len(data) < 6:
        raise ValueError("Snapshot too short: expected at least 6 bytes")
    if data[:4] != MAGIC:
        raise ValueError(
            f"Invalid snapshot magic bytes: expected {MAGIC!r}, got {data[:4]!r}"
        )
    schema_version = struct.unpack(">H", data[4:6])[0]
    payload = data[6:]
    doc = msgpack.unpackb(payload, raw=False, strict_map_key=False)
    operator_class = doc.get("operator_class")
    if not operator_class:
        raise ValueError("Missing operator_class in snapshot payload")
    schema = registry.get_schema(operator_class, schema_version)
    return {f["name"]: doc.get(f["name"]) for f in schema["fields"]}
