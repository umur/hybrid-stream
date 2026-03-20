from __future__ import annotations
from typing import Any
from hea.execution.base_operator import BaseOperator


class RiskCheck(BaseOperator):
    """
    Ultra-low latency risk exposure check. 8 instances, one per risk category.
    SLO: 1ms (critical).
    """

    operator_type = "RiskCheck"

    CATEGORIES = {
        "credit":        5_000_000.0,
        "market":       10_000_000.0,
        "liquidity":     2_000_000.0,
        "operational":   1_000_000.0,
        "counterparty":  3_000_000.0,
        "settlement":      500_000.0,
        "model":         1_500_000.0,
        "reputational":    250_000.0,
    }

    def __init__(self, operator_id: str, risk_category: str):
        self.operator_id    = operator_id
        self._risk_category = risk_category
        self._limit         = self.CATEGORIES.get(risk_category, 1_000_000.0)
        self._breach_count  = 0
        self._total_checked = 0

    def get_slo_ms(self) -> float:
        return 1.0

    def get_lambda_class(self) -> str:
        return "critical"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        exposure = float(record.get("exposure", 0.0))
        self._total_checked += 1
        exceeded = exposure > self._limit
        if exceeded:
            self._breach_count += 1

        output = dict(record)
        output.update({
            "risk_category":  self._risk_category,
            "limit":          self._limit,
            "exposure":       exposure,
            "risk_exceeded":  exceeded,
            "exposure_ratio": exposure / self._limit if self._limit > 0 else 0.0,
            "breach_count":   self._breach_count,
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "risk_category": self._risk_category,
            "limit":         self._limit,
            "breach_count":  self._breach_count,
            "total_checked": self._total_checked,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._risk_category = state.get("risk_category", self._risk_category)
        self._limit         = float(state.get("limit",        1_000_000.0))
        self._breach_count  = int(state.get("breach_count",  0))
        self._total_checked = int(state.get("total_checked", 0))
