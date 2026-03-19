# Phase 3 — Adaptive Offloading Decision Engine (AODE)

> **Depends on:** Phase 1 complete (proto stubs), Phase 2 complete (HEA gRPC interface)  
> **Goal:** A production-ready Python 3.12 orchestrator that monitors HEA telemetry, runs the scoring algorithm (Eq. 1), and triggers PCTR migrations via the 4-phase protocol.  
> Estimated scope: ~1,800 lines of Python.

---

## Deliverables Checklist

- [ ] `aode/pyproject.toml` and `aode/Dockerfile`
- [ ] `aode/aode/main.py` — asyncio entrypoint with HA primary/standby
- [ ] `aode/aode/config.py` — pydantic settings with etcd persistence
- [ ] `aode/aode/telemetry/collector.py` — poll all HEA nodes every 5s
- [ ] `aode/aode/scoring/algorithm.py` — Equation 1 implementation
- [ ] `aode/aode/scoring/weights.py` — latency-first/balanced/resource presets
- [ ] `aode/aode/migration/pctr.py` — 4-phase PCTR protocol orchestrator
- [ ] `aode/aode/placement/optimizer.py` — recalibration Algorithm 1
- [ ] `aode/aode/placement/state.py` — current operator→tier mapping
- [ ] `aode/aode/etcd/client.py` — distributed state + leader election
- [ ] `aode/aode/grpc/server.py` — management API for external control
- [ ] `aode/aode/grpc/clients.py` — gRPC clients to HEA and Flink Connector
- [ ] `aode/tests/` — unit + integration tests
- [ ] All tests passing

---

## Step 1 — `aode/pyproject.toml`

```toml
[tool.poetry]
name = "hybridstream-aode"
version = "0.1.0"
description = "HybridStream Adaptive Offloading Decision Engine"
packages = [{include = "aode"}]

[tool.poetry.dependencies]
python = "^3.12"
hybridstream-common = {path = "../hybridstream-common", develop = true}
grpcio = "1.62.0"
grpcio-tools = "1.62.0"
etcd3 = "^0.12"
pydantic = "^2.0"
pydantic-settings = "^2.0"
numpy = "^1.26"
scipy = "^1.12"
asyncio-mqtt = "^0.16"  # for optional MQTT telemetry export

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"
```

---

## Step 2 — `aode/aode/config.py`

```python
from pydantic_settings import BaseSettings
from pydantic import Field


class AODEConfig(BaseSettings):
    # Identity
    instance_id:            str   = Field("aode-1",              env="AODE_INSTANCE_ID")
    cluster_id:             str   = Field("default",             env="AODE_CLUSTER_ID")

    # gRPC server
    grpc_port:              int   = Field(50052,                 env="AODE_GRPC_PORT")

    # etcd for HA state
    etcd_endpoints:         list[str] = Field(["localhost:2379"], env="AODE_ETCD_ENDPOINTS")
    etcd_key_prefix:        str   = Field("/aode/",              env="AODE_ETCD_PREFIX")
    leader_election_ttl:    int   = Field(30,                    env="AODE_LEADER_TTL")

    # Telemetry collection
    telemetry_interval_s:   int   = Field(5,                     env="AODE_TELEMETRY_INTERVAL")
    telemetry_timeout_s:    int   = Field(2,                     env="AODE_TELEMETRY_TIMEOUT")

    # Recalibration
    recalibration_interval_s: int = Field(5,                     env="AODE_RECALIBRATION_INTERVAL")
    recalibration_enabled:  bool  = Field(True,                  env="AODE_RECALIBRATION_ENABLED")

    # Scoring algorithm constants (from paper)
    kappa:                  float = Field(2.0,                   env="AODE_KAPPA")                  # κ contention coefficient
    delta_h:                float = Field(0.15,                  env="AODE_DELTA_H")               # Δₕ hysteresis threshold
    lookahead_horizon_s:    int   = Field(30,                    env="AODE_LOOKAHEAD_HORIZON")     # H
    slo_penalty_factor:     int   = Field(10,                    env="AODE_SLO_PENALTY")          # M

    # Weight presets
    default_weight_preset:  str   = Field("balanced",            env="AODE_DEFAULT_WEIGHTS")       # balanced/latency-first/resource-efficient

    # HEA and Flink Connector discovery
    hea_discovery_method:   str   = Field("static",              env="AODE_HEA_DISCOVERY")         # static/etcd/k8s
    hea_endpoints:          list[str] = Field([                  env="AODE_HEA_ENDPOINTS")
        "edge-node-1:50051", "edge-node-2:50051", "edge-node-3:50051", "edge-node-4:50051"
    ])
    flink_connector_endpoint: str = Field("localhost:50053",     env="AODE_FLINK_CONNECTOR")

    # PCTR migration
    migration_timeout_s:    int   = Field(300,                   env="AODE_MIGRATION_TIMEOUT")     # 5 min max per migration
    drain_timeout_s:        int   = Field(60,                    env="AODE_DRAIN_TIMEOUT")         # ω_drain = 60s

    # Object store
    minio_endpoint:         str   = Field("http://localhost:9000", env="AODE_MINIO_ENDPOINT")
    minio_access_key:       str   = Field("hybridstream",         env="AODE_MINIO_ACCESS_KEY")
    minio_secret_key:       str   = Field("hybridstream123",      env="AODE_MINIO_SECRET_KEY")
    minio_bucket:           str   = Field("hybridstream-snapshots", env="AODE_MINIO_BUCKET")

    class Config:
        env_file = ".env"
```

---

## Step 3 — `aode/aode/telemetry/collector.py`

