from __future__ import annotations
import time
import collections
from typing import Any
from hea.execution.base_operator import BaseOperator


class VehicleDetector(BaseOperator):
    """
    Per-sensor vehicle detection with EWMA state.
    500 instances, each monitoring one roadside sensor. SLO: 2s.
    """

    operator_type = "VehicleDetector"

    def __init__(self, operator_id: str, sensor_id: str, alpha: float = 0.2):
        self.operator_id      = operator_id
        self._sensor_id       = sensor_id
        self._alpha           = alpha
        self._ewma_occ        = 0.0
        self._ewma_speed      = 0.0
        self._detection_count = 0
        self._last_detection_ts: float | None = None
        self._detection_times: collections.deque[float] = collections.deque(maxlen=100)

    def get_slo_ms(self) -> float:
        return 2000.0

    def get_lambda_class(self) -> str:
        return "standard"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        occupancy = float(record.get("occupancy", 0.0))
        speed     = float(record.get("speed_kmh", 0.0))
        ts        = float(record.get("timestamp", time.time()))

        self._ewma_occ   = (1 - self._alpha) * self._ewma_occ   + self._alpha * occupancy
        self._ewma_speed = (1 - self._alpha) * self._ewma_speed + self._alpha * speed

        detected = self._ewma_occ > 0.15 and self._ewma_speed > 2.0

        if detected:
            self._detection_count += 1
            self._last_detection_ts = ts
            self._detection_times.append(ts)

        headway_s = None
        if len(self._detection_times) >= 2:
            intervals = [self._detection_times[i] - self._detection_times[i - 1]
                         for i in range(1, len(self._detection_times))]
            headway_s = sum(intervals) / len(intervals)

        return [{
            "sensor_id":        self._sensor_id,
            "vehicle_detected": detected,
            "ewma_occupancy":   round(self._ewma_occ,   4),
            "ewma_speed_kmh":   round(self._ewma_speed, 4),
            "detection_count":  self._detection_count,
            "mean_headway_s":   round(headway_s, 3) if headway_s else None,
            "timestamp":        ts,
        }]

    def get_state(self) -> dict[str, Any]:
        return {
            "sensor_id":         self._sensor_id,
            "alpha":             self._alpha,
            "ewma_occ":          self._ewma_occ,
            "ewma_speed":        self._ewma_speed,
            "detection_count":   self._detection_count,
            "last_detection_ts": self._last_detection_ts,
            "detection_times":   list(self._detection_times),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._alpha             = float(state.get("alpha",           0.2))
        self._ewma_occ          = float(state.get("ewma_occ",        0.0))
        self._ewma_speed        = float(state.get("ewma_speed",       0.0))
        self._detection_count   = int(state.get("detection_count",   0))
        self._last_detection_ts = state.get("last_detection_ts")
        self._detection_times   = collections.deque(state.get("detection_times", []), maxlen=100)
