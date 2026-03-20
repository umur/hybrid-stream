from __future__ import annotations
import math
from typing import Any
from hea.execution.base_operator import BaseOperator


class NormalizerOperator(BaseOperator):
    """
    Per-zone signal normalizer.
    Applies z-score normalization using Welford's online mean/variance.
    5 instances, one per traffic zone (zone_1 through zone_5).
    SLO: 5ms.
    """

    operator_type = "NormalizerOperator"

    def __init__(self, operator_id: str, zone_id: str, alpha: float = 0.01):
        self.operator_id = operator_id
        self.zone_id     = zone_id
        self._alpha      = alpha
        self._mean       = 0.0
        self._variance   = 1.0
        self._count      = 0

    def get_slo_ms(self) -> float:
        return 5.0

    def get_lambda_class(self) -> str:
        return "standard"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        value = float(record.get("sensor_value", 0.0))

        self._count += 1
        delta          = value - self._mean
        self._mean    += delta / self._count
        delta2         = value - self._mean
        self._variance = ((self._count - 1) * self._variance + delta * delta2) / self._count

        std        = math.sqrt(max(self._variance, 1e-9))
        normalized = (value - self._mean) / std

        output = dict(record)
        output.update({
            "zone_id":          self.zone_id,
            "normalized_value": normalized,
            "sensor_mean":      self._mean,
            "sensor_std":       std,
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "zone_id":  self.zone_id,
            "mean":     self._mean,
            "variance": self._variance,
            "count":    self._count,
            "alpha":    self._alpha,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._mean     = float(state.get("mean",     0.0))
        self._variance = float(state.get("variance", 1.0))
        self._count    = int(state.get("count",      0))
        self._alpha    = float(state.get("alpha",    0.01))
