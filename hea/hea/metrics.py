import math
import time
import asyncio
import logging
from collections import deque

log = logging.getLogger(__name__)

EWMA_ALPHA = 0.2


class HEAMetrics:
    def __init__(self, alpha: float = EWMA_ALPHA, rtt_probe_interval_ms: int = 500,
                 cloud_kafka_endpoint: str = "localhost:9092"):
        self._alpha = alpha
        self._rtt_probe_ms = rtt_probe_interval_ms
        self._cloud_endpoint = cloud_kafka_endpoint

        self.cpu_utilization:    float = 0.0
        self.memory_utilization: float = 0.0
        self.rtt_ms:             float = 10.0
        self.ingest_rate_eps:    float = 0.0

        self._latency_samples: dict[str, deque] = {}
        self._ingest_counts:   deque = deque(maxlen=300)

        self._task: asyncio.Task | None = None

    def record_latency(self, operator_id: str, latency_ms: float) -> None:
        if operator_id not in self._latency_samples:
            self._latency_samples[operator_id] = deque(maxlen=1000)
        self._latency_samples[operator_id].append(latency_ms)

    def record_ingest(self, n_records: int) -> None:
        self._ingest_counts.append((time.monotonic(), n_records))

    def get_operator_p95(self) -> dict[str, float]:
        result = {}
        for oid, samples in self._latency_samples.items():
            if samples:
                sorted_s = sorted(samples)
                idx = min(len(sorted_s) - 1, max(0, math.ceil(len(sorted_s) * 0.95) - 1))
                result[oid] = sorted_s[idx]
        return result

    def _compute_ingest_rate(self) -> float:
        now = time.monotonic()
        cutoff = now - 30.0
        recent = [(t, n) for t, n in self._ingest_counts if t >= cutoff]
        if not recent:
            return 0.0
        total = sum(n for _, n in recent)
        window = now - recent[0][0] if len(recent) > 1 else 1.0
        return total / max(window, 1.0)

    def start(self) -> None:
        self._task = asyncio.create_task(self._update_loop())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _update_loop(self) -> None:
        import psutil
        while True:
            try:
                cpu_sample = psutil.cpu_percent(interval=None) / 100.0
                mem_sample = psutil.virtual_memory().percent / 100.0
                self.cpu_utilization = (1 - self._alpha) * self.cpu_utilization + self._alpha * cpu_sample
                self.memory_utilization = (1 - self._alpha) * self.memory_utilization + self._alpha * mem_sample
                rtt = await self._probe_rtt()
                self.rtt_ms = (1 - self._alpha) * self.rtt_ms + self._alpha * rtt
                self.ingest_rate_eps = self._compute_ingest_rate()
            except Exception as e:
                log.warning("Metrics update error: %s", e)
            await asyncio.sleep(self._rtt_probe_ms / 1000.0)

    async def _probe_rtt(self) -> float:
        host, port_str = self._cloud_endpoint.rsplit(":", 1)
        port = int(port_str)
        start = time.monotonic()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=1.0
            )
            writer.close()
            await writer.wait_closed()
        except Exception:
            return 1000.0
        return (time.monotonic() - start) * 1000.0
