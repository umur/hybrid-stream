import numpy as np
from typing import Dict, List, Optional

from ..telemetry.collector import TelemetryCollector
from ..config import AODEConfig
from .weights import get_weight_preset, WeightPreset


class ScoringAlgorithm:
    def __init__(self, config: AODEConfig, telemetry: TelemetryCollector) -> None:
        self._config = config
        self._telemetry = telemetry
        self._weights: WeightPreset = get_weight_preset(config.default_weight_preset)

    def set_weights(self, preset_name: str) -> None:
        self._weights = get_weight_preset(preset_name)

    def compute_scores(
        self,
        operator_types: List[str],
        tiers: List[str],
        slo_map: Dict[str, Optional[float]],
        lambda_map: Dict[str, str],
    ) -> np.ndarray:
        n_ops = len(operator_types)
        n_tiers = len(tiers)
        scores = np.zeros((n_ops, n_tiers))

        for i, op_type in enumerate(operator_types):
            slo_ms = slo_map.get(op_type)
            lambda_class = lambda_map.get(op_type, "standard")

            for j, tier_id in enumerate(tiers):
                phi_lat = self._compute_phi_lat(op_type, tier_id, lambda_class)
                phi_res = self._compute_phi_res(tier_id)
                phi_net = self._compute_phi_net(tier_id)
                phi_slo = self._compute_phi_slo(op_type, tier_id, slo_ms)

                scores[i, j] = (
                    self._weights.w_lat * phi_lat
                    + self._weights.w_res * phi_res
                    + self._weights.w_net * phi_net
                    + self._weights.w_slo * phi_slo
                )

        return scores

    def _compute_phi_lat(self, operator_type: str, tier_id: str, lambda_class: str) -> float:
        lambda_weights = {"critical": 3.0, "standard": 1.0, "batch": 0.1}
        lambda_factor = lambda_weights.get(lambda_class, 1.0)
        observed_latency_ms = self._telemetry.get_operator_latency(operator_type) or 1.0
        return lambda_factor * observed_latency_ms

    def _compute_phi_res(self, tier_id: str) -> float:
        cpu_util, mem_util = self._telemetry.get_tier_utilization(tier_id)
        rho_j = max(cpu_util, mem_util)
        rho_j = min(rho_j, 0.99)  # Cap at 0.99 to prevent division by zero
        return self._config.kappa * rho_j / (1 - rho_j)

    def _compute_phi_net(self, tier_id: str) -> float:
        if tier_id == "cloud":
            return 0.0
        tel = self._telemetry.get_latest_telemetry().get(tier_id)
        if tel and tel.reachable:
            return tel.rtt_ms
        return 1000.0

    def _compute_phi_slo(self, operator_type: str, tier_id: str, slo_ms: Optional[float]) -> float:
        if slo_ms is None:
            # Batch operators have no real-time SLO. Use 3,600,000 ms (1 hour)
            # as a permissive sentinel so the SLO penalty term is effectively
            # zero under normal operating conditions.
            slo_ms = 3600.0 * 1000  # 3600s × 1000 ms/s = 3,600,000 ms
        observed_latency_ms = self._telemetry.get_operator_latency(operator_type) or 1.0
        if observed_latency_ms <= slo_ms:
            return 0.0
        violation_ratio = (observed_latency_ms - slo_ms) / slo_ms
        return self._config.slo_penalty_factor * violation_ratio


def find_optimal_placement(
    scores: np.ndarray,
    operator_types: List[str],
    tiers: List[str],
    tier_capacities: Dict[str, int],
) -> Dict[str, str]:
    placement = {}
    tier_usage = {tier: 0 for tier in tiers}

    op_min_scores = [(i, np.min(scores[i, :])) for i in range(len(operator_types))]
    op_min_scores.sort(key=lambda x: x[1], reverse=True)

    for i, _ in op_min_scores:
        op_type = operator_types[i]
        tier_scores = [(scores[i, j], j) for j in range(len(tiers))]
        tier_scores.sort()

        assigned = False
        for score, j in tier_scores:
            tier_id = tiers[j]
            if tier_usage[tier_id] < tier_capacities[tier_id]:
                placement[op_type] = tier_id
                tier_usage[tier_id] += 1
                assigned = True
                break

        if not assigned:
            placement[op_type] = "cloud"

    return placement
