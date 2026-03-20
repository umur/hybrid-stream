from __future__ import annotations
import asyncio
import logging
import time

from .config import EXPERIMENT_MATRIX, ExperimentConfig, WORKLOAD_CONFIGS, NETWORK_PROFILES
from .network import apply_network_profile, clear_network_profile
from .baselines import setup_baseline_b1, setup_baseline_b2, B1Config
from ..metrics.collector import MetricsCollector
from ..metrics.storage import save_snapshots

log = logging.getLogger(__name__)


class ExperimentRunner:
    """Orchestrates all 270 experiment runs (27 configs × 10 reps)."""

    def __init__(self, dry_run: bool = False):
        self._dry_run = dry_run

    async def run_all(self) -> None:
        total = len(EXPERIMENT_MATRIX) * 10
        log.info("Starting: %d configs × 10 reps = %d runs", len(EXPERIMENT_MATRIX), total)

        sorted_configs = sorted(EXPERIMENT_MATRIX, key=lambda c: (c.network, c.workload, c.system))
        current_network = None
        start_time = time.monotonic()

        for config in sorted_configs:
            if config.network != current_network:
                profile = NETWORK_PROFILES[config.network]
                if not self._dry_run:
                    await apply_network_profile(profile)
                log.info("Network profile: %s (RTT=%dms)", config.network, profile.rtt_ms)
                current_network = config.network

            for rep in range(1, 11):
                log.info("Running: %s rep %d/10", config.config_id, rep)
                if self._dry_run:
                    log.info("[DRY RUN] Would run %s rep %d", config.config_id, rep)
                    continue
                await self._run_single(config, rep)
                await asyncio.sleep(60)

        log.info("All experiments complete in %.1fh", (time.monotonic() - start_time) / 3600)

    async def _run_single(self, config: ExperimentConfig, repetition: int) -> None:
        wl_config = WORKLOAD_CONFIGS[config.workload]
        collector = MetricsCollector(
            config_id=config.config_id, repetition=repetition, warmup_s=wl_config.warmup_s
        )
        try:
            await self._setup_system(config)
            await asyncio.sleep(30)
            collector.start()
            gen_task = asyncio.create_task(
                self._run_generator(config.workload, wl_config.ingest_rate_eps)
            )
            await asyncio.sleep(wl_config.warmup_s + wl_config.duration_s)
            gen_task.cancel()
            collector.stop()
            snapshots = collector.get_snapshots(post_warmup_only=True)
            save_snapshots(snapshots, config.config_id, repetition)
            log.info("Completed %s rep %d: %d snapshots", config.config_id, repetition, len(snapshots))
        except Exception as e:
            log.error("Run failed %s rep %d: %s", config.config_id, repetition, e)
            raise
        finally:
            await self._teardown_system(config)

    async def _setup_system(self, config: ExperimentConfig) -> None:
        if config.system == "B1":
            await setup_baseline_b1(B1Config(), config.workload)
        elif config.system == "B2":
            await setup_baseline_b2(config.workload, config.network)
        else:
            log.info("HybridStream: started via docker compose")

    async def _run_generator(self, workload: str, rate_eps: int) -> None:
        import importlib
        module = importlib.import_module(f"generators.{workload.lower()}_generator")
        await module.__dict__[f"generate_{workload.lower()}"]("localhost:9092", rate_eps)

    async def _teardown_system(self, config: ExperimentConfig) -> None:
        log.info("Teardown: %s", config.config_id)
