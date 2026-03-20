from __future__ import annotations
import time
from typing import Any
from hea.execution.base_operator import BaseOperator


class MultiStreamJoin(BaseOperator):
    """
    Joins aggregated features from all 5 zones into a single multi-zone feature vector.
    Emits when all n_zones have contributed, or when window_timeout_ms elapses.
    SLO: 5ms.
    """

    operator_type = "MultiStreamJoin"

    def __init__(self, operator_id: str, n_zones: int = 5, window_timeout_ms: float = 100.0):
        self.operator_id     = operator_id
        self._n_zones        = n_zones
        self._window_timeout = window_timeout_ms / 1000.0
        self._current_window: dict[str, dict] = {}
        self._window_start   = time.monotonic()

    def get_slo_ms(self) -> float:
        return 5.0

    def get_lambda_class(self) -> str:
        return "standard"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        zone_id = record.get("zone_id", "unknown")
        self._current_window[zone_id] = record

        now              = time.monotonic()
        timeout_exceeded = (now - self._window_start) > self._window_timeout
        all_present      = len(self._current_window) >= self._n_zones

        if all_present or timeout_exceeded:
            output = self._emit_join()
            self._current_window = {}
            self._window_start   = now
            return [output]

        return []

    def _emit_join(self) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "join_timestamp": time.time(),
            "zones_present":  list(self._current_window.keys()),
        }
        for zone_id, agg in self._current_window.items():
            merged[f"{zone_id}_mean"] = agg.get("agg_mean", 0.0)
            merged[f"{zone_id}_max"]  = agg.get("agg_max",  0.0)
            merged[f"{zone_id}_p95"]  = agg.get("agg_p95",  0.0)
        return merged

    def get_state(self) -> dict[str, Any]:
        return {
            "n_zones":        self._n_zones,
            "window_timeout": self._window_timeout,
            "current_window": self._current_window,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._n_zones        = int(state.get("n_zones",         5))
        self._window_timeout = float(state.get("window_timeout", 0.1))
        self._current_window = state.get("current_window",       {})
        self._window_start   = time.monotonic()