```python
import asyncio
import logging
import time
import grpc
from typing import Dict, List, Optional
from dataclasses import dataclass

from ..config import AODEConfig
from ..grpc.clients import HEAClient
from hybridstream.proto import hybridstream_pb2 as pb2

log = logging.getLogger(__name__)


@dataclass
class HEATelemetry:
    """Telemetry snapshot from a single HEA node."""
    hea_id:              str
    cpu_utilization:     float
    memory_utilization:  float
    rtt_ms:              float
    ingest_rate_eps:     float
    operator_p95_ms:     Dict[str, float]  # operator_id → p95 latency
    timestamp_ms:        int
    reachable:           bool
    collection_latency_ms: float = 0.0


class TelemetryCollector:
    """
    Polls all HEA nodes every N seconds for resource and performance metrics.
    Provides EWMA-smoothed aggregates for the scoring algorithm.
    """

    def __init__(self, config: AODEConfig):
        self._config = config
        self._hea_clients: Dict[str, HEAClient] = {}
        self._last_telemetry: Dict[str, HEATelemetry] = {}
        self._collection_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Initialize gRPC clients to all configured HEA endpoints."""
        for endpoint in self._config.hea_endpoints:
            hea_id = endpoint.split(":")[0]  # Extract hostname as HEA ID
            self._hea_clients[hea_id] = HEAClient(endpoint)
            await self._hea_clients[hea_id].connect()

        self._collection_task = asyncio.create_task(self._collection_loop())
        log.info("TelemetryCollector started with %d HEA endpoints", len(self._hea_clients))

    async def stop(self) -> None:
        if self._collection_task:
            self._collection_task.cancel()
        for client in self._hea_clients.values():
            await client.close()

    def get_latest_telemetry(self) -> Dict[str, HEATelemetry]:
        """Return the most recent telemetry snapshot from all HEA nodes."""
        return dict(self._last_telemetry)

    def get_reachable_heas(self) -> List[str]:
        """Return list of HEA IDs that responded to the last collection cycle."""
        return [hea_id for hea_id, tel in self._last_telemetry.items() if tel.reachable]

    def get_tier_utilization(self, hea_id: str) -> tuple[float, float]:
        """
        Return (cpu_utilization, memory_utilization) for a specific HEA.
        Used by Equation 1 for ρⱼ calculation.
        """
        tel = self._last_telemetry.get(hea_id)
        if not tel or not tel.reachable:
            return 0.9, 0.9  # Penalize unreachable nodes with high utilization
        return tel.cpu_utilization, tel.memory_utilization

    def get_operator_latency(self, operator_id: str) -> Optional[float]:
        """
        Return p95 latency for a specific operator across all HEA nodes.
        If the operator runs on multiple HEAs, return the worst-case (max) p95.
        """
        latencies = []
        for tel in self._last_telemetry.values():
            if tel.reachable and operator_id in tel.operator_p95_ms:
                latencies.append(tel.operator_p95_ms[operator_id])
        return max(latencies) if latencies else None

    async def _collection_loop(self) -> None:
        """Poll all HEA nodes every telemetry_interval_s seconds."""
        while True:
            try:
                await self._collect_all()
            except Exception as e:
                log.error("Telemetry collection error: %s", e)

            await asyncio.sleep(self._config.telemetry_interval_s)

    async def _collect_all(self) -> None:
        """Concurrently collect telemetry from all HEA nodes."""
        tasks = []
        for hea_id, client in self._hea_clients.items():
            task = asyncio.create_task(self._collect_one(hea_id, client))
            tasks.append(task)

        # Wait for all with timeout
        timeout = self._config.telemetry_timeout_s
        done, pending = await asyncio.wait(tasks, timeout=timeout, return_when=asyncio.ALL_COMPLETED)

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        # Process results
        for task in done:
            try:
                hea_id, telemetry = await task
                self._last_telemetry[hea_id] = telemetry
            except Exception as e:
                log.warning("Telemetry collection failed: %s", e)

    async def _collect_one(self, hea_id: str, client: HEAClient) -> tuple[str, HEATelemetry]:
        """Collect telemetry from a single HEA node."""
        start_ns = time.monotonic_ns()
        try:
            response = await client.get_telemetry()
            collection_latency_ms = (time.monotonic_ns() - start_ns) / 1e6

            return hea_id, HEATelemetry(
                hea_id              = response.hea_id,
                cpu_utilization     = response.cpu_utilization,
                memory_utilization  = response.memory_utilization,
                rtt_ms              = response.rtt_ms if hasattr(response, 'rtt_ms') else 10.0,
                ingest_rate_eps     = response.ingest_rate_eps,
                operator_p95_ms     = dict(response.operator_p95_ms),
                timestamp_ms        = response.timestamp_ms,
                reachable           = True,
                collection_latency_ms = collection_latency_ms,
            )
        except grpc.RpcError as e:
            log.warning("HEA %s unreachable: %s", hea_id, e.code())
            return hea_id, HEATelemetry(
                hea_id              = hea_id,
                cpu_utilization     = 0.0,
                memory_utilization  = 0.0,
                rtt_ms              = 1000.0,
                ingest_rate_eps     = 0.0,
                operator_p95_ms     = {},
                timestamp_ms        = int(time.time() * 1000),
                reachable           = False,
            )
```

---

## Step 4 — `aode/aode/scoring/algorithm.py`

Implementation of Equation 1 from the paper.

```python
import numpy as np
from typing import Dict, List, Tuple, Optional
from ..telemetry.collector import TelemetryCollector
from ..config import AODEConfig
from .weights import get_weight_preset, WeightPreset


class ScoringAlgorithm:
    """
    Implements Equation 1: S(oᵢ, tⱼ) = w₁·Φ_lat + w₂·Φ_res + w₃·Φ_net + w₄·Φ_slo

    The scoring matrix is computed for all (operator_type, tier) pairs.
    For workloads with many operator instances (e.g., W2 with 521 instances),
    we score at the operator TYPE level, not individual instances.
    """

    def __init__(self, config: AODEConfig, telemetry: TelemetryCollector):
        self._config = config
        self._telemetry = telemetry
        self._weights: WeightPreset = get_weight_preset(config.default_weight_preset)

    def set_weights(self, preset_name: str) -> None:
        """Switch to a different weight configuration (latency-first, balanced, resource-efficient)."""
        self._weights = get_weight_preset(preset_name)

    def compute_scores(
        self,
        operator_types: List[str],
        tiers: List[str],
        slo_map: Dict[str, Optional[float]],   # operator_type → SLO in ms (None = batch)
        lambda_map: Dict[str, str],            # operator_type → 'critical'|'standard'|'batch'
    ) -> np.ndarray:
        """
        Compute the scoring matrix S[i, j] for all (operator_type[i], tier[j]) pairs.

        Args:
            operator_types: List of operator type names (e.g., ["VehicleDetector", "ZoneAggregator"])
            tiers:          List of tier IDs (e.g., ["edge-node-1", "edge-node-2", "cloud"])
            slo_map:        operator_type → SLO in ms (None for batch operators)
            lambda_map:     operator_type → latency class ('critical', 'standard', 'batch')

        Returns:
            Scoring matrix S[i, j] where S[i, j] = score of placing operator_types[i] on tiers[j].
            Lower scores = better placement.
        """
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
                    self._weights.w_lat * phi_lat +
                    self._weights.w_res * phi_res +
                    self._weights.w_net * phi_net +
                    self._weights.w_slo * phi_slo
                )

        return scores

    def _compute_phi_lat(self, operator_type: str, tier_id: str, lambda_class: str) -> float:
        """
        Φ_lat = λ-class latency factor × observed p95 latency.
        
        λ-class weights:
        - critical: 3.0 (heavy penalty for high latency)
        - standard: 1.0 (baseline)
        - batch:    0.1 (latency-insensitive)
        """
        lambda_weights = {"critical": 3.0, "standard": 1.0, "batch": 0.1}
        lambda_factor = lambda_weights.get(lambda_class, 1.0)

        # Get observed p95 latency for this operator type
        # For simplicity, assume operator instances of the same type have similar latency
        observed_latency_ms = self._telemetry.get_operator_latency(operator_type) or 1.0

        return lambda_factor * observed_latency_ms

    def _compute_phi_res(self, tier_id: str) -> float:
        """
        Φ_res = κ·ρⱼ / (1 - ρⱼ)

        Where ρⱼ = max(CPU, memory) utilization on tier j.
        κ = 2.0 (contention coefficient from M/D/1 queueing theory).
        """
        cpu_util, mem_util = self._telemetry.get_tier_utilization(tier_id)
        rho_j = max(cpu_util, mem_util)

        # Avoid division by zero: cap utilization at 99%
        rho_j = min(rho_j, 0.99)

        return self._config.kappa * rho_j / (1 - rho_j)

    def _compute_phi_net(self, tier_id: str) -> float:
        """
        Φ_net = RTT from tier to cloud in ms.
        Edge tiers: actual measured RTT to cloud.
        Cloud tier: RTT = 0 (no network penalty).
        """
        if tier_id == "cloud":
            return 0.0

        tel = self._telemetry.get_latest_telemetry().get(tier_id)
        if tel and tel.reachable:
            return tel.rtt_ms
        else:
            return 1000.0  # Penalize unreachable tiers

    def _compute_phi_slo(self, operator_type: str, tier_id: str, slo_ms: Optional[float]) -> float:
        """
        Φ_slo = M × (observed_latency - SLO) / SLO   if observed_latency > SLO
                0                                     otherwise

        For batch operators (slo_ms = None), use nominal SLO of 3600s to avoid division by zero.
        """
        if slo_ms is None:
            slo_ms = 3600.0 * 1000  # 3600s = 1 hour in ms for batch operators

        observed_latency_ms = self._telemetry.get_operator_latency(operator_type) or 1.0

        if observed_latency_ms <= slo_ms:
            return 0.0
        else:
            violation_ratio = (observed_latency_ms - slo_ms) / slo_ms
            return self._config.slo_penalty_factor * violation_ratio


def find_optimal_placement(
    scores: np.ndarray,
    operator_types: List[str],
    tiers: List[str],
    tier_capacities: Dict[str, int],           # tier → max operators it can handle
) -> Dict[str, str]:
    """
    Greedy assignment: assign each operator type to its lowest-scoring feasible tier.
    
    For workloads with multiple instances per type (e.g., W2's 521 VehicleDetector instances),
    this returns operator_type → tier mapping. The caller distributes instances within the type.

    Args:
        scores:           Scoring matrix S[i, j] from compute_scores()
        operator_types:   List of operator type names
        tiers:            List of tier IDs  
        tier_capacities:  Maximum number of operator types each tier can host

    Returns:
        operator_type → tier_id mapping
    """
    placement = {}
    tier_usage = {tier: 0 for tier in tiers}

    # Sort operators by their minimum score (prioritize hard-to-place operators)
    op_min_scores = [(i, np.min(scores[i, :])) for i in range(len(operator_types))]
    op_min_scores.sort(key=lambda x: x[1], reverse=True)  # Descending: hardest first

    for i, _ in op_min_scores:
        op_type = operator_types[i]
        
        # Find the best feasible tier for this operator type
        tier_scores = [(scores[i, j], j) for j in range(len(tiers))]
        tier_scores.sort()  # Ascending: best score first

        assigned = False
        for score, j in tier_scores:
            tier_id = tiers[j]
            if tier_usage[tier_id] < tier_capacities[tier_id]:
                placement[op_type] = tier_id
                tier_usage[tier_id] += 1
                assigned = True
                break

        if not assigned:
            # Fallback: assign to cloud (assume cloud has infinite capacity)
            placement[op_type] = "cloud"

    return placement
```

