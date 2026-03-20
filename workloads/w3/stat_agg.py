from __future__ import annotations
import math
from typing import Any
from hea.execution.base_operator import BaseOperator


class StatAggregator(BaseOperator):
    """
    Online statistical aggregation using Welford's algorithm.
    12 instances, one per instrument class. Batch — no SLO.
    Emits every 500 records.
    """

    operator_type = "StatAggregator"

    def __init__(self, operator_id: str, instrument_class: str):
        self.operator_id       = operator_id
        self._instrument_class = instrument_class
        self._count   = 0
        self._mean    = 0.0
        self._m2      = 0.0
        self._min     = float("inf")
        self._max     = float("-inf")

    def get_slo_ms(self) -> float | None:
        return None

    def get_lambda_class(self) -> str:
        return "batch"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        value = float(record.get("value", 0.0))

        self._count += 1
        delta       = value - self._mean
        self._mean += delta / self._count
        self._m2   += delta * (value - self._mean)
        self._min   = min(self._min, value)
        self._max   = max(self._max, value)

        if self._count % 500 == 0:
            variance = self._m2 / (self._count - 1) if self._count > 1 else 0.0
            return [{
                "instrument_class": self._instrument_class,
                "count":            self._count,
                "mean":             round(self._mean, 6),
                "std":              round(math.sqrt(variance), 6),
                "variance":         round(variance, 8),
                "min":              self._min,
                "max":              self._max,
            }]
        return []

    def get_state(self) -> dict[str, Any]:
        return {
            "instrument_class": self._instrument_class,
            "count":            self._count,
            "mean":             self._mean,
            "m2":               self._m2,
            "min":              self._min if self._min != float("inf")  else None,
            "max":              self._max if self._max != float("-inf") else None,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._instrument_class = state.get("instrument_class", self._instrument_class)
        self._count = int(state.get("count",  0))
        self._mean  = float(state.get("mean", 0.0))
        self._m2    = float(state.get("m2",   0.0))
        self._min   = float(state["min"])  if state.get("min") is not None  else float("inf")
        self._max   = float(state["max"])  if state.get("max") is not None else float("-inf")
