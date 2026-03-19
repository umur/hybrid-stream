from __future__ import annotations
from typing import Type
from .execution.base_operator import BaseOperator

_registry: dict[str, Type[BaseOperator]] = {}


def register(operator_type: str, cls: Type[BaseOperator]) -> None:
    _registry[operator_type] = cls


def get(operator_type: str) -> Type[BaseOperator]:
    if operator_type not in _registry:
        raise KeyError(
            f"Operator type '{operator_type}' not registered. "
            f"Available: {sorted(_registry.keys())}"
        )
    return _registry[operator_type]


def register_all_from_workload(module_path: str) -> None:
    import importlib
    import inspect
    mod = importlib.import_module(module_path)
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, BaseOperator) and obj is not BaseOperator:
            if hasattr(obj, "operator_type"):
                register(obj.operator_type, obj)
