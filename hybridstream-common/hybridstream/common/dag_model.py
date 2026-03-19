from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class LambdaClass(str, Enum):
    CRITICAL = "critical"
    STANDARD = "standard"
    BATCH    = "batch"


@dataclass
class OperatorNode:
    operator_id:    str
    operator_type:  str               # maps to schema registry class name
    lambda_class:   LambdaClass
    slo_ms:         float | None      # None for BATCH; use 3600_000 in scoring
    parallelism:    int = 1
    extra_config:   dict = field(default_factory=dict)


@dataclass
class Dependency:
    upstream_id:   str
    downstream_id: str


@dataclass
class OperatorDAG:
    operators:    list[OperatorNode]
    dependencies: list[Dependency]

    def upstream_ids(self, operator_id: str) -> list[str]:
        return [d.upstream_id for d in self.dependencies if d.downstream_id == operator_id]

    def downstream_ids(self, operator_id: str) -> list[str]:
        return [d.downstream_id for d in self.dependencies if d.upstream_id == operator_id]

    def topological_order(self) -> list[str]:
        """Kahn's algorithm — returns operator IDs in topological order."""
        in_degree: dict[str, int] = {op.operator_id: 0 for op in self.operators}
        for dep in self.dependencies:
            in_degree[dep.downstream_id] += 1

        queue = [oid for oid, deg in in_degree.items() if deg == 0]
        order: list[str] = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for downstream in self.downstream_ids(node):
                in_degree[downstream] -= 1
                if in_degree[downstream] == 0:
                    queue.append(downstream)

        if len(order) != len(self.operators):
            raise ValueError("DAG has a cycle — topological sort failed.")
        return order

    @classmethod
    def from_yaml(cls, path: str) -> "OperatorDAG":
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        operators = [
            OperatorNode(
                operator_id=op["id"],
                operator_type=op["type"],
                lambda_class=LambdaClass(op["lambda"]),
                slo_ms=op.get("slo_ms"),
                parallelism=op.get("parallelism", 1),
                extra_config={k: v for k, v in op.items()
                              if k not in ("id", "type", "lambda", "slo_ms", "parallelism")},
            )
            for op in data["operators"]
        ]
        dependencies = [
            Dependency(upstream_id=e["from"], downstream_id=e["to"])
            for e in data.get("edges", [])
        ]
        return cls(operators=operators, dependencies=dependencies)
