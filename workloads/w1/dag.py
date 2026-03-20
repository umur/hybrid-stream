from hea.operator_registry import register
from .normalizer  import NormalizerOperator
from .aggregator  import FeatureAggWindow
from .join        import MultiStreamJoin
from .classifier  import BinaryClassifier

ZONES = ["zone_1", "zone_2", "zone_3", "zone_4", "zone_5"]


def register_w1_operators():
    register("NormalizerOperator", NormalizerOperator)
    register("FeatureAggWindow",   FeatureAggWindow)
    register("MultiStreamJoin",    MultiStreamJoin)
    register("BinaryClassifier",   BinaryClassifier)


def build_w1_pipeline(engine) -> list:
    """
    W1 DAG:
      w1-raw-zone-{1..5} → NormalizerOperator (5×) → FeatureAggWindow (5×)
                         → MultiStreamJoin (1×) → BinaryClassifier (1×) → w1-classified
    """
    pipeline = []

    for zone in ZONES:
        op = NormalizerOperator(operator_id=f"normalizer-{zone}", zone_id=zone)
        pipeline.append((op, [f"w1-raw-{zone}"], [f"w1-norm-{zone}"]))

    for zone in ZONES:
        op = FeatureAggWindow(operator_id=f"agg-{zone}", zone_id=zone)
        pipeline.append((op, [f"w1-norm-{zone}"], [f"w1-agg-{zone}"]))

    join = MultiStreamJoin(operator_id="multi-join", n_zones=5)
    pipeline.append((join, [f"w1-agg-{z}" for z in ZONES], ["w1-joined"]))

    classifier = BinaryClassifier(operator_id="classifier")
    pipeline.append((classifier, ["w1-joined"], ["w1-classified"]))

    return pipeline