---

## Step 5 — `aode/aode/scoring/weights.py`

```python
from dataclasses import dataclass
from typing import Dict


@dataclass
class WeightPreset:
    """Weight configuration for Equation 1: w₁·Φ_lat + w₂·Φ_res + w₃·Φ_net + w₄·Φ_slo"""
    name:   str
    w_lat:  float  # w₁ = latency factor weight  
    w_res:  float  # w₂ = resource factor weight
    w_net:  float  # w₃ = network factor weight
    w_slo:  float  # w₄ = SLO penalty weight

    def __post_init__(self):
        # Validate weights sum to 1.0
        total = self.w_lat + self.w_res + self.w_net + self.w_slo
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weight preset '{self.name}': weights must sum to 1.0 (got {total})")


# Predefined weight configurations from the paper
WEIGHT_PRESETS: Dict[str, WeightPreset] = {
    "latency-first": WeightPreset(
        name="latency-first",
        w_lat=0.55,  # Heavy emphasis on low latency
        w_res=0.10,  # Light resource consideration
        w_net=0.20,  # Moderate network awareness
        w_slo=0.15,  # Moderate SLO compliance
    ),
    "balanced": WeightPreset(
        name="balanced",
        w_lat=0.30,  # Balanced latency priority
        w_res=0.30,  # Balanced resource priority
        w_net=0.20,  # Moderate network consideration
        w_slo=0.20,  # Moderate SLO compliance
    ),
    "resource-efficient": WeightPreset(
        name="resource-efficient", 
        w_lat=0.20,  # Lower latency priority
        w_res=0.50,  # Heavy resource optimization
        w_net=0.20,  # Moderate network consideration
        w_slo=0.10,  # Light SLO penalty (accept some violations for efficiency)
    ),
}


def get_weight_preset(name: str) -> WeightPreset:
    """Get a predefined weight configuration by name."""
    if name not in WEIGHT_PRESETS:
        raise ValueError(f"Unknown weight preset '{name}'. Available: {list(WEIGHT_PRESETS.keys())}")
    return WEIGHT_PRESETS[name]


def create_custom_preset(name: str, w_lat: float, w_res: float, w_net: float, w_slo: float) -> WeightPreset:
    """Create a custom weight preset with validation."""
    return WeightPreset(name=name, w_lat=w_lat, w_res=w_res, w_net=w_net, w_slo=w_slo)
```

---

## Step 6 — `aode/aode/migration/pctr.py`

The 4-phase PCTR migration protocol orchestrator.

