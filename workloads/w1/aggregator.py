from __future__ import annotations
import collections
import statistics
from typing import Any
from hea.execution.base_operator import BaseOperator


class FeatureAggWindow(BaseOperator):
    """
    Sliding window aggregator: sum, mean, min, max, p95 over a tumbling window.
    5 instances, one per zone. Window size: 1000 events.
    Emits every 100 records to reduce downstream pressure.
    SLO: 5ms.
    """

    operator_type = "FeatureAggWindow"

    def __init__(self, operator_id: str, zone_id: str, window_size: int = 1000):
        self.operator_id        = operator_id
        self.zone_id            = zone_id
        self._window_size       = window_size
        self._window: collections.deque[float] = collections.deque(maxlen=window_size)
        self._emit_every        = 100
        self._count_since_emit  = 0

    def get_slo_ms(self) -> float:
        return 5.0

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        value = float(record.get("normalized_value", 0.0))
        self._window.append(value)
        self._count_since_emit += 1

        if self._count_since_emit < self._emit_every:
            return []

        self._count_since_emit = 0
        window_list = list(self._window)
        sorted_w    = sorted(window_list)
        p95_idx     = max(0, int(len(sorted_w) * 0.95) - 1)

        return [{
            "zone_id":      self.zone_id,
            "agg_sum":      sum(window_list),
            "agg_mean":     statistics.mean(window_list),
            "agg_min":      min(window_list),
            "agg_max":      max(window_list),
            "agg_p95":      sorted_w[p95_idx],
            "agg_stdev":    statistics.stdev(window_list) if len(window_list) > 1 else 0.0,
            "window_count": len(window_list),
            "source_ts":    record.get("timestamp", 0),
        }]

    def get_state(self) -> dict[str, Any]:
        return {
            "zone_id":     self.zone_id,
            "window":      list(self._window),
            "window_size": self._window_size,
            "emit_every":  self._emit_every,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._window_size      = int(state.get("window_size", 1000))
        self._window           = collections.deque(state.get("window", []), maxlen=self._window_size)
        self._emit_every       = int(state.get("emit_every",  100))
        self._count_since_emit = 0
