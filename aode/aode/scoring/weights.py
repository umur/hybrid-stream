import math
from dataclasses import dataclass
from typing import Dict


@dataclass
class WeightPreset:
    name:   str
    w_lat:  float
    w_res:  float
    w_net:  float
    w_slo:  float

    def __post_init__(self):
        total = self.w_lat + self.w_res + self.w_net + self.w_slo
        if not math.isclose(total, 1.0, abs_tol=0.01):
            raise ValueError(f"Weight preset '{self.name}': weights must sum to 1.0 (got {total})")


WEIGHT_PRESETS: Dict[str, WeightPreset] = {
    "latency-first": WeightPreset(name="latency-first", w_lat=0.55, w_res=0.10, w_net=0.20, w_slo=0.15),
    "balanced": WeightPreset(name="balanced", w_lat=0.30, w_res=0.30, w_net=0.20, w_slo=0.20),
    "resource-efficient": WeightPreset(name="resource-efficient", w_lat=0.20, w_res=0.50, w_net=0.20, w_slo=0.10),
}


def get_weight_preset(name: str) -> WeightPreset:
    if name not in WEIGHT_PRESETS:
        raise ValueError(f"Unknown weight preset '{name}'. Available: {list(WEIGHT_PRESETS.keys())}")
    return WEIGHT_PRESETS[name]


def create_custom_preset(name: str, w_lat: float, w_res: float, w_net: float, w_slo: float) -> WeightPreset:
    return WeightPreset(name=name, w_lat=w_lat, w_res=w_res, w_net=w_net, w_slo=w_slo)
