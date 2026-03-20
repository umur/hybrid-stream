import asyncio
import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from ..config import AODEConfig

log = logging.getLogger(__name__)


@dataclass
class HEATelemetry:
    hea_id:              str
    cpu_utilization:     float
    memory_utilization:  float
    rtt_ms:              float
    ingest_rate_eps:     float
    operator_p95_ms:     Dict[str, float]
    timestamp_ms:        int
    reachable:           bool
    collection_latency_ms: float = 0.0


class TelemetryCollector:
    def __init__(self, config: AODEConfig) -> None:
        self._config = config
        self._last_telemetry: Dict[str, HEATelemetry] = {}
        self._collection_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._collection_task = asyncio.create_task(self._collection_loop())

    async def stop(self) -> None:
        if self._collection_task:
            self._collection_task.cancel()

    def get_latest_telemetry(self) -> Dict[str, HEATelemetry]:
        return dict(self._last_telemetry)

    def get_reachable_heas(self) -> List[str]:
        return [hea_id for hea_id, tel in self._last_telemetry.items() if tel.reachable]

    def get_tier_utilization(self, hea_id: str) -> tuple[float, float]:
        tel = self._last_telemetry.get(hea_id)
        if not tel or not tel.reachable:
            return 0.9, 0.9
        return tel.cpu_utilization, tel.memory_utilization

    def get_operator_latency(self, operator_id: str) -> Optional[float]:
        latencies = []
        for tel in self._last_telemetry.values():
            if tel.reachable and operator_id in tel.operator_p95_ms:
                latencies.append(tel.operator_p95_ms[operator_id])
        return max(latencies) if latencies else None

    def _get_stub(self, hea_id: str):
        """Get gRPC stub for a specific HEA. Override in tests."""
        return None

    async def _collect_one(self, hea_id: str) -> HEATelemetry:
        """Collect telemetry from a single HEA node."""
        start_ns = time.monotonic_ns()
        try:
            stub = self._get_stub(hea_id)
            response = await stub.CollectTelemetry()
            collection_latency_ms = (time.monotonic_ns() - start_ns) / 1e6

            return HEATelemetry(
                hea_id=hea_id,
                cpu_utilization=response.cpu_utilization,
                memory_utilization=response.memory_utilization,
                rtt_ms=response.rtt_ms,
                ingest_rate_eps=response.ingest_rate_eps,
                operator_p95_ms=dict(response.operator_p95_ms),
                timestamp_ms=int(time.time() * 1000),
                reachable=True,
                collection_latency_ms=collection_latency_ms,
            )
        except Exception as e:
            log.warning("HEA %s unreachable: %s", hea_id, e)
            return HEATelemetry(
                hea_id=hea_id,
                cpu_utilization=0.0,
                memory_utilization=0.0,
                rtt_ms=1000.0,
                ingest_rate_eps=0.0,
                operator_p95_ms={},
                timestamp_ms=int(time.time() * 1000),
                reachable=False,
            )

    async def _collection_loop(self) -> None:
        while True:
            try:
                await self._collect_all()
            except Exception as e:
                log.error("Telemetry collection error: %s", e)
            await asyncio.sleep(self._config.telemetry_interval_s)

    async def _collect_all(self) -> None:
        for hea_id in list(self._last_telemetry.keys()):
            tel = await self._collect_one(hea_id)
            self._last_telemetry[hea_id] = tel
