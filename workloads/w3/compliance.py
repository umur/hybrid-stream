from __future__ import annotations
import time
from typing import Any
from hea.execution.base_operator import BaseOperator


class ComplianceLogger(BaseOperator):
    """
    Records compliance-relevant events for regulatory audit trail.
    6 instances, one per compliance domain. Batch — durability > speed.
    """

    operator_type = "ComplianceLogger"

    DOMAINS = ["mifid2", "dodd_frank", "basel3", "sox", "gdpr", "aml"]

    def __init__(self, operator_id: str, compliance_domain: str):
        self.operator_id      = operator_id
        self._domain          = compliance_domain
        self._log_seq         = 0
        self._event_counts: dict[str, int] = {}
        self._first_event_ts: float | None = None
        self._last_event_ts:  float | None = None

    def get_slo_ms(self) -> float | None:
        return None

    def get_lambda_class(self) -> str:
        return "batch"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        event_type = str(record.get("event_type", "unknown"))
        ts         = float(record.get("timestamp", time.time()))

        self._log_seq += 1
        self._event_counts[event_type] = self._event_counts.get(event_type, 0) + 1

        if self._first_event_ts is None:
            self._first_event_ts = ts
        self._last_event_ts = ts

        output = dict(record)
        output.update({
            "compliance_domain": self._domain,
            "log_sequence":      self._log_seq,
            "compliance_logged": True,
            "event_type_counts": dict(self._event_counts),
            "logged_at":         time.time(),
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "domain":         self._domain,
            "log_seq":        self._log_seq,
            "event_counts":   self._event_counts,
            "first_event_ts": self._first_event_ts,
            "last_event_ts":  self._last_event_ts,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._domain         = state.get("domain",         self._domain)
        self._log_seq        = int(state.get("log_seq",    0))
        self._event_counts   = state.get("event_counts",   {})
        self._first_event_ts = state.get("first_event_ts")
        self._last_event_ts  = state.get("last_event_ts")
