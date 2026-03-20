from __future__ import annotations
import collections
from typing import Any
from hea.execution.base_operator import BaseOperator


class PatternDetector(BaseOperator):
    """
    Detects anomalous traffic flow patterns (congestion waves) across zones.
    Single instance. Batch operator — no SLO.
    """

    operator_type = "PatternDetector"

    def __init__(self, operator_id: str, congestion_threshold: float = 0.7):
        self.operator_id           = operator_id
        self._congestion_threshold = congestion_threshold
        self._zone_history: dict[str, collections.deque[float]] = {}
        self._incident_count = 0

    def get_slo_ms(self) -> float | None:
        return None

    def get_lambda_class(self) -> str:
        return "batch"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        zone_id = record.get("zone_id", "unknown")
        density = float(record.get("density", 0.0))

        if zone_id not in self._zone_history:
            self._zone_history[zone_id] = collections.deque(maxlen=20)
        self._zone_history[zone_id].append(density)

        congested_zones = [z for z, hist in self._zone_history.items()
                           if hist and hist[-1] > self._congestion_threshold]

        if len(congested_zones) >= 3:
            self._incident_count += 1
            return [{
                "pattern_type":    "congestion_wave",
                "congested_zones": congested_zones,
                "incident_count":  self._incident_count,
                "severity":        len(congested_zones),
                "timestamp":       record.get("timestamp", 0),
            }]

        return []

    def get_state(self) -> dict[str, Any]:
        return {
            "congestion_threshold": self._congestion_threshold,
            "zone_history":         {k: list(v) for k, v in self._zone_history.items()},
            "incident_count":       self._incident_count,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._congestion_threshold = float(state.get("congestion_threshold", 0.7))
        self._incident_count       = int(state.get("incident_count", 0))
        self._zone_history = {
            k: collections.deque(v, maxlen=20)
            for k, v in state.get("zone_history", {}).items()
        }
