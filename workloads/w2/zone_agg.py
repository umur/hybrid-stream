from __future__ import annotations
import time
from typing import Any
from hea.execution.base_operator import BaseOperator


class ZoneAggregator(BaseOperator):
    """
    Aggregates detection counts and flow statistics per traffic zone.
    20 instances, each covering 25 sensors. Batch operator — no hard SLO.
    """

    operator_type = "ZoneAggregator"

    def __init__(self, operator_id: str, zone_id: str, n_sensors: int = 25):
        self.operator_id    = operator_id
        self._zone_id       = zone_id
        self._n_sensors     = n_sensors
        self._sensor_counts: dict[str, int] = {}
        self._zone_total    = 0
        self._last_emit_ts  = time.monotonic()
        self._emit_interval = 5.0

    def get_slo_ms(self) -> float | None:
        return None

    def get_lambda_class(self) -> str:
        return "batch"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        sensor_id = record.get("sensor_id", "unknown")
        detected  = bool(record.get("vehicle_detected", False))

        if detected:
            self._sensor_counts[sensor_id] = self._sensor_counts.get(sensor_id, 0) + 1
            self._zone_total += 1

        now = time.monotonic()
        if now - self._last_emit_ts >= self._emit_interval:
            self._last_emit_ts = now
            return [{
                "zone_id":          self._zone_id,
                "total_detections": self._zone_total,
                "active_sensors":   len(self._sensor_counts),
                "density":          len(self._sensor_counts) / max(self._n_sensors, 1),
                "timestamp":        time.time(),
            }]

        return []

    def get_state(self) -> dict[str, Any]:
        return {
            "zone_id":       self._zone_id,
            "n_sensors":     self._n_sensors,
            "sensor_counts": self._sensor_counts,
            "zone_total":    self._zone_total,
            "emit_interval": self._emit_interval,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._zone_id       = state.get("zone_id",      self._zone_id)
        self._n_sensors     = int(state.get("n_sensors",    25))
        self._sensor_counts = state.get("sensor_counts", {})
        self._zone_total    = int(state.get("zone_total",    0))
        self._emit_interval = float(state.get("emit_interval", 5.0))
        self._last_emit_ts  = time.monotonic()
