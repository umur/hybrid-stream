from __future__ import annotations
import asyncio
import math
import time
import logging
import statistics
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """
    One 5-second snapshot of M1–M6.
    M1: p95 latency (ms) per operator type
    M2: SLO compliance [0..1] per operator type
    M3: throughput (events/second)
    M4: max migration pause (ms) in window, 0 if none
    M5: mean AODE recalibration overhead (ms)
    M6: mean edge resource utilization [0..1]
    """
    timestamp:             float
    config_id:             str
    repetition:            int
    m1_p95_latency_ms:     dict[str, float] = field(default_factory=dict)
    m2_slo_compliance:     dict[str, float] = field(default_factory=dict)
    m3_throughput_eps:     float = 0.0
    m4_migration_pause_ms: float = 0.0
    m5_aode_overhead_ms:   float = 0.0
    m6_edge_utilization:   float = 0.0


class MetricsCollector:
    """Collects M1–M6 every 5 seconds. Warmup period stored separately."""

    def __init__(self, config_id: str, repetition: int, warmup_s: int = 600):
        self._config_id   = config_id
        self._repetition  = repetition
        self._warmup_s    = warmup_s
        self._start_time  = time.monotonic()
        self._snapshots: list[MetricSnapshot] = []

        self._latency_samples: dict[str, list[float]]  = {}
        self._slo_counters:    dict[str, tuple[int, int]] = {}
        self._ingest_count     = 0
        self._ingest_window_start = time.monotonic()
        self._migration_times: list[float] = []
        self._aode_overhead_samples: list[float] = []
        self._edge_utilizations: list[float] = []
        self._collection_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        self._start_time = time.monotonic()
        self._ingest_window_start = self._start_time
        self._collection_task = asyncio.create_task(self._collection_loop())
        log.info("MetricsCollector started: config=%s rep=%d warmup=%ds",
                 self._config_id, self._repetition, self._warmup_s)

    def stop(self) -> None:
        if self._collection_task:
            self._collection_task.cancel()

    def record_latency(self, operator_type: str, latency_ms: float, slo_ms: Optional[float] = None) -> None:
        self._latency_samples.setdefault(operator_type, []).append(latency_ms)
        if slo_ms is not None:
            compliant, total = self._slo_counters.get(operator_type, (0, 0))
            self._slo_counters[operator_type] = (compliant + (1 if latency_ms <= slo_ms else 0), total + 1)

    def record_ingest(self, n_events: int) -> None:
        self._ingest_count += n_events

    def record_migration(self, pause_duration_ms: float) -> None:
        self._migration_times.append(pause_duration_ms)

    def record_aode_overhead(self, duration_ms: float) -> None:
        self._aode_overhead_samples.append(duration_ms)

    def record_edge_utilization(self, cpu_frac: float, mem_frac: float) -> None:
        self._edge_utilizations.append(max(cpu_frac, mem_frac))

    def get_snapshots(self, warmup_only: bool = False, post_warmup_only: bool = True) -> list[MetricSnapshot]:
        warmup_end = self._start_time + self._warmup_s
        if warmup_only:
            return [s for s in self._snapshots if (self._start_time + s.timestamp) < warmup_end]
        if post_warmup_only:
            return [s for s in self._snapshots if s.timestamp >= self._warmup_s]
        return list(self._snapshots)

    async def _collection_loop(self) -> None:
        while True:
            try:
                self._snapshots.append(self._build_snapshot())
            except Exception as e:
                log.error("Metrics collection error: %s", e)
            await asyncio.sleep(5)

    def _build_snapshot(self) -> MetricSnapshot:
        now     = time.monotonic()
        elapsed = now - self._start_time

        # M1
        m1 = {}
        for op_type, samples in self._latency_samples.items():
            if samples:
                sorted_s = sorted(samples[-1000:])
                idx = min(len(sorted_s) - 1, max(0, math.ceil(len(sorted_s) * 0.95) - 1))
                m1[op_type] = sorted_s[idx]
        self._latency_samples.clear()

        # M2
        m2 = {}
        for op_type, (compliant, total) in self._slo_counters.items():
            m2[op_type] = compliant / total if total > 0 else 1.0
        self._slo_counters.clear()

        # M3
        window_s = now - self._ingest_window_start
        m3 = self._ingest_count / max(window_s, 1.0)
        self._ingest_count = 0
        self._ingest_window_start = now

        # M4
        m4 = max(self._migration_times) if self._migration_times else 0.0
        self._migration_times.clear()

        # M5
        m5 = statistics.mean(self._aode_overhead_samples) if self._aode_overhead_samples else 0.0
        self._aode_overhead_samples.clear()

        # M6
        m6 = statistics.mean(self._edge_utilizations) if self._edge_utilizations else 0.0
        self._edge_utilizations.clear()

        return MetricSnapshot(
            timestamp=elapsed, config_id=self._config_id, repetition=self._repetition,
            m1_p95_latency_ms=m1, m2_slo_compliance=m2,
            m3_throughput_eps=m3, m4_migration_pause_ms=m4,
            m5_aode_overhead_ms=m5, m6_edge_utilization=m6,
        )
