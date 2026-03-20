from __future__ import annotations
from typing import Any
from hea.execution.base_operator import BaseOperator


class BinaryClassifier(BaseOperator):
    """
    Classifies the joined feature vector as normal/anomalous traffic.
    Single instance at end of W1 pipeline. SLO: 5ms (critical).
    """

    operator_type = "BinaryClassifier"

    def __init__(self, operator_id: str, threshold: float = 0.6):
        self.operator_id = operator_id
        self._threshold  = threshold
        self._tp = self._fp = self._tn = self._fn = 0

    def get_slo_ms(self) -> float:
        return 5.0

    def get_lambda_class(self) -> str:
        return "critical"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        zone_maxes = [v for k, v in record.items() if k.endswith("_max")]
        score      = sum(zone_maxes) / len(zone_maxes) if zone_maxes else 0.0

        label      = 1 if score >= self._threshold else 0
        confidence = score if label == 1 else (1.0 - score)

        output = dict(record)
        output.update({
            "label":      label,
            "score":      round(score, 4),
            "confidence": round(confidence, 4),
            "threshold":  self._threshold,
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "threshold": self._threshold,
            "tp": self._tp, "fp": self._fp,
            "tn": self._tn, "fn": self._fn,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._threshold = float(state.get("threshold", 0.6))
        self._tp = int(state.get("tp", 0)); self._fp = int(state.get("fp", 0))
        self._tn = int(state.get("tn", 0)); self._fn = int(state.get("fn", 0))
