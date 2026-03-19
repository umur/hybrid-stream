import pytest
from hybridstream.common.dag_model import OperatorDAG, OperatorNode, Dependency, LambdaClass


ALL_OPERATOR_TYPES = [
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


def make_simple_dag() -> OperatorDAG:
    ops = [
        OperatorNode("A", "NormalizerOperator", LambdaClass.STANDARD, None),
        OperatorNode("B", "FeatureAggWindow",   LambdaClass.STANDARD, None),
        OperatorNode("C", "BinaryClassifier",   LambdaClass.CRITICAL, 5.0),
    ]
    deps = [Dependency("A", "B"), Dependency("B", "C")]
    return OperatorDAG(ops, deps)


# --- Original tests ---

def test_topological_order():
    dag = make_simple_dag()
    order = dag.topological_order()
    assert order.index("A") < order.index("B")
    assert order.index("B") < order.index("C")


def test_upstream_ids():
    dag = make_simple_dag()
    assert dag.upstream_ids("C") == ["B"]
    assert dag.upstream_ids("A") == []


def test_cycle_detection():
    ops = [
        OperatorNode("X", "NormalizerOperator", LambdaClass.STANDARD, None),
        OperatorNode("Y", "FeatureAggWindow",   LambdaClass.STANDARD, None),
    ]
    deps = [Dependency("X", "Y"), Dependency("Y", "X")]
    dag = OperatorDAG(ops, deps)
    with pytest.raises(ValueError, match="cycle"):
        dag.topological_order()


# --- New tests ---

@pytest.mark.parametrize("op_type", ALL_OPERATOR_TYPES)
def test_all_11_operator_types_can_be_created(op_type: str):
    node = OperatorNode(
        operator_id=f"test_{op_type}",
        operator_type=op_type,
        lambda_class=LambdaClass.STANDARD,
        slo_ms=None,
    )
    assert node.operator_type == op_type
    assert node.operator_id == f"test_{op_type}"
    assert node.parallelism == 1
    assert node.extra_config == {}


def test_multi_root_dag_w2_topology():
    """W2-like topology: 500 VehicleDetector → 20 ZoneAggregator → 1 PatternDetector."""
    ops = []
    deps = []

    # 500 leaf detectors
    for i in range(500):
        ops.append(OperatorNode(
            f"vd_{i}", "VehicleDetector", LambdaClass.CRITICAL, 2000.0,
        ))

    # 20 zone aggregators, each receiving from 25 detectors
    for z in range(20):
        ops.append(OperatorNode(
            f"za_{z}", "ZoneAggregator", LambdaClass.STANDARD, None,
        ))
        for i in range(z * 25, (z + 1) * 25):
            deps.append(Dependency(f"vd_{i}", f"za_{z}"))

    # 1 pattern detector receiving from all 20 aggregators
    ops.append(OperatorNode(
        "pd_0", "PatternDetector", LambdaClass.BATCH, None,
    ))
    for z in range(20):
        deps.append(Dependency(f"za_{z}", "pd_0"))

    dag = OperatorDAG(ops, deps)
    order = dag.topological_order()

    assert len(order) == 521
    # All detectors before their aggregators
    for z in range(20):
        za_idx = order.index(f"za_{z}")
        for i in range(z * 25, (z + 1) * 25):
            assert order.index(f"vd_{i}") < za_idx
    # All aggregators before pattern detector
    pd_idx = order.index("pd_0")
    for z in range(20):
        assert order.index(f"za_{z}") < pd_idx


def test_dag_with_no_edges():
    ops = [
        OperatorNode("solo_1", "NormalizerOperator", LambdaClass.STANDARD, None),
        OperatorNode("solo_2", "BinaryClassifier",   LambdaClass.CRITICAL, 5.0),
        OperatorNode("solo_3", "RiskCheck",          LambdaClass.CRITICAL, 1.0),
    ]
    dag = OperatorDAG(ops, [])
    order = dag.topological_order()
    assert set(order) == {"solo_1", "solo_2", "solo_3"}
    assert len(order) == 3


def test_lambda_class_enum_values():
    assert LambdaClass.CRITICAL.value == "critical"
    assert LambdaClass.STANDARD.value == "standard"
    assert LambdaClass.BATCH.value == "batch"
    # Verify all three are distinct
    assert len(set(LambdaClass)) == 3


def test_slo_none_for_batch_operators():
    batch_node = OperatorNode(
        "batch_op", "PatternDetector", LambdaClass.BATCH, None,
    )
    assert batch_node.slo_ms is None
    assert batch_node.lambda_class == LambdaClass.BATCH


def test_downstream_ids():
    dag = make_simple_dag()
    assert dag.downstream_ids("A") == ["B"]
    assert dag.downstream_ids("C") == []
    assert dag.downstream_ids("B") == ["C"]
