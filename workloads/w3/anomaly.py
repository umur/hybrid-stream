from __future__ import annotations
import math
import collections
from typing import Any
from hea.execution.base_operator import BaseOperator


class AnomalyDetector(BaseOperator):
    """
    EWMA-based anomaly detector using 3-sigma rule.
    4 instances, one per financial metric class. SLO: 5ms (critical).
    """

    operator_type = "AnomalyDetector"

    def __init__(self, operator_id: str, metric_class: str, alpha: float = 0.2, z_threshold: float = 3.0):
        self.operator_id   = operator_id
        self._metric_class = metric_class
        self._alpha        = alpha
        self._z_threshold  = z_threshold
        self._ewma_mean    = 0.0
        self._ewma_m2      = 1.0
        self._anomaly_count = 0
        self._recent_zscores: collections.deque[float] = collections.deque(maxlen=100)

    def get_slo_ms(self) -> float:
        return 5.0

    def get_lambda_class(self) -> str:
        return "critical"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        value     = float(record.get("value", 0.0))
        prev_mean = self._ewma_mean

        self._ewma_mean = (1 - self._alpha) * self._ewma_mean + self._alpha * value
        delta           = value - prev_mean
        self._ewma_m2   = (1 - self._alpha) * self._ewma_m2 + self._alpha * delta ** 2

        std = math.sqrt(max(self._ewma_m2, 1e-12))
        z   = abs(value - self._ewma_mean) / std if std > 0 else 0.0
        self._recent_zscores.append(z)

        is_anomaly = z > self._z_threshold
        if is_anomaly:
            self._anomaly_count += 1

        output = dict(record)
        output.update({
            "metric_class":  self._metric_class,
            "is_anomaly":    is_anomaly,
            "z_score":       round(z, 4),
            "ewma_mean":     round(self._ewma_mean, 6),
            "ewma_std":      round(std, 6),
            "anomaly_count": self._anomaly_count,
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "metric_class":   self._metric_class,
            "alpha":          self._alpha,
            "z_threshold":    self._z_threshold,
            "ewma_mean":      self._ewma_mean,
            "ewma_m2":        self._ewma_m2,
            "anomaly_count":  self._anomaly_count,
            "recent_zscores": list(self._recent_zscores),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._metric_class   = state.get("metric_class",  self._metric_class)
        self._alpha          = float(state.get("alpha",        0.2))
        self._z_threshold    = float(state.get("z_threshold",  3.0))
        self._ewma_mean      = float(state.get("ewma_mean",    0.0))
        self._ewma_m2        = float(state.get("ewma_m2",      1.0))
        self._anomaly_count  = int(state.get("anomaly_count",  0))
        self._recent_zscores = collections.deque(state.get("recent_zscores", []), maxlen=100)