```python
import asyncio
import logging
import json
import time
from typing import Dict, Optional, List
from enum import Enum

from ..config import AODEConfig
from ..grpc.clients import HEAClient, FlinkConnectorClient
from hybridstream.common.object_store import ObjectStore

log = logging.getLogger(__name__)


class MigrationPhase(Enum):
    PHASE_1_DRAIN   = "drain"
    PHASE_2_SNAP    = "snapshot" 
    PHASE_3_RESTORE = "restore"
    PHASE_4_TERM    = "terminate"


class PCTRMigration:
    """
    Orchestrates the 4-phase pause-checkpoint-transfer-resume protocol for a single operator.
    """

    def __init__(
        self,
        migration_id: str,
        operator_id: str,
        source_tier: str,
        target_tier: str,
        config: AODEConfig,
        hea_clients: Dict[str, HEAClient],
        flink_client: FlinkConnectorClient,
        object_store: ObjectStore,
    ):
        self.migration_id = migration_id
        self.operator_id = operator_id
        self.source_tier = source_tier
        self.target_tier = target_tier
        self._config = config
        self._hea_clients = hea_clients
        self._flink_client = flink_client
        self._object_store = object_store

        self.phase = MigrationPhase.PHASE_1_DRAIN
        self.start_time = time.monotonic()
        self.drain_offset_map: Dict[int, int] = {}
        self.snapshot_object_key: Optional[str] = None
        self.snapshot_size: int = 0
        self.completed = False
        self.error: Optional[str] = None

    async def execute(self) -> bool:
        """
        Execute the full 4-phase PCTR migration.
        Returns True on success, False on error.
        """
        log.info("Starting PCTR migration %s: %s %s→%s", 
                 self.migration_id, self.operator_id, self.source_tier, self.target_tier)

        try:
            await self._phase_1_drain()
            await self._phase_2_snapshot()
            await self._phase_3_restore()
            await self._phase_4_terminate()
            
            self.completed = True
            elapsed = time.monotonic() - self.start_time
            log.info("PCTR migration %s completed in %.1fs", self.migration_id, elapsed)
            return True

        except Exception as e:
            self.error = str(e)
            log.error("PCTR migration %s failed in %s: %s", self.migration_id, self.phase.value, e)
            return False

    async def _phase_1_drain(self) -> None:
        """
        Phase 1: Drain operator input queue to ω_drain threshold.
        Upstreams continue producing; output is routed to migration buffer.
        """
        self.phase = MigrationPhase.PHASE_1_DRAIN
        
        source_client = self._hea_clients.get(self.source_tier)
        if not source_client:
            raise ValueError(f"No HEA client for source tier: {self.source_tier}")

        # TODO: Implement drain logic via gRPC to source HEA
        # For now, simulate with a timeout
        drain_timeout = self._config.drain_timeout_s
        
        log.debug("Phase 1: Draining operator %s (timeout=%ds)", self.operator_id, drain_timeout)
        await asyncio.sleep(min(2.0, drain_timeout))  # Simulate drain
        
        # Mock drain offset map (in real implementation, get from Kafka consumer position)
        self.drain_offset_map = {0: 12345, 1: 12346, 2: 12347}  # partition → offset

    async def _phase_2_snapshot(self) -> None:
        """
        Phase 2: Create operator state snapshot and upload to object store.
        """
        self.phase = MigrationPhase.PHASE_2_SNAP
        
        source_client = self._hea_clients.get(self.source_tier)
        if not source_client:
            raise ValueError(f"No HEA client for source tier: {self.source_tier}")

        migration_seq = int(time.time())  # Use timestamp as sequence number
        
        log.debug("Phase 2: Creating snapshot for operator %s", self.operator_id)
        
        response = await source_client.trigger_snapshot(
            operator_id=self.operator_id,
            migration_seq=migration_seq,
            drain_offset_map=json.dumps(self.drain_offset_map),
        )
        
        if response.error_msg:
            raise RuntimeError(f"Snapshot failed: {response.error_msg}")
            
        self.snapshot_object_key = response.object_key
        self.snapshot_size = response.byte_size
        
        log.debug("Phase 2: Snapshot created: key=%s size=%d bytes", 
                 self.snapshot_object_key, self.snapshot_size)

    async def _phase_3_restore(self) -> None:
        """
        Phase 3: Download snapshot and restore operator on target tier.
        """
        self.phase = MigrationPhase.PHASE_3_RESTORE
        
        if self.target_tier == "cloud":
            # Restore via Flink Connector
            log.debug("Phase 3: Restoring operator %s on cloud via Flink", self.operator_id)
            await self._flink_client.restore_operator(
                operator_id=self.operator_id,
                snapshot_key=self.snapshot_object_key,
            )
        else:
            # Restore on target HEA
            target_client = self._hea_clients.get(self.target_tier)
            if not target_client:
                raise ValueError(f"No HEA client for target tier: {self.target_tier}")
                
            log.debug("Phase 3: Restoring operator %s on HEA %s", self.operator_id, self.target_tier)
            # TODO: Implement restore_operator RPC in HEA gRPC interface
            # For now, this is a placeholder
            await asyncio.sleep(0.1)

    async def _phase_4_terminate(self) -> None:
        """
        Phase 4: Terminate operator on source tier and release resources.
        """
        self.phase = MigrationPhase.PHASE_4_TERM
        
        source_client = self._hea_clients.get(self.source_tier)
        if not source_client:
            raise ValueError(f"No HEA client for source tier: {self.source_tier}")

        log.debug("Phase 4: Terminating operator %s on %s", self.operator_id, self.source_tier)
        
        response = await source_client.terminate_operator(
            operator_id=self.operator_id,
            flush_state=True,
        )
        
        if not response.success:
            raise RuntimeError(f"Termination failed: {response.error_msg}")

    def get_status(self) -> Dict:
        """Return migration status for monitoring/debugging."""
        elapsed = time.monotonic() - self.start_time
        return {
            "migration_id": self.migration_id,
            "operator_id": self.operator_id,
            "source_tier": self.source_tier,
            "target_tier": self.target_tier,
            "phase": self.phase.value,
            "elapsed_s": round(elapsed, 2),
            "snapshot_size": self.snapshot_size,
            "completed": self.completed,
            "error": self.error,
        }


class PCTROrchestrator:
    """
    Manages multiple concurrent PCTR migrations.
    Enforces safety constraints (e.g., no concurrent migrations for the same operator).
    """

    def __init__(
        self,
        config: AODEConfig,
        hea_clients: Dict[str, HEAClient],
        flink_client: FlinkConnectorClient,
        object_store: ObjectStore,
    ):
        self._config = config
        self._hea_clients = hea_clients
        self._flink_client = flink_client
        self._object_store = object_store

        self._active_migrations: Dict[str, PCTRMigration] = {}  # operator_id → migration
        self._migration_counter = 0

    async def migrate_operator(
        self,
        operator_id: str,
        source_tier: str,
        target_tier: str,
    ) -> str:
        """
        Start a new PCTR migration for an operator.
        Returns migration_id for tracking.
        Raises ValueError if operator is already being migrated.
        """
        if operator_id in self._active_migrations:
            raise ValueError(f"Operator {operator_id} is already being migrated")

        self._migration_counter += 1
        migration_id = f"migration-{self._migration_counter:04d}"

        migration = PCTRMigration(
            migration_id=migration_id,
            operator_id=operator_id,
            source_tier=source_tier,
            target_tier=target_tier,
            config=self._config,
            hea_clients=self._hea_clients,
            flink_client=self._flink_client,
            object_store=self._object_store,
        )

        self._active_migrations[operator_id] = migration
        
        # Execute migration in background
        asyncio.create_task(self._execute_migration(migration))
        
        return migration_id

    async def _execute_migration(self, migration: PCTRMigration) -> None:
        """Execute a migration and clean up when complete."""
        try:
            timeout = self._config.migration_timeout_s
            await asyncio.wait_for(migration.execute(), timeout=timeout)
        except asyncio.TimeoutError:
            migration.error = f"Migration timed out after {timeout}s"
            log.error("Migration %s timed out", migration.migration_id)
        finally:
            # Remove from active migrations
            self._active_migrations.pop(migration.operator_id, None)

    def get_migration_status(self, operator_id: str) -> Optional[Dict]:
        """Get status of an active migration, or None if not found."""
        migration = self._active_migrations.get(operator_id)
        return migration.get_status() if migration else None

    def list_active_migrations(self) -> List[Dict]:
        """Return status of all active migrations."""
        return [m.get_status() for m in self._active_migrations.values()]
```

---

## Step 7 — `aode/aode/placement/optimizer.py`

Algorithm 1 from the paper — the recalibration logic.

