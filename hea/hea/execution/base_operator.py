from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class BaseOperator(ABC):
    """
    Abstract base class for all HybridStream stream processing operators.
    """

    operator_id:   str
    operator_type: str

    @abstractmethod
    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def restore_state(self, state: dict[str, Any]) -> None:
        ...

    def get_slo_ms(self) -> float | None:
        return None

    def get_lambda_class(self) -> str:
        return "standard"

    def on_start(self) -> None:
        pass

    def on_stop(self) -> None:
        pass
