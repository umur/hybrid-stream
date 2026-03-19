import pytest
import os
from hybridstream.common.schema_registry import SchemaRegistry

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "../../schema-registry/schemas")

ALL_OPERATOR_CLASSES = [
    "NormalizerOperator",
    "FeatureAggWindow",
    "MultiStreamJoin",
    "BinaryClassifier",
    "VehicleDetector",
    "ZoneAggregator",
    "PatternDetector",
    "RiskCheck",
    "AnomalyDetector",
    "StatAggregator",
    "ComplianceLogger",
]


def _registry() -> SchemaRegistry:
    return SchemaRegistry(local_schema_dir=SCHEMA_DIR)


@pytest.mark.parametrize("op_class", ALL_OPERATOR_CLASSES)
def test_all_11_schemas_load_without_error(op_class: str):
    registry = _registry()
    schema = registry.get_schema(op_class)
    assert schema is not None
    assert "fields" in schema
    assert "operator_class" in schema
    assert "schema_version" in schema


@pytest.mark.parametrize("op_class", ALL_OPERATOR_CLASSES)
def test_schema_version_is_1(op_class: str):
    registry = _registry()
    schema = registry.get_schema(op_class)
    assert schema["schema_version"] == 1


@pytest.mark.parametrize("op_class", ALL_OPERATOR_CLASSES)
def test_operator_class_matches(op_class: str):
    registry = _registry()
    schema = registry.get_schema(op_class)
    assert schema["operator_class"] == op_class


@pytest.mark.parametrize("op_class", ALL_OPERATOR_CLASSES)
def test_fields_have_required_keys(op_class: str):
    registry = _registry()
    schema = registry.get_schema(op_class)
    for field_def in schema["fields"]:
        assert "name" in field_def, f"Missing 'name' in field of {op_class}"
        assert "type" in field_def, f"Missing 'type' in field of {op_class}"
        assert "nullable" in field_def, f"Missing 'nullable' in field of {op_class}"
        assert "description" in field_def, f"Missing 'description' in field of {op_class}"


# Verify specific field counts per operator type
EXPECTED_FIELD_COUNTS = {
    "NormalizerOperator": 3,
    "FeatureAggWindow": 5,
    "MultiStreamJoin": 6,
    "BinaryClassifier": 4,
    "VehicleDetector": 3,
    "ZoneAggregator": 5,
    "PatternDetector": 5,
    "RiskCheck": 4,
    "AnomalyDetector": 4,
    "StatAggregator": 5,
    "ComplianceLogger": 4,
}


@pytest.mark.parametrize("op_class", ALL_OPERATOR_CLASSES)
def test_correct_field_count(op_class: str):
    registry = _registry()
    schema = registry.get_schema(op_class)
    assert len(schema["fields"]) == EXPECTED_FIELD_COUNTS[op_class], (
        f"{op_class}: expected {EXPECTED_FIELD_COUNTS[op_class]} fields, "
        f"got {len(schema['fields'])}"
    )


def test_raises_on_unknown_type():
    registry = _registry()
    with pytest.raises(KeyError, match="Schema not found"):
        registry.get_schema("TotallyFakeOperator")


def test_schema_caching():
    registry = _registry()
    schema1 = registry.get_schema("NormalizerOperator")
    schema2 = registry.get_schema("NormalizerOperator")
    assert schema1 is schema2  # same object reference — proves cache hit