```python
import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Tuple

from ..scoring.algorithm import ScoringAlgorithm, find_optimal_placement
from ..migration.pctr import PCTROrchestrator
from ..placement.state import PlacementState
from ..config import AODEConfig

log = logging.getLogger(__name__)


class PlacementOptimizer:
    """
    Implements Algorithm 1: Adaptive Recalibration
    
    Monitors system state and triggers operator migrations when:
    1. Current placement score deteriorates significantly (hysteresis threshold)
    2. A better placement option becomes available
    3. SLO violations exceed acceptable bounds
    """

    def __init__(
        self,
        config: AODEConfig,
        scoring: ScoringAlgorithm,
        migration_orchestrator: PCTROrchestrator,
        placement_state: PlacementState,
    ):
        self._config = config
        self._scoring = scoring
        self._migration = migration_orchestrator
        self._placement = placement_state

        self._optimization_task: Optional[asyncio.Task] = None
        self._last_optimization = 0.0

    async def start(self) -> None:
        """Start the recalibration background task."""
        if self._config.recalibration_enabled:
            self._optimization_task = asyncio.create_task(self._optimization_loop())
            log.info("PlacementOptimizer started (interval=%ds)", self._config.recalibration_interval_s)

    async def stop(self) -> None:
        """Stop the recalibration task."""
        if self._optimization_task:
            self._optimization_task.cancel()

    async def force_recalibration(self, reason: str = "manual") -> Dict:
        """
        Trigger immediate recalibration outside the normal schedule.
        Returns summary of actions taken.
        """
        log.info("Forced recalibration triggered: %s", reason)
        return await self._run_optimization()

    async def _optimization_loop(self) -> None:
        """Background task that runs Algorithm 1 every N seconds."""
        while True:
            try:
                await self._run_optimization()
                self._last_optimization = time.monotonic()
            except Exception as e:
                log.error("Optimization cycle error: %s", e)

            await asyncio.sleep(self._config.recalibration_interval_s)

    async def _run_optimization(self) -> Dict:
        """
        Algorithm 1: Adaptive Recalibration
        
        1. Get current operator→tier mapping
        2. Compute optimal placement using current telemetry
        3. Identify operators with significant score improvements
        4. Trigger migrations for operators exceeding hysteresis threshold
        """
        start_time = time.monotonic()
        
        # Step 1: Get current placement state
        current_placement = self._placement.get_current_placement()
        operator_types = list(current_placement.keys())
        tiers = self._placement.get_available_tiers()

        if not operator_types:
            return {"status": "no_operators", "duration_ms": 0}

        # Step 2: Compute optimal placement
        slo_map = self._placement.get_slo_map()
        lambda_map = self._placement.get_lambda_map()
        tier_capacities = self._placement.get_tier_capacities()

        scores = self._scoring.compute_scores(operator_types, tiers, slo_map, lambda_map)
        optimal_placement = find_optimal_placement(scores, operator_types, tiers, tier_capacities)

        # Step 3: Identify migration candidates
        candidates = self._identify_migration_candidates(current_placement, optimal_placement, scores, operator_types, tiers)

        # Step 4: Execute migrations
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
                
                # Update placement state optimistically
                self._placement.update_operator_placement(op_type, target_tier)
                
            except Exception as e:
                log.warning("Failed to start migration for %s: %s", op_type, e)

        duration_ms = (time.monotonic() - start_time) * 1000
        
        result = {
            "status": "completed",
            "duration_ms": round(duration_ms, 1),
            "candidates_evaluated": len(candidates),
            "migrations_started": len(migrations_started),
            "migrations": migrations_started,
        }
        
        if migrations_started:
            log.info("Recalibration triggered %d migrations in %.1fms", 
                    len(migrations_started), duration_ms)
        
        return result

    def _identify_migration_candidates(
        self,
        current_placement: Dict[str, str],
        optimal_placement: Dict[str, str],
        scores: "np.ndarray",
        operator_types: List[str],
        tiers: List[str],
    ) -> List[Tuple[str, str, str, float]]:
        """
        Identify operators that should be migrated based on:
        1. Hysteresis threshold (Δₕ = 0.15)
        2. SLO violations
        3. Availability of better placement options
        
        Returns list of (operator_type, source_tier, target_tier, score_improvement) tuples.
        """
        candidates = []
        delta_h = self._config.delta_h

        for i, op_type in enumerate(operator_types):
            current_tier = current_placement.get(op_type)
            optimal_tier = optimal_placement.get(op_type)

            if not current_tier or not optimal_tier or current_tier == optimal_tier:
                continue  # No change needed

            # Get score improvement
            current_tier_idx = tiers.index(current_tier) if current_tier in tiers else -1
            optimal_tier_idx = tiers.index(optimal_tier) if optimal_tier in tiers else -1

            if current_tier_idx < 0 or optimal_tier_idx < 0:
                continue

            current_score = scores[i, current_tier_idx]
            optimal_score = scores[i, optimal_tier_idx]
            score_improvement = current_score - optimal_score  # Lower score = better

            # Apply hysteresis: only migrate if improvement exceeds threshold
            if score_improvement >= delta_h:
                candidates.append((op_type, current_tier, optimal_tier, score_improvement))

        # Sort by score improvement (largest improvement first)
        candidates.sort(key=lambda x: x[3], reverse=True)

        return candidates

    def get_status(self) -> Dict:
        """Return optimizer status for monitoring."""
        last_run_ago = time.monotonic() - self._last_optimization if self._last_optimization > 0 else None
        active_migrations = self._migration.list_active_migrations()
        
        return {
            "enabled": self._config.recalibration_enabled,
            "interval_s": self._config.recalibration_interval_s,
            "last_run_ago_s": round(last_run_ago, 1) if last_run_ago else None,
            "active_migrations": len(active_migrations),
            "hysteresis_threshold": self._config.delta_h,
        }
```

---

## Step 8 — `aode/aode/placement/state.py`

```python
import asyncio
import logging
from typing import Dict, List, Optional, Set
from ..etcd.client import EtcdClient

log = logging.getLogger(__name__)


class PlacementState:
    """
    Manages the current operator→tier mapping state.
    Persisted in etcd for HA consistency between AODE instances.
    """

    def __init__(self, etcd_client: EtcdClient):
        self._etcd = etcd_client
        self._cache: Dict[str, str] = {}  # operator_type → tier_id
        self._lock = asyncio.Lock()

    async def load_from_etcd(self) -> None:
        """Load placement state from etcd on startup."""
        async with self._lock:
            placement_data = await self._etcd.get_dict("/placement/operators")
            self._cache.update(placement_data)
            log.info("Loaded placement state: %d operators", len(self._cache))

    async def update_operator_placement(self, operator_type: str, tier_id: str) -> None:
        """Update placement for a single operator type."""
        async with self._lock:
            self._cache[operator_type] = tier_id
            await self._etcd.put(f"/placement/operators/{operator_type}", tier_id)

    async def remove_operator(self, operator_type: str) -> None:
        """Remove an operator type from placement tracking."""
        async with self._lock:
            self._cache.pop(operator_type, None)
            await self._etcd.delete(f"/placement/operators/{operator_type}")

    def get_current_placement(self) -> Dict[str, str]:
        """Return a copy of the current operator→tier mapping."""
        return dict(self._cache)

    def get_operators_on_tier(self, tier_id: str) -> List[str]:
        """Return list of operator types currently placed on a specific tier."""
        return [op_type for op_type, t_id in self._cache.items() if t_id == tier_id]

    def get_available_tiers(self) -> List[str]:
        """Return list of all tiers that have at least one operator."""
        return sorted(set(self._cache.values()))

    # Static configuration methods (in real deployment, loaded from config)
    
    def get_slo_map(self) -> Dict[str, Optional[float]]:
        """Return operator_type → SLO mapping. Mock implementation."""
        return {
            "VehicleDetector":    2000.0,  # 2s SLO
            "ZoneAggregator":     None,    # Batch operator
            "PatternDetector":    5000.0,  # 5s SLO
            "RiskCheck":          1.0,     # 1ms SLO (critical)
            "AnomalyDetector":    5.0,     # 5ms SLO
            "StatAggregator":     None,    # Batch operator
            "ComplianceLogger":   None,    # Batch operator
            "NormalizerOperator": 10.0,    # 10ms SLO
            "FeatureAggWindow":   50.0,    # 50ms SLO  
            "MultiStreamJoin":    100.0,   # 100ms SLO
            "BinaryClassifier":   5.0,     # 5ms SLO (critical)
        }

    def get_lambda_map(self) -> Dict[str, str]:
        """Return operator_type → λ-class mapping."""
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
        """Return tier → max operator types capacity."""
        return {
            "edge-node-1": 5,  # 5 operator types max per HEA
            "edge-node-2": 5,
            "edge-node-3": 5,
            "edge-node-4": 5,
            "cloud":       100, # Assume cloud has high capacity
        }
```

---

## Step 9 — `aode/aode/etcd/client.py`

