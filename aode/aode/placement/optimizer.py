import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple

from ..scoring.algorithm import ScoringAlgorithm, find_optimal_placement
from ..migration.pctr import PCTROrchestrator
from .state import PlacementState
from ..config import AODEConfig

log = logging.getLogger(__name__)


class PlacementOptimizer:
    def __init__(
        self,
        config: AODEConfig,
        scoring: ScoringAlgorithm,
        migration_orchestrator: PCTROrchestrator,
        placement_state: PlacementState,
    ) -> None:
        self._config = config
        self._scoring = scoring
        self._migration = migration_orchestrator
        self._placement = placement_state
        self._optimization_task: Optional[asyncio.Task] = None
        self._last_optimization: float = 0.0

    async def start(self) -> None:
        if self._config.recalibration_enabled:
            self._optimization_task = asyncio.create_task(self._optimization_loop())

    async def stop(self) -> None:
        if self._optimization_task:
            self._optimization_task.cancel()

    async def force_recalibration(self, reason: str = "manual") -> Dict:
        return await self._run_optimization()

    async def _optimization_loop(self) -> None:
        while True:
            try:
                await self._run_optimization()
                self._last_optimization = time.monotonic()
            except Exception as e:
                log.error("Optimization cycle error: %s", e)
            await asyncio.sleep(self._config.recalibration_interval_s)

    async def _run_optimization(self) -> Dict:
        start_time = time.monotonic()
        current_placement = self._placement.get_current_placement()
        operator_types = list(current_placement.keys())
        available_tiers = self._placement.get_available_tiers()

        if not operator_types or len(available_tiers) < 2:
            return {"status": "no_operators", "duration_ms": 0}

        tiers = list(self._placement.get_tier_capacities().keys())

        slo_map = self._placement.get_slo_map()
        lambda_map = self._placement.get_lambda_map()
        tier_capacities = self._placement.get_tier_capacities()

        scores = self._scoring.compute_scores(operator_types, tiers, slo_map, lambda_map)
        optimal_placement = find_optimal_placement(scores, operator_types, tiers, tier_capacities)

        candidates = self._identify_migration_candidates(
            current_placement, optimal_placement, scores, operator_types, tiers
        )

        migrations_started = []
        for op_type, source_tier, target_tier, score_improvement in candidates:
            try:
                migration_id = await self._migration.migrate_operator(op_type, source_tier, target_tier)
                migrations_started.append({
                    "operator_type": op_type,
                    "source": source_tier,
                    "target": target_tier,
                    "score_improvement": round(score_improvement, 3),
                    "migration_id": migration_id,
                })
                await self._placement.update_operator_placement(op_type, target_tier)
            except Exception as e:
                log.warning("Failed to start migration for %s: %s", op_type, e)

        duration_ms = (time.monotonic() - start_time) * 1000

        return {
            "status": "completed",
            "duration_ms": round(duration_ms, 1),
            "candidates_evaluated": len(candidates),
            "migrations_started": len(migrations_started),
            "migrations": migrations_started,
        }

    def _identify_migration_candidates(
        self,
        current_placement: Dict[str, str],
        optimal_placement: Dict[str, str],
        scores,  # np.ndarray
        operator_types: List[str],
        tiers: List[str],
    ) -> List[Tuple[str, str, str, float]]:
        candidates = []
        delta_h = self._config.delta_h

        for i, op_type in enumerate(operator_types):
            current_tier = current_placement.get(op_type)
            optimal_tier = optimal_placement.get(op_type)

            if not current_tier or not optimal_tier or current_tier == optimal_tier:
                continue

            current_tier_idx = tiers.index(current_tier) if current_tier in tiers else -1
            optimal_tier_idx = tiers.index(optimal_tier) if optimal_tier in tiers else -1

            if current_tier_idx < 0 or optimal_tier_idx < 0:
                continue

            current_score = scores[i, current_tier_idx]
            optimal_score = scores[i, optimal_tier_idx]
            score_improvement = current_score - optimal_score

            if score_improvement >= delta_h:
                candidates.append((op_type, current_tier, optimal_tier, score_improvement))

        candidates.sort(key=lambda x: x[3], reverse=True)
        return candidates

    def get_status(self) -> Dict:
        last_run_ago = time.monotonic() - self._last_optimization if self._last_optimization > 0 else None
        active_migrations = self._migration.list_active_migrations()
        return {
            "enabled": self._config.recalibration_enabled,
            "interval_s": self._config.recalibration_interval_s,
            "last_run_ago_s": round(last_run_ago, 1) if last_run_ago else None,
            "active_migrations": len(active_migrations),
            "hysteresis_threshold": self._config.delta_h,
        }
