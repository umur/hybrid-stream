import msgpack
from .schema_registry import SchemaRegistry


def serialize(operator_class: str, state: dict, registry: SchemaRegistry) -> bytes:
    """
    Serialize operator state dict to MessagePack bytes using the schema registry layout.
    Embeds schema_version as header field for cross-language deserialization.
    """
    schema = registry.get_schema(operator_class)
    doc = {"schema_version": schema["schema_version"], "operator_class": operator_class}
    for field_def in schema["fields"]:
        name = field_def["name"]
        doc[name] = state.get(name)
    return msgpack.packb(doc, use_bin_type=True)


def deserialize(data: bytes, registry: SchemaRegistry) -> dict:
    """
    Deserialize MessagePack bytes to state dict.
    Reads schema_version and operator_class from header — no prior knowledge needed.
    """
    doc = msgpack.unpackb(data, raw=False, strict_map_key=False)
    operator_class = doc["operator_class"]
    schema = registry.get_schema(operator_class, doc["schema_version"])
    return {f["name"]: doc.get(f["name"]) for f in schema["fields"]}