```python
import asyncio
import logging
import json
import time
from typing import Dict, Optional, Any, List
import etcd3

log = logging.getLogger(__name__)


class EtcdClient:
    """
    Async wrapper around etcd3 client for AODE state persistence and leader election.
    Provides high-level operations for placement state and HA coordination.
    """

    def __init__(self, endpoints: List[str], key_prefix: str):
        self._endpoints = endpoints
        self._prefix = key_prefix.rstrip("/")
        self._client: Optional[etcd3.Etcd3Client] = None
        self._lease: Optional[etcd3.Lease] = None

    async def connect(self) -> None:
        """Connect to etcd cluster."""
        # For simplicity, connect to first endpoint (in production: proper cluster handling)
        host, port = self._endpoints[0].split(":")
        self._client = etcd3.client(host=host, port=int(port))
        log.info("Connected to etcd: %s", self._endpoints[0])

    async def close(self) -> None:
        """Close etcd connection."""
        if self._lease:
            await self._lease.revoke()
        if self._client:
            self._client.close()

    async def put(self, key: str, value: str) -> None:
        """Store a key-value pair."""
        full_key = f"{self._prefix}{key}"
        self._client.put(full_key, value)

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a value by key."""
        full_key = f"{self._prefix}{key}"
        result, _ = self._client.get(full_key)
        return result.decode() if result else None

    async def delete(self, key: str) -> None:
        """Delete a key."""
        full_key = f"{self._prefix}{key}"
        self._client.delete(full_key)

    async def get_dict(self, key_prefix: str) -> Dict[str, str]:
        """
        Retrieve all key-value pairs under a prefix.
        Returns {key_suffix: value} mapping.
        """
        full_prefix = f"{self._prefix}{key_prefix}"
        results = self._client.get_prefix(full_prefix)
        
        kv_dict = {}
        for value, metadata in results:
            full_key = metadata.key.decode()
            suffix = full_key[len(full_prefix):].lstrip("/")
            if suffix:  # Skip empty keys
                kv_dict[suffix] = value.decode()
        
        return kv_dict

    async def acquire_leader_lock(self, lock_name: str, ttl_seconds: int = 30) -> bool:
        """
        Try to acquire a leader election lock.
        Returns True if acquired, False if another instance holds it.
        """
        lock_key = f"{self._prefix}/leaders/{lock_name}"
        
        # Create a lease
        lease = self._client.lease(ttl_seconds)
        self._lease = lease
        
        # Try to put the lock key with the lease
        try:
            success = self._client.transaction(
                compare=[self._client.transactions.create(lock_key) == 0],  # Key doesn't exist
                success=[self._client.transactions.put(lock_key, f"leader-{int(time.time())}", lease=lease)],
                failure=[]
            )
            
            if success:
                log.info("Acquired leader lock: %s", lock_name)
                return True
            else:
                log.debug("Failed to acquire leader lock: %s (already held)", lock_name)
                return False
                
        except Exception as e:
            log.error("Leader election error: %s", e)
            return False

    async def release_leader_lock(self) -> None:
        """Release the current leader lock by revoking the lease."""
        if self._lease:
            self._lease.revoke()
            self._lease = None
            log.info("Released leader lock")

    async def maintain_leadership(self, lock_name: str, ttl_seconds: int = 30) -> None:
        """
        Background task to refresh leader lease.
        Run this as an asyncio task after acquiring leadership.
        """
        if not self._lease:
            raise ValueError("No active lease to maintain")
            
        try:
            while True:
                await asyncio.sleep(ttl_seconds // 3)  # Refresh at 1/3 interval
                self._lease.refresh()
                log.debug("Refreshed leader lease for %s", lock_name)
        except Exception as e:
            log.error("Leadership maintenance failed: %s", e)
            raise


class LeaderElection:
    """
    High-level leader election for AODE HA.
    Only the leader instance runs recalibration and migration orchestration.
    """

    def __init__(self, etcd_client: EtcdClient, instance_id: str):
        self._etcd = etcd_client
        self._instance_id = instance_id
        self._is_leader = False
        self._leadership_task: Optional[asyncio.Task] = None

    async def start_election(self) -> bool:
        """
        Start leader election process.
        Returns True if this instance becomes leader.
        """
        is_leader = await self._etcd.acquire_leader_lock("aode", ttl_seconds=30)
        
        if is_leader:
            self._is_leader = True
            self._leadership_task = asyncio.create_task(
                self._etcd.maintain_leadership("aode", ttl_seconds=30)
            )
            log.info("AODE instance %s is now the leader", self._instance_id)
        else:
            log.info("AODE instance %s is in standby mode", self._instance_id)
            
        return is_leader

    async def stop_election(self) -> None:
        """Stop leadership and clean up."""
        if self._leadership_task:
            self._leadership_task.cancel()
        
        if self._is_leader:
            await self._etcd.release_leader_lock()
            self._is_leader = False

    def is_leader(self) -> bool:
        """Return True if this instance is currently the leader."""
        return self._is_leader
```

---

## Step 10 — `aode/aode/grpc/clients.py`

```python
import grpc
import asyncio
from typing import Optional

from hybridstream.proto import hybridstream_pb2 as pb2
from hybridstream.proto import hybridstream_pb2_grpc as pb2_grpc


class HEAClient:
    """gRPC client for communicating with HybridStream Edge Agent nodes."""

    def __init__(self, endpoint: str):
        self._endpoint = endpoint
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[pb2_grpc.HEAManagementStub] = None

    async def connect(self) -> None:
        self._channel = grpc.aio.insecure_channel(self._endpoint)
        self._stub = pb2_grpc.HEAManagementStub(self._channel)

    async def close(self) -> None:
        if self._channel:
            await self._channel.close()

    async def get_telemetry(self) -> pb2.TelemetryResponse:
        """Poll HEA for resource and performance telemetry."""
        request = pb2.TelemetryRequest()
        return await self._stub.GetTelemetry(request, timeout=5)

    async def apply_placement(self, directive_id: str, operator_to_tier: dict) -> pb2.PlacementAck:
        """Send new operator placement to HEA."""
        request = pb2.PlacementDirective(
            directive_id=directive_id,
            operator_to_tier=operator_to_tier,
        )
        return await self._stub.ApplyPlacement(request, timeout=10)

    async def trigger_snapshot(self, operator_id: str, migration_seq: int, drain_offset_map: str) -> pb2.SnapshotResponse:
        """Trigger PCTR Phase 2 snapshot creation."""
        request = pb2.SnapshotRequest(
            operator_id=operator_id,
            migration_seq=migration_seq,
            drain_offset_map=drain_offset_map,
        )
        return await self._stub.TriggerSnapshot(request, timeout=30)

    async def terminate_operator(self, operator_id: str, flush_state: bool = True) -> pb2.TerminateAck:
        """Trigger PCTR Phase 4 operator termination."""
        request = pb2.TerminateRequest(
            operator_id=operator_id,
            flush_state=flush_state,
        )
        return await self._stub.TerminateOperator(request, timeout=10)


class FlinkConnectorClient:
    """gRPC client for communicating with HybridStream Flink Connector."""

    def __init__(self, endpoint: str):
        self._endpoint = endpoint
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[pb2_grpc.FlinkConnectorStub] = None

    async def connect(self) -> None:
        self._channel = grpc.aio.insecure_channel(self._endpoint)
        self._stub = pb2_grpc.FlinkConnectorStub(self._channel)

    async def close(self) -> None:
        if self._channel:
            await self._channel.close()

    async def restore_operator(self, operator_id: str, snapshot_key: str) -> pb2.RestoreResponse:
        """Restore an operator from snapshot on the cloud Flink cluster."""
        request = pb2.RestoreRequest(
            operator_id=operator_id,
            snapshot_object_key=snapshot_key,
        )
        return await self._stub.RestoreOperator(request, timeout=60)

    async def submit_job(self, job_config: dict) -> pb2.JobSubmissionResponse:
        """Submit a new Flink job configuration."""
        # TODO: Define job submission protobuf messages
        pass
```

---

## Step 11 — `aode/aode/grpc/server.py`

