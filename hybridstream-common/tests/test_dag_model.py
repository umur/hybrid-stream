import pytest
from hybridstream.common.dag_model import OperatorDAG, OperatorNode, Dependency, LambdaClass


def make_simple_dag() -> OperatorDAG:
    ops = [
        OperatorNode("A", "NormalizerOperator", LambdaClass.STANDARD, None),
        OperatorNode("B", "FeatureAggWindow",   LambdaClass.STANDARD, None),
        OperatorNode("C", "BinaryClassifier",   LambdaClass.CRITICAL, 5.0),
    ]
    deps = [Dependency("A", "B"), Dependency("B", "C")]
    return OperatorDAG(ops, deps)


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
