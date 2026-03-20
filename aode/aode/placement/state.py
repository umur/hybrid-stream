import asyncio
import logging
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


class PlacementState:
    def __init__(self, etcd_client) -> None:
        self._etcd = etcd_client
        self._cache: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def load_from_etcd(self) -> None:
        async with self._lock:
            placement_data = await self._etcd.get_dict("/placement/operators")
            self._cache.update(placement_data)

    async def update_operator_placement(self, operator_type: str, tier_id: str) -> None:
        async with self._lock:
            self._cache[operator_type] = tier_id
            await self._etcd.put(f"/placement/operators/{operator_type}", tier_id)

    async def remove_operator(self, operator_type: str) -> None:
        async with self._lock:
            self._cache.pop(operator_type, None)
            await self._etcd.delete(f"/placement/operators/{operator_type}")

    def get_current_placement(self) -> Dict[str, str]:
        return dict(self._cache)

    def get_operators_on_tier(self, tier_id: str) -> List[str]:
        return [op for op, t in self._cache.items() if t == tier_id]

    def get_available_tiers(self) -> List[str]:
        return sorted(set(self._cache.values()))

    def get_slo_map(self) -> Dict[str, Optional[float]]:
        return {
            "VehicleDetector":    2000.0,
            "ZoneAggregator":     None,
            "PatternDetector":    5000.0,
            "RiskCheck":          1.0,
            "AnomalyDetector":    5.0,
            "StatAggregator":     None,
            "ComplianceLogger":   None,
            "NormalizerOperator": 10.0,
            "FeatureAggWindow":   50.0,
            "MultiStreamJoin":    100.0,
            "BinaryClassifier":   5.0,
        }

    def get_lambda_map(self) -> Dict[str, str]:
        return {
            "VehicleDetector":    "standard",
            "ZoneAggregator":     "batch",
            "PatternDetector":    "standard",
            "RiskCheck":          "critical",
            "AnomalyDetector":    "critical",
            "StatAggregator":     "batch",
            "ComplianceLogger":   "batch",
            "NormalizerOperator": "standard",
            "FeatureAggWindow":   "standard",
            "MultiStreamJoin":    "standard",
            "BinaryClassifier":   "critical",
        }

    def get_tier_capacities(self) -> Dict[str, int]:
        return {
            "edge-node-1": 5,
            "edge-node-2": 5,
            "edge-node-3": 5,
            "edge-node-4": 5,
            "cloud":       100,
        }
