from hea.operator_registry import register
from .detector import VehicleDetector
from .zone_agg import ZoneAggregator
from .pattern  import PatternDetector

N_SENSORS = 500
N_ZONES   = 20


def register_w2_operators():
    register("VehicleDetector", VehicleDetector)
    register("ZoneAggregator",  ZoneAggregator)
    register("PatternDetector", PatternDetector)


def build_w2_pipeline(engine) -> list:
    """
    W2 DAG: 521 instances (500 VehicleDetector + 20 ZoneAggregator + 1 PatternDetector)
    """
    pipeline = []
    sensors_per_zone = N_SENSORS // N_ZONES  # 25

    for i in range(N_SENSORS):
        zone_idx = i // sensors_per_zone
        zone_id  = f"zone_{zone_idx + 1:02d}"
        op = VehicleDetector(
            operator_id=f"detector-{i:04d}",
            sensor_id=f"sensor_{i:04d}",
        )
        pipeline.append((op, ["w2-sensors"], [f"w2-detections-{zone_id}"]))

    for i in range(N_ZONES):
        zone_id = f"zone_{i + 1:02d}"
        op = ZoneAggregator(operator_id=f"zone-agg-{zone_id}", zone_id=zone_id)
        pipeline.append((op, [f"w2-detections-{zone_id}"], [f"w2-zone-{zone_id}"]))

    zone_topics = [f"w2-zone-zone_{i + 1:02d}" for i in range(N_ZONES)]
    pipeline.append((PatternDetector(operator_id="pattern-detector"), zone_topics, ["w2-incidents"]))

    return pipeline