```python
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import grpc

from hybridstream.proto import hybridstream_pb2 as pb2
from hybridstream.proto import hybridstream_pb2_grpc as pb2_grpc

from ..placement.optimizer import PlacementOptimizer
from ..placement.state import PlacementState
from ..migration.pctr import PCTROrchestrator
from ..scoring.algorithm import ScoringAlgorithm

log = logging.getLogger(__name__)


class AODEManagementServicer(pb2_grpc.AODEManagementServicer):
    """
    gRPC server for external AODE management.
    Used by monitoring systems, admin tools, or integration testing.
    """

    def __init__(
        self,
        optimizer: PlacementOptimizer,
        placement_state: PlacementState,
        migration_orchestrator: PCTROrchestrator,
        scoring_algorithm: ScoringAlgorithm,
    ):
        self._optimizer = optimizer
        self._placement = placement_state
        self._migration = migration_orchestrator
        self._scoring = scoring_algorithm

    def GetStatus(self, request, context):
        """Return AODE system status."""
        current_placement = self._placement.get_current_placement()
        optimizer_status = self._optimizer.get_status()
        active_migrations = self._migration.list_active_migrations()
        
        return pb2.AODEStatusResponse(
            instance_id="aode-1",  # TODO: get from config
            is_leader=True,        # TODO: get from leader election
            operators_managed=len(current_placement),
            active_migrations=len(active_migrations),
            last_recalibration_ago_s=optimizer_status.get("last_run_ago_s", 0),
            uptime_s=0,  # TODO: track uptime
        )

    def TriggerRecalibration(self, request, context):
        """Force immediate recalibration cycle."""
        try:
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                self._optimizer.force_recalibration(reason=request.reason or "manual"),
                loop
            )
            result = future.result(timeout=30)
            
            return pb2.RecalibrationResponse(
                success=True,
                migrations_started=result.get("migrations_started", 0),
                duration_ms=result.get("duration_ms", 0),
            )
        except Exception as e:
            log.error("TriggerRecalibration error: %s", e)
            return pb2.RecalibrationResponse(
                success=False,
                error_msg=str(e),
            )

    def UpdateWeights(self, request, context):
        """Change scoring algorithm weight preset."""
        try:
            self._scoring.set_weights(request.preset_name)
            return pb2.WeightUpdateResponse(success=True)
        except Exception as e:
            return pb2.WeightUpdateResponse(success=False, error_msg=str(e))

    def GetPlacementState(self, request, context):
        """Return current operator→tier mapping."""
        placement = self._placement.get_current_placement()
        return pb2.PlacementStateResponse(operator_to_tier=placement)


async def serve_management_api(
    port: int,
    optimizer: PlacementOptimizer,
    placement_state: PlacementState,
    migration_orchestrator: PCTROrchestrator,
    scoring_algorithm: ScoringAlgorithm,
) -> None:
    """Start the AODE management gRPC server."""
    server = grpc.aio.server(ThreadPoolExecutor(max_workers=1))
    pb2_grpc.add_AODEManagementServicer_to_server(
        AODEManagementServicer(optimizer, placement_state, migration_orchestrator, scoring_algorithm),
        server
    )
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    log.info("AODE management server listening on port %d", port)
    await server.wait_for_termination()
```

---

## Step 12 — `aode/aode/main.py`

```python
import asyncio
import logging
import signal
import sys

from .config import AODEConfig
from .etcd.client import EtcdClient, LeaderElection
from .telemetry.collector import TelemetryCollector
from .scoring.algorithm import ScoringAlgorithm
from .placement.state import PlacementState
from .placement.optimizer import PlacementOptimizer
from .migration.pctr import PCTROrchestrator
from .grpc.clients import FlinkConnectorClient
from .grpc.server import serve_management_api
from hybridstream.common.object_store import ObjectStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


class AODEService:
    """Main AODE service with HA primary/standby support."""

    def __init__(self):
        self.config = AODEConfig()
        self.etcd_client: EtcdClient | None = None
        self.leader_election: LeaderElection | None = None
        self.telemetry_collector: TelemetryCollector | None = None
        self.placement_state: PlacementState | None = None
        self.optimizer: PlacementOptimizer | None = None
        self.migration_orchestrator: PCTROrchestrator | None = None
        self.is_leader = False
        self.shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Initialize and start all AODE subsystems."""
        log.info("Starting AODE instance %s", self.config.instance_id)

        # Connect to etcd
        self.etcd_client = EtcdClient(self.config.etcd_endpoints, self.config.etcd_key_prefix)
        await self.etcd_client.connect()

        # Start leader election
        self.leader_election = LeaderElection(self.etcd_client, self.config.instance_id)
        self.is_leader = await self.leader_election.start_election()

        # Initialize shared components
        self.telemetry_collector = TelemetryCollector(self.config)
        self.placement_state = PlacementState(self.etcd_client)
        
        await self.telemetry_collector.start()
        await self.placement_state.load_from_etcd()

        # Leader-only components
        if self.is_leader:
            await self._start_leader_components()
        else:
            log.info("Running in standby mode")

        # Start management gRPC server (available on both leader and standby)
        asyncio.create_task(self._serve_management_api())

        # Install signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda s, f: asyncio.create_task(self.stop()))

        log.info("AODE startup complete")

    async def _start_leader_components(self) -> None:
        """Start components that only run on the leader instance."""
        log.info("Initializing leader-only components")

        # Object store for migration snapshots
        object_store = ObjectStore(
            endpoint_url=self.config.minio_endpoint,
            access_key=self.config.minio_access_key,
            secret_key=self.config.minio_secret_key,
            bucket=self.config.minio_bucket,
        )

        # Flink connector client
        flink_client = FlinkConnectorClient(self.config.flink_connector_endpoint)
        await flink_client.connect()

        # HEA clients
        hea_clients = {}
        for endpoint in self.config.hea_endpoints:
            hea_id = endpoint.split(":")[0]
            from .grpc.clients import HEAClient
            client = HEAClient(endpoint)
            await client.connect()
            hea_clients[hea_id] = client

        # Scoring algorithm
        scoring = ScoringAlgorithm(self.config, self.telemetry_collector)

        # Migration orchestrator
        self.migration_orchestrator = PCTROrchestrator(
            self.config, hea_clients, flink_client, object_store
        )

        # Placement optimizer (runs Algorithm 1)
        self.optimizer = PlacementOptimizer(
            self.config, scoring, self.migration_orchestrator, self.placement_state
        )
        await self.optimizer.start()

    async def _serve_management_api(self) -> None:
        """Start the gRPC management API server."""
        if self.is_leader and self.optimizer and self.migration_orchestrator:
            scoring = ScoringAlgorithm(self.config, self.telemetry_collector)
            await serve_management_api(
                self.config.grpc_port,
                self.optimizer,
                self.placement_state,
                self.migration_orchestrator,
                scoring,
            )
        else:
            # Standby mode: serve limited API
            # TODO: implement standby-only management API
            await asyncio.sleep(1)  # Placeholder

    async def stop(self) -> None:
        """Graceful shutdown."""
        log.info("Shutting down AODE")

        if self.optimizer:
            await self.optimizer.stop()

        if self.telemetry_collector:
            await self.telemetry_collector.stop()

        if self.leader_election:
            await self.leader_election.stop_election()

        if self.etcd_client:
            await self.etcd_client.close()

        self.shutdown_event.set()

    async def run(self) -> None:
        """Run the AODE service until shutdown."""
        await self.start()
        await self.shutdown_event.wait()


async def main() -> None:
    service = AODEService()
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Step 13 — Unit Tests

### `aode/tests/test_scoring.py`

```python
import pytest
import numpy as np
from unittest.mock import MagicMock

from aode.aode.scoring.algorithm import ScoringAlgorithm
from aode.aode.scoring.weights import get_weight_preset
from aode.aode.config import AODEConfig


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AODEConfig)
    config.kappa = 2.0
    config.slo_penalty_factor = 10
    config.default_weight_preset = "balanced"
    return config


@pytest.fixture 
def mock_telemetry():
    telemetry = MagicMock()
    telemetry.get_tier_utilization.return_value = (0.3, 0.4)  # 30% CPU, 40% memory
    telemetry.get_operator_latency.return_value = 15.0        # 15ms p95 latency
    telemetry.get_latest_telemetry.return_value = {
        "edge-node-1": MagicMock(reachable=True, rtt_ms=25.0)
    }
    return telemetry


def test_scoring_algorithm_basic(mock_config, mock_telemetry):
    """Test basic scoring computation for a simple scenario."""
    scoring = ScoringAlgorithm(mock_config, mock_telemetry)
    
    operator_types = ["TestOp"]
    tiers = ["edge-node-1", "cloud"] 
    slo_map = {"TestOp": 50.0}  # 50ms SLO
    lambda_map = {"TestOp": "standard"}

    scores = scoring.compute_scores(operator_types, tiers, slo_map, lambda_map)
    
    assert scores.shape == (1, 2)  # 1 operator × 2 tiers
    assert scores[0, 0] > 0        # Edge score should be positive
    assert scores[0, 1] >= 0       # Cloud score should be non-negative


def test_phi_lat_lambda_classes(mock_config, mock_telemetry):
    """Test that λ-class affects latency factor correctly."""
    scoring = ScoringAlgorithm(mock_config, mock_telemetry)
    
    # Critical operators should have higher latency penalty
    critical_phi = scoring._compute_phi_lat("TestOp", "edge-node-1", "critical")
    standard_phi = scoring._compute_phi_lat("TestOp", "edge-node-1", "standard") 
    batch_phi = scoring._compute_phi_lat("TestOp", "edge-node-1", "batch")
    
    assert critical_phi > standard_phi > batch_phi


def test_phi_res_utilization_curve(mock_config, mock_telemetry):
    """Test that Φ_res follows the M/D/1 queueing curve."""
    scoring = ScoringAlgorithm(mock_config, mock_telemetry)
    
    # Low utilization
    mock_telemetry.get_tier_utilization.return_value = (0.1, 0.1)
    phi_low = scoring._compute_phi_res("edge-node-1")
    
    # High utilization
    mock_telemetry.get_tier_utilization.return_value = (0.8, 0.8)
    phi_high = scoring._compute_phi_res("edge-node-1")
    
    assert phi_high > phi_low * 5  # High utilization should have much higher penalty


def test_slo_violation_penalty(mock_config, mock_telemetry):
    """Test SLO violation penalty calculation."""
    scoring = ScoringAlgorithm(mock_config, mock_telemetry)
    
    # No violation: observed 15ms < SLO 50ms
    phi_no_violation = scoring._compute_phi_slo("TestOp", "edge-node-1", 50.0)
    assert phi_no_violation == 0.0
    
    # Violation: observed 15ms > SLO 5ms
    phi_violation = scoring._compute_phi_slo("TestOp", "edge-node-1", 5.0) 
    assert phi_violation > 0


def test_weight_presets():
    """Test that weight presets sum to 1.0."""
    for preset_name in ["latency-first", "balanced", "resource-efficient"]:
        preset = get_weight_preset(preset_name)
        total = preset.w_lat + preset.w_res + preset.w_net + preset.w_slo
        assert abs(total - 1.0) < 0.01
```

### `aode/tests/test_placement_optimizer.py`

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from aode.aode.placement.optimizer import PlacementOptimizer
from aode.aode.config import AODEConfig


@pytest.mark.asyncio
async def test_migration_candidate_identification():
    """Test that optimizer correctly identifies operators needing migration."""
    # Mock config with hysteresis threshold
    config = MagicMock(spec=AODEConfig)
    config.delta_h = 0.15
    config.recalibration_enabled = False  # Disable background task for test

    # Mock dependencies
    scoring = MagicMock()
    migration = AsyncMock()
    placement_state = MagicMock()
    
    # Setup placement state
    placement_state.get_current_placement.return_value = {
        "OpA": "edge-node-1",
        "OpB": "edge-node-2",
    }
    placement_state.get_available_tiers.return_value = ["edge-node-1", "edge-node-2", "cloud"]
    placement_state.get_slo_map.return_value = {"OpA": 50.0, "OpB": 100.0}
    placement_state.get_lambda_map.return_value = {"OpA": "standard", "OpB": "standard"}
    placement_state.get_tier_capacities.return_value = {"edge-node-1": 5, "edge-node-2": 5, "cloud": 100}

    # Mock scoring matrix: OpA should migrate from edge-node-1 to cloud
    import numpy as np
    scores = np.array([
        [0.8, 0.9, 0.2],  # OpA: edge-1=0.8, edge-2=0.9, cloud=0.2 (best)
        [0.3, 0.3, 0.5],  # OpB: edge-1=0.3, edge-2=0.3, cloud=0.5 (stay on edge)
    ])
    scoring.compute_scores.return_value = scores

    optimizer = PlacementOptimizer(config, scoring, migration, placement_state)
    
    # Force optimization
    result = await optimizer._run_optimization()
    
    # Should identify OpA for migration (score improvement 0.8 - 0.2 = 0.6 > threshold 0.15)
    assert result["migrations_started"] == 1
    migration.migrate_operator.assert_called_once_with("OpA", "edge-node-1", "cloud")


@pytest.mark.asyncio 
async def test_hysteresis_threshold():
    """Test that small score improvements don't trigger migrations (hysteresis)."""
    config = MagicMock(spec=AODEConfig)
    config.delta_h = 0.15  # 15% threshold
    config.recalibration_enabled = False
    
    scoring = MagicMock()
    migration = AsyncMock()
    placement_state = MagicMock()
    
    placement_state.get_current_placement.return_value = {"OpA": "edge-node-1"}
    placement_state.get_available_tiers.return_value = ["edge-node-1", "cloud"]
    placement_state.get_slo_map.return_value = {"OpA": 50.0}
    placement_state.get_lambda_map.return_value = {"OpA": "standard"}  
    placement_state.get_tier_capacities.return_value = {"edge-node-1": 5, "cloud": 100}

    # Small improvement: 0.5 - 0.4 = 0.1 < threshold 0.15
    import numpy as np
    scores = np.array([[0.5, 0.4]])  # OpA: edge=0.5, cloud=0.4
    scoring.compute_scores.return_value = scores

    optimizer = PlacementOptimizer(config, scoring, migration, placement_state)
    result = await optimizer._run_optimization()
    
    # No migration should be triggered
    assert result["migrations_started"] == 0
    migration.migrate_operator.assert_not_called()
```

---

## Step 14 — `aode/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install etcd client dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY hybridstream-common/ /app/hybridstream-common/
COPY aode/ /app/aode/
RUN pip install --no-cache-dir /app/hybridstream-common && \
    pip install --no-cache-dir /app/aode

# Copy generated proto stubs 
COPY aode/aode/grpc/ /app/aode/aode/grpc/

EXPOSE 50052

ENTRYPOINT ["python", "-m", "aode.main"]
```

---

## Phase 3 Completion Criteria

Phase 3 is done when:

1. `pytest aode/tests/` passes — all unit tests green
2. AODE container starts and connects to etcd: `docker compose up aode`
3. Leader election works: primary instance acquires lock, standby instance waits
4. Telemetry collection: AODE polls all HEA endpoints and gets valid responses
5. Scoring algorithm: `compute_scores()` returns a valid matrix for test operator types
6. Recalibration: Algorithm 1 identifies migration candidates correctly with hysteresis
7. PCTR orchestration: can start a mock migration (Phase 1-4) without errors
8. gRPC management API: `GetStatus`, `TriggerRecalibration`, `UpdateWeights` work correctly

The AODE should be fully operational as the "brain" of the HybridStream system.