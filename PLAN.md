# HybridStream Implementation Plan

> Based on: *A Hybrid Edge-Cloud Stream Processing Framework for Low-Latency Real-Time Analytics*  
> Paper sections: §4 (Architecture), §5 (Implementation), §6 (Evaluation)  
> Last updated: 2026-03-19

---

## Table of Contents

1. [Overview](#1-overview)
2. [Repository Structure](#2-repository-structure)
3. [Technology Stack (Final)](#3-technology-stack-final)
4. [Component Breakdown](#4-component-breakdown)
5. [Implementation Order](#5-implementation-order)
6. [Phase 1 — Shared Foundation](#6-phase-1--shared-foundation)
7. [Phase 2 — HybridStream Edge Agent (HEA)](#7-phase-2--hybridstream-edge-agent-hea)
8. [Phase 3 — Adaptive Offloading Decision Engine (AODE)](#8-phase-3--adaptive-offloading-decision-engine-aode)
9. [Phase 4 — HybridStream Flink Connector](#9-phase-4--hybridstream-flink-connector)
10. [Phase 5 — Evaluation Workloads](#10-phase-5--evaluation-workloads)
11. [Phase 6 — Experiment Orchestration](#11-phase-6--experiment-orchestration)
12. [Configuration & Deployment](#12-configuration--deployment)
13. [Testing Strategy](#13-testing-strategy)
14. [Key Design Decisions (from paper)](#14-key-design-decisions-from-paper)

---

## 1. Overview

HybridStream is a hybrid edge-cloud stream processing framework. It has **four primary software components**:

| Component | Language | Deployed On |
|---|---|---|
| **HybridStream Edge Agent (HEA)** | Python 3.12 | Each edge node (Docker container) |
| **Adaptive Offloading Decision Engine (AODE)** | Python 3.12 | Standalone VM (t3.medium or co-located) |
| **HybridStream Flink Connector** | Java 17 | Apache Flink cluster (plugin) |
| **Evaluation Workloads** | Python 3.12 + Java 17 | All tiers |

The data plane runs through Apache Kafka. The control plane runs through gRPC. State snapshots transit through MinIO/S3. AODE coordination state lives in etcd.

---

## 2. Repository Structure

```
code/
├── PLAN.md                          ← this file
│
├── proto/
│   └── hybridstream.proto           ← single source-of-truth proto3 definition
│
├── hea/                             ← HybridStream Edge Agent (Python)
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── hea/
│   │   ├── __init__.py
│   │   ├── main.py                  ← entrypoint; starts asyncio event loop
│   │   ├── operator_registry.py     ← maps operator class names → Python classes
│   │   ├── execution/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py            ← asyncio + ProcessPoolExecutor dispatch
│   │   │   ├── base_operator.py     ← abstract base class all operators inherit
│   │   │   └── decorators.py        ← @cpu_bound, @io_bound decorators
│   │   ├── state/
│   │   │   ├── __init__.py
│   │   │   ├── store.py             ← RocksDB column family wrapper (rocksdict)
│   │   │   ├── checkpoint.py        ← periodic checkpointing (every 30s)
│   │   │   └── snapshot.py          ← PCTR Phase 2: full state → MessagePack
│   │   ├── kafka/
│   │   │   ├── __init__.py
│   │   │   ├── consumer.py          ← aiokafka consumer group per topic
│   │   │   └── producer.py          ← bridge topic producer for inter-tier output
│   │   ├── grpc/
│   │   │   ├── __init__.py
│   │   │   └── server.py            ← HEAManagement gRPC server (4 RPCs)
│   │   ├── metrics.py               ← EWMA CPU/mem/latency/ingest tracking
│   │   └── config.py                ← pydantic settings from env/YAML
│   └── tests/
│
├── aode/                            ← Adaptive Offloading Decision Engine (Python)
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── aode/
│   │   ├── __init__.py
│   │   ├── main.py                  ← entrypoint; starts recalibration loop
│   │   ├── telemetry/
│   │   │   ├── __init__.py
│   │   │   ├── collector.py         ← parallel gRPC GetTelemetry to all HEAs
│   │   │   └── buffer.py            ← circular metric history buffer (depth=300)
│   │   ├── scoring/
│   │   │   ├── __init__.py
│   │   │   ├── model.py             ← Eq.1: Φ = w1·Φ_lat + w2·Φ_res + w3·Φ_net + w4·Φ_slo
│   │   │   ├── factors.py           ← Φ_lat, Φ_res, Φ_net, Φ_slo implementations
│   │   │   └── presets.py           ← latency-first / balanced / resource-efficient weight presets
│   │   ├── placement/
│   │   │   ├── __init__.py
│   │   │   ├── algorithm.py         ← Algorithm 1: topological recalibration loop
│   │   │   ├── dag.py               ← operator DAG + Kahn's topological sort (cached)
│   │   │   └── hysteresis.py        ← Δ_h = 0.15 threshold logic
│   │   ├── migration/
│   │   │   ├── __init__.py
│   │   │   ├── dispatcher.py        ← asyncio Task per migration; topological ordering
│   │   │   └── pctr.py              ← PCTR Phase 1–4 state machine
│   │   ├── ha/
│   │   │   ├── __init__.py
│   │   │   └── coordinator.py       ← etcd lease; primary/standby failover
│   │   ├── trend.py                 ← OLS regression via scipy.stats.linregress; p-value check
│   │   ├── grpc_clients.py          ← gRPC client stubs for HEAs + Flink connector
│   │   └── config.py
│   └── tests/
│
├── flink-connector/                 ← HybridStream Flink Connector (Java 17)
│   ├── pom.xml
│   └── src/main/java/ai/hybridstream/connector/
│       ├── HybridStreamPlugin.java              ← ServiceLoader entry point
│       ├── grpc/
│       │   ├── HybridStreamGrpcServer.java      ← same 4 RPCs as HEA
│       │   └── PlacementDirectiveHandler.java   ← ApplyPlacement → JobGraph rescale
│       ├── snapshot/
│       │   ├── SnapshotTranslator.java           ← Flink savepoint → MessagePack
│       │   └── SchemaRegistryClient.java         ← reads schema from etcd
│       ├── telemetry/
│       │   └── FlinkTelemetryCollector.java      ← Flink metrics API → TelemetryResponse
│       └── proto/                               ← generated Java stubs (protoc)
│
├── schema-registry/                 ← operator schema documents
│   ├── README.md
│   └── schemas/
│       ├── v1/
│       │   ├── NormalizerOperator.json
│       │   ├── FeatureAggWindow.json
│       │   ├── MultiStreamJoin.json
│       │   ├── BinaryClassifier.json
│       │   ├── VehicleDetector.json
│       │   ├── ZoneAggregator.json
│       │   ├── PatternDetector.json
│       │   ├── RiskCheck.json
│       │   ├── AnomalyDetector.json
│       │   ├── StatAggregator.json
│       │   └── ComplianceLogger.json
│
├── workloads/                       ← evaluation workloads (§6.2)
│   ├── w1_industrial_iot/
│   │   ├── operators/               ← Python operator implementations
│   │   │   ├── normalizer.py
│   │   │   ├── feature_agg_window.py
│   │   │   ├── multi_stream_join.py
│   │   │   └── binary_classifier.py
│   │   ├── dag.yaml                 ← operator DAG definition
│   │   └── producer.py              ← Kafka producer with load injection phases
│   ├── w2_smart_city/
│   │   ├── operators/
│   │   │   ├── vehicle_detector.py
│   │   │   ├── zone_aggregator.py
│   │   │   └── pattern_detector.py
│   │   ├── dag.yaml
│   │   └── producer.py
│   └── w3_financial/
│       ├── operators/
│       │   ├── risk_check.py
│       │   ├── anomaly_detector.py
│       │   ├── stat_aggregator.py
│       │   └── compliance_logger.py
│       ├── dag.yaml
│       ├── producer.py
│       └── trace_replay.py          ← NYSE/NASDAQ tape replay with spike injection
│
├── infra/                           ← Docker Compose + Kubernetes manifests
│   ├── docker-compose.yml           ← local development stack (Kafka, MinIO, etcd, HEA, AODE)
│   ├── docker-compose.eval.yml      ← evaluation testbed configuration
│   ├── k8s/
│   │   ├── aode-deployment.yaml
│   │   ├── hea-daemonset.yaml
│   │   └── flink-cluster.yaml
│   └── tc-netem/
│       ├── n1_low_latency.sh        ← tc netem: 5ms delay, 0.5ms jitter
│       ├── n2_medium_latency.sh     ← tc netem: 25ms delay, 3ms jitter, 0.01% loss
│       └── n3_high_latency.sh       ← tc netem: 75ms delay, 12ms jitter, 0.05% loss
│
├── experiments/                     ← orchestration and results
│   ├── run_experiment.py            ← single (workload, config, network) run
│   ├── run_all.py                   ← runs all 63 configurations × 10 reps = 630 executions
│   ├── collect_metrics.py           ← pulls M1–M6 from InfluxDB / log files
│   └── results/                     ← raw results (gitignored; large)
│
└── scripts/
    ├── generate_proto.sh            ← runs grpcio-tools (Python) + protoc (Java)
    ├── build_all.sh                 ← builds all components
    └── deploy_testbed.sh            ← provisions testbed, runs tc netem
```

---

## 3. Technology Stack (Final)

| Component | Tech | Version |
|---|---|---|
| HEA runtime | CPython | 3.12 |
| AODE runtime | CPython | 3.12 |
| Flink Connector | Java (OpenJDK) | 17 LTS |
| Apache Flink | Flink | 1.18.1 |
| Apache Kafka | Kafka | 3.6.1 |
| Edge state store | RocksDB via rocksdict | 0.8 (RocksDB 8.10) |
| Object store | MinIO / Amazon S3 | RELEASE.2024-01 / boto3 1.34 |
| AODE coord store | etcd | 3.5 |
| RPC | gRPC + proto3 | gRPC 1.62 |
| Serialization | MessagePack | msgpack 1.0 (Python), msgpack-core 0.9 (Java) |
| Async Kafka | aiokafka | 0.10 |
| Async S3 | aioboto3 | 13.x |
| Scientific computing | NumPy + SciPy | latest stable |
| Container runtime | Docker | 25.0 |
| Cloud orchestration | Kubernetes + Flink K8s Operator | 1.29 |

---

## 4. Component Breakdown

### 4.1 Proto3 Service Definition (`hybridstream.proto`)

This is the **single source of truth** for the control plane API. Both Python and Java stubs are generated from it. It defines:

```proto
service HEAManagement {
  rpc GetTelemetry      (TelemetryRequest)    returns (TelemetryResponse);
  rpc ApplyPlacement    (PlacementDirective)  returns (PlacementAck);
  rpc TriggerSnapshot   (SnapshotRequest)     returns (SnapshotResponse);
  rpc TerminateOperator (TerminateRequest)    returns (TerminateAck);
}
```

**Key messages:**
- `TelemetryResponse`: CPU util, memory util, per-operator p95 latency map, ingest rate
- `PlacementDirective`: operator_id → tier mapping (edge node ID or "cloud")
- `SnapshotResponse`: object_key (MinIO path), byte_size, schema_version
- Error codes for unreachable HEA detection (AODE marks HEA unreachable on timeout)

### 4.2 HybridStream Edge Agent (HEA)

The HEA is a single Docker container per edge node. It does three things:
1. **Runs operators** — asyncio event loop for I/O-bound; `ProcessPoolExecutor` for CPU-bound
2. **Manages state** — RocksDB per operator (column family isolation); periodic checkpoints every 30s
3. **Exposes gRPC** — 4 RPCs on port 50051

**Execution model:**
- `@io_bound` operators → asyncio coroutine in the main event loop
- `@cpu_bound` operators → `asyncio.run_in_executor(process_pool, ...)` with pool size = max(1, N_cpu − 1)
- Backpressure: when worker queue > 2× pool size, pause aiokafka consumer assignment

**EWMA metrics tracking (Eq. 2):**
- τⱼ(t) = (1 − 0.2) · τⱼ(t−1) + 0.2 · m(t) — RTT probe every 500ms
- CPU and memory: 5-second interval averages
- Per-operator p95 latency: rolling histogram per recalibration interval

### 4.3 Adaptive Offloading Decision Engine (AODE)

The AODE runs the recalibration loop every 5 seconds. The loop does:

1. **Collect** — parallel `GetTelemetry` gRPC to all HEAs + Flink connector (1s timeout)
2. **Detect trend** — OLS regression over last 12 ρ(t) samples; if p < 0.05, activate Eq. 3
3. **Score** — compute Φ matrix (|O| × (|E|+1)) using Eq. 1; infeasible → +∞
4. **Recalibrate** — topological pass; issue migration if score improvement > Δ_h = 0.15
5. **Dispatch** — one asyncio Task per migration; Phase 1–4 PCTR via etcd-checkpointed state machine
6. **Persist** — write π_new to etcd

**Scoring weights (Eq. 1):** Φ = w₁·Φ_lat + w₂·Φ_res + w₃·Φ_net + w₄·Φ_slo
- Latency-first preset: (0.55, 0.10, 0.20, 0.15)
- Balanced preset: (0.30, 0.30, 0.20, 0.20)
- Resource-efficient preset: (0.20, 0.50, 0.20, 0.10)

**Key constants:**
- α = 0.2 (EWMA smoothing)
- κ = 2.0 (CPU contention coefficient — M/D/1 model)
- Δ_h = 0.15 (hysteresis threshold)
- H = 30s (ingest rate lookahead horizon)
- M = 10 (SLO urgency penalty multiplier)
- Recalibration interval = 5s

**HA:** etcd lease TTL=10s, heartbeat every 3s. Standby monitors via watch stream. Failover ≤ 5s.

### 4.4 HybridStream Flink Connector (Java)

Loaded as a standard Flink plugin via Java `ServiceLoader`. Implements the same 4 gRPC RPCs as the HEA:
- `GetTelemetry` → reads Flink metrics API
- `ApplyPlacement` → calls Flink `JobMasterGateway` REST API to rescale operators
- `TriggerSnapshot` → calls Flink `CheckpointCoordinator` → translates Kryo → MessagePack
- `TerminateOperator` → cancels Flink subtask

**Snapshot translation** (cloud→edge migrations only): Flink savepoint → MessagePack via schema registry. Adds 45–120ms per migration depending on state size. Edge→cloud migrations bypass this (HEA generates MessagePack directly).

---

## 5. Implementation Order

This order minimizes rework — each phase builds on the previous.

```
Phase 1: Shared foundation          (proto, schema registry, shared libs)
Phase 2: HEA                        (edge runtime, operator execution, state, gRPC)
Phase 3: AODE                       (telemetry, scoring, Algorithm 1, PCTR, HA)
Phase 4: Flink Connector            (Java plugin, snapshot translation)
Phase 5: Workloads                  (W1, W2, W3 operators + DAG definitions)
Phase 6: Experiment orchestration   (run scripts, metrics collection, tc netem)
```

---

## 6. Phase 1 — Shared Foundation

### 6.1 Proto3 definition

File: `proto/hybridstream.proto`

Define all messages and the `HEAManagement` service. Then generate:
```bash
# Python stubs (into hea/ and aode/)
python -m grpc_tools.protoc -I proto \
  --python_out=hea/hea/grpc \
  --grpc_python_out=hea/hea/grpc \
  proto/hybridstream.proto

# Java stubs (into flink-connector/src/main/java)
protoc -I proto \
  --java_out=flink-connector/src/main/java \
  --grpc-java_out=flink-connector/src/main/java \
  proto/hybridstream.proto
```

Script: `scripts/generate_proto.sh` — run this every time the proto changes.

### 6.2 Schema Registry

Files: `schema-registry/schemas/v1/<OperatorClass>.json`

Each JSON document describes the MessagePack serialization layout for one operator class:
```json
{
  "schema_version": 1,
  "operator_class": "FeatureAggWindow",
  "fields": [
    {"name": "window_buffers",   "type": "array",   "element_type": "tuple3"},
    {"name": "accumulators",     "type": "map",     "key_type": "str", "val_type": "float64"},
    {"name": "watermark_ms",     "type": "int64"},
    {"name": "pending_timers",   "type": "array",   "element_type": "int64"},
    {"name": "kafka_offset_map", "type": "map",     "key_type": "int32", "val_type": "int64"}
  ]
}
```

Schema documents are written to etcd at AODE startup under `/hybridstream/schema/v1/<operator_class>`.

### 6.3 Shared Python library (`hybridstream-common`)

A small shared package imported by both `hea` and `aode`:
```
hybridstream-common/
├── hybridstream/common/
│   ├── schema_registry.py   ← etcd-backed schema lookup (cached per process lifetime)
│   ├── snapshot.py          ← MessagePack serialize/deserialize against schema
│   ├── object_store.py      ← aioboto3 wrapper: upload/download snapshot bytes
│   └── dag_model.py         ← OperatorDAG, OperatorNode, Dependency dataclasses
```

### 6.4 Docker Compose (local dev)

`infra/docker-compose.yml` starts:
- Kafka (KRaft mode, single broker for dev)
- MinIO (single node)
- etcd (single node)
- Placeholder HEA containers (1 per simulated edge node)

---

## 7. Phase 2 — HybridStream Edge Agent (HEA)

### 7.1 `base_operator.py`

All application operators inherit from `BaseOperator`:

```python
class BaseOperator(ABC):
    operator_id: str
    operator_type: str

    async def process(self, record: dict) -> list[dict]:
        """Called for each input record. Returns list of output records."""
        ...

    def get_state(self) -> dict:
        """Serialize current state for snapshot."""
        ...

    def restore_state(self, state: dict) -> None:
        """Restore from snapshot dict."""
        ...

    def get_slo_ms(self) -> float | None:
        """Return SLO in milliseconds, or None for batch operators."""
        ...
```

CPU-bound operators use the `@cpu_bound` class decorator:
```python
@cpu_bound
class BinaryClassifier(BaseOperator):
    ...
```

### 7.2 `execution/engine.py`

The heart of the HEA. Manages:
- One `asyncio.AbstractEventLoop`
- One `ProcessPoolExecutor(max_workers=max(1, os.cpu_count()-1))`
- Per-operator asyncio queues for I/O-bound operators
- `asyncio.run_in_executor` dispatch for CPU-bound operators
- Backpressure via aiokafka consumer pause/resume

Key methods:
```python
async def register_operator(op: BaseOperator, input_topics: list[str]) -> None
async def deregister_operator(operator_id: str) -> None
async def _consume_loop(topic: str) -> None   # aiokafka polling coroutine
async def _dispatch(op: BaseOperator, record: dict) -> None
```

### 7.3 `state/store.py`

Thin wrapper around `rocksdict.Rdict`:
```python
class OperatorStateStore:
    def __init__(self, operator_id: str, db_path: str): ...
    def get(self, key: str) -> bytes | None: ...
    def put(self, key: str, value: bytes) -> None: ...
    def checkpoint(self) -> str:   # returns checkpoint path (hard-linked SST files)
        ...
```

### 7.4 `state/snapshot.py`

PCTR Phase 2 implementation:
```python
async def create_snapshot(
    operator: BaseOperator,
    store: OperatorStateStore,
    schema_registry: SchemaRegistry,
    object_store: ObjectStore,
    operator_id: str,
    migration_seq: int,
) -> SnapshotResponse:
    state = operator.get_state()
    msgpack_bytes = schema_registry.serialize(operator.operator_type, state)
    object_key = f"{operator_id}/{migration_seq}/snapshot.msgpack"
    byte_size = await object_store.upload(object_key, msgpack_bytes)
    return SnapshotResponse(object_key=object_key, byte_size=byte_size, schema_version=1)
```

### 7.5 `grpc/server.py`

gRPC server on port 50051 (configurable). Runs on a `ThreadPoolExecutor(max_workers=1)` separate from the asyncio loop.

**GetTelemetry:** reads from `metrics.py` EWMA state → returns `TelemetryResponse`  
**ApplyPlacement:** atomically updates topic→operator routing table; starts/stops operators  
**TriggerSnapshot:** calls `snapshot.create_snapshot()` asynchronously  
**TerminateOperator:** graceful shutdown of operator coroutine + worker; flushes and closes RocksDB column family; releases Kafka assignments

### 7.6 `metrics.py`

```python
class HEAMetrics:
    cpu_ewma: float          # EWMA α=0.2 over 5-second samples
    mem_ewma: float          # EWMA α=0.2 over 5-second samples
    rtt_ewma: float          # Eq. 2: τⱼ(t) = 0.8·τⱼ(t-1) + 0.2·m(t), probe every 500ms
    operator_p95: dict[str, float]   # per-operator p95 latency rolling histogram
    ingest_rate: float       # 30-second sliding window event/s
```

---

## 8. Phase 3 — Adaptive Offloading Decision Engine (AODE)

### 8.1 `telemetry/collector.py`

```python
async def collect_all(
    hea_clients: list[HEAGrpcClient],
    flink_client: FlinkGrpcClient,
    timeout_s: float = 1.0,
) -> dict[str, TelemetryResponse]:
    # asyncio.gather with per-client timeout
    # marks non-responding HEAs as unreachable
    # flags their operators for emergency cloud migration
```

### 8.2 `telemetry/buffer.py`

```python
class MetricBuffer:
    """Circular buffer depth=300 per metric (25 min at 5s interval)."""
    def push(self, hea_id: str, metric_name: str, value: float) -> None: ...
    def get_window(self, hea_id: str, metric_name: str, n: int) -> list[float]: ...
    # n=12 → last 60 seconds at 5s interval (used for OLS regression)
```

### 8.3 `trend.py`

```python
def detect_ingest_trend(
    buffer: MetricBuffer,
    significance_threshold: float = 0.05,
) -> tuple[float, float] | None:
    """
    OLS regression via scipy.stats.linregress over last 12 ρ(t) samples.
    Returns (slope ρ'(t), p_value) if trend is statistically significant.
    Returns None if p >= significance_threshold.
    Completes in ~0.3ms on evaluation platform.
    """
    samples = buffer.get_window("global", "ingest_rate", n=12)
    result = scipy.stats.linregress(range(len(samples)), samples)
    if result.pvalue < significance_threshold and result.slope > 0:
        return result.slope, result.pvalue
    return None
```

### 8.4 `scoring/factors.py`

Implements the four Φ components (Eq. 1):

```python
def phi_lat(op: OperatorNode, tier: Tier, telemetry: TelemetrySnapshot,
            p0_min: dict, kappa: float = 2.0) -> float:
    """Φ_lat = min(p̂ᵢ(θ) / SLOᵢ, 1). For batch: use nominal SLO=3600s."""

def phi_res(op: OperatorNode, tier: Tier, telemetry: TelemetrySnapshot) -> float:
    """Φ_res = max(projected_cpu_util, projected_mem_util). Cloud → 0."""
    # Returns +inf if projected util > 1.0 (infeasible)

def phi_net(op: OperatorNode, tier: Tier, current_placement: PlacementMap,
            telemetry: TelemetrySnapshot, gamma: float) -> float:
    """Φ_net = (1/Γ) · Σ cross-tier RTT × upstream output rate."""

def phi_slo(op: OperatorNode, tier: Tier, telemetry: TelemetrySnapshot,
            current_placement: PlacementMap, M: float = 10.0) -> float:
    """Φ_slo = M · max(0, (projected_latency - SLOᵢ) / SLOᵢ). Zero for batch."""
```

### 8.5 `scoring/model.py`

```python
def score_matrix(
    dag: OperatorDAG,
    tiers: list[Tier],
    telemetry: TelemetrySnapshot,
    weights: ScoringWeights,
    current_placement: PlacementMap,
    gamma: float,
    trend: tuple[float, float] | None,
    lookahead_s: float = 30.0,
) -> np.ndarray:
    """
    Returns Φ ∈ ℝ^(|O| × (|E|+1)).
    Uses vectorized NumPy operations.
    Substitutes ρ̂(t+H) = ρ(t) + H·ρ'(t) (Eq. 3) if trend is not None.
    Infeasible assignments → +inf.
    """
```

### 8.6 `placement/algorithm.py`

Algorithm 1 from §4.2.3:

```python
async def recalibrate(
    dag: OperatorDAG,
    current_placement: PlacementMap,
    telemetry: TelemetrySnapshot,
    score_matrix: np.ndarray,
    delta_h: float = 0.15,
) -> tuple[PlacementMap, list[MigrationDirective]]:
    """
    Topological pass (Kahn's sort, cached).
    For each operator: find best_θ with best_Φ.
    Issue migration only if improvement > Δ_h.
    Migration ordering: upstream first.
    """
```

### 8.7 `migration/pctr.py`

PCTR Phase 1–4 state machine (one asyncio Task per migration):

```python
class PCTRMigration:
    operator_id: str
    src_tier: Tier
    dst_tier: Tier
    phase: int   # 1, 2, 3, 4; checkpointed to etcd after each phase

    async def run(self) -> None:
        await self._phase1_upstream_pause()
        await self._phase2_checkpoint()
        await self._phase3_target_init()
        await self._phase4_redirect_resume()

    async def _phase1_upstream_pause(self) -> None:
        # Send PAUSE to each upstream HEA/Flink
        # Wait for drain_offset confirmation
        # Record ω_drain

    async def _phase2_checkpoint(self) -> None:
        # TriggerSnapshot RPC to src
        # Upload MessagePack snapshot to MinIO
        # Record object_key, ω_snap

    async def _phase3_target_init(self) -> None:
        # ApplyPlacement + restore snapshot on dst
        # Wait for readiness ack

    async def _phase4_redirect_resume(self) -> None:
        # Update global routing table
        # Signal target to start running (drain migration buffer first)
        # TerminateOperator on src
```

---

## 9. Phase 4 — HybridStream Flink Connector

### 9.1 `HybridStreamPlugin.java`

Entry point via `ServiceLoader`. Registers itself with Flink's plugin system. Starts the gRPC server using the same proto3 stubs as the HEA (generated by protoc).

### 9.2 `PlacementDirectiveHandler.java`

Translates `ApplyPlacement` → Flink JobGraph operations:
- Increase operator parallelism: `JobMasterGateway.rescaleJob()`
- Reduce operator parallelism: trigger Flink savepoint + rescale
- Maps HybridStream operator IDs to Flink `JobVertexID`

### 9.3 `SnapshotTranslator.java`

Cloud→edge migrations only:
1. Trigger Flink `CheckpointCoordinator.triggerSavepoint()`
2. For each state handle: `TypeSerializer.deserialize()` (Kryo → Java object)
3. Re-serialize: `MsgpackSchemaAdapter.serialize()` → MessagePack bytes
4. Upload to MinIO via AWS SDK v2

### 9.4 `FlinkTelemetryCollector.java`

Reads from Flink's `MetricGroup` API:
- `NumberOfInputRecords`, `NumberOfOutputRecords` → ingest rate
- `LatencyHistogram` (p95) per task
- JVM memory used → memory utilization proxy

---

## 10. Phase 5 — Evaluation Workloads

### 10.1 Operator DAG format (`dag.yaml`)

```yaml
operators:
  - id: normalizer_zone_1
    type: NormalizerOperator
    lambda: standard          # critical | standard | batch
    slo_ms: null
    parallelism: 1

  - id: feature_agg_zone_1
    type: FeatureAggWindow
    lambda: standard
    slo_ms: null
    window_seconds: 30
    parallelism: 1

  - id: classifier
    type: BinaryClassifier
    lambda: critical
    slo_ms: 5.0
    parallelism: 1

edges:
  - from: normalizer_zone_1
    to:   feature_agg_zone_1
  - from: feature_agg_zone_1
    to:   classifier
```

### 10.2 W1 — Industrial IoT

- **12 operators:** 5 NormalizerOperator + 5 FeatureAggWindow + 1 MultiStreamJoin + 1 BinaryClassifier
- **Load phases:** 100% → 180% (10 min) → 300% (90s) → 100%
- **Baseline ingest:** 2M ev/s
- **Critical SLO:** classifier, 5ms

### 10.3 W2 — Smart City

- **3 operator types:** VehicleDetector (500 instances, λ=critical, SLO=2s) + ZoneAggregator (20 instances, λ=standard) + PatternDetector (1 instance, λ=batch)
- **AODE scoring matrix:** 3 × 5 (types × tiers)
- **Stress:** memory — zone aggregators sized to consume 85% of edge RAM at peak
- **Baseline ingest:** 50k ev/s

### 10.4 W3 — Financial

- **30 operators:** 8 RiskCheck (SLO=1ms) + 4 AnomalyDetector (SLO=5ms) + 12 StatAggregator + 6 ComplianceLogger
- **Trace:** NYSE/NASDAQ 2023-10-10 consolidated tape
- **Stress:** 3 recorded ingest rate spikes that 3× ingest rate within 10 seconds
- **Trace replay:** `workloads/w3_financial/trace_replay.py` with deterministic spike timestamps

---

## 11. Phase 6 — Experiment Orchestration

### 11.1 Single run (`experiments/run_experiment.py`)

```
args: --workload w1 --config hybridstream --network n2 --seed 42
steps:
  1. Apply tc netem profile (n2_medium_latency.sh)
  2. Deploy config (HybridStream / B1 / B2)
  3. Wait 10 minutes (warm-up, discard measurements)
  4. Record for 60 minutes
  5. Collect M1–M6 metrics
  6. Write results/w1_hybridstream_n2_seed42.json
```

### 11.2 Full evaluation (`experiments/run_all.py`)

- 21 unique (workload × config × network) triples
- × 3 systems (HybridStream, B1, B2) = 63 run configurations
- × 10 repetitions = **630 total executions**
- Parallelizes where hardware allows; serializes within a given node

### 11.3 Metrics collection (`experiments/collect_metrics.py`)

- M1 (p95 latency): timestamp watermarks embedded in Kafka records at producer; measured at final sink
- M2 (SLO compliance): 10-second windows; fraction compliant
- M3 (throughput): Kafka consumer lag probe; incremental ingest test
- M4 (migration pause): AODE migration log timestamps (Phase 1 start → Phase 4 drain complete)
- M5 (AODE overhead): `psutil` CPU + RSS samples at 1-second intervals
- M6 (edge utilization): HEA telemetry (per-phase breakdown)

---

## 12. Configuration & Deployment

### 12.1 HEA configuration (`hea/config.yaml`)

```yaml
hea:
  node_id: edge-node-1
  grpc_port: 50051
  kafka_bootstrap: kafka:9092
  minio_endpoint: http://minio:9000
  minio_bucket: hybridstream-snapshots
  etcd_endpoints: ["etcd:2379"]
  rocksdb_path: /data/rocksdb
  checkpoint_interval_s: 30
  worker_pool_size: 3         # max(1, N_cpu - 1)
  kafka_batch_size: 500
  rtt_probe_interval_ms: 500
  backpressure_high_water: 6  # 2 × pool size
  backpressure_low_water: 2
```

### 12.2 AODE configuration (`aode/config.yaml`)

```yaml
aode:
  grpc_port: 50052
  recalibration_interval_s: 5
  hea_timeout_s: 1.0
  etcd_endpoints: ["etcd:2379"]
  etcd_lease_ttl_s: 10
  etcd_heartbeat_s: 3
  delta_h: 0.15               # hysteresis threshold
  alpha: 0.2                  # EWMA smoothing
  kappa: 2.0                  # CPU contention coefficient
  lookahead_s: 30.0           # H, trend forward projection
  M: 10.0                     # SLO urgency multiplier
  trend_significance: 0.05    # OLS p-value threshold
  scoring_preset: balanced    # latency-first | balanced | resource-efficient
```

---

## 13. Testing Strategy

### Unit tests (pytest)

| Module | What to test |
|---|---|
| `scoring/factors.py` | Φ_lat, Φ_res returns +∞ for infeasible; Φ_slo = 0 for batch operators |
| `scoring/model.py` | score_matrix dimensions; trend substitution changes projected ingest rate |
| `placement/algorithm.py` | migration issued when improvement > Δ_h; not issued below threshold; topological ordering |
| `migration/pctr.py` | each phase transitions correctly; retry idempotency on Phase 2 failure |
| `trend.py` | returns None when p >= 0.05; returns (slope, pvalue) when significant |
| `state/snapshot.py` | round-trip: serialize → deserialize → same state dict |
| `hea/execution/engine.py` | CPU-bound ops dispatched to process pool; backpressure pauses consumer |

### Integration tests

| Scenario | What to verify |
|---|---|
| End-to-end migration | PCTR completes; no records dropped; consumer offset advances past ω_snap + 1 |
| AODE failover | Kill primary → standby acquires lease → recalibration resumes < 5s |
| Unreachable HEA | HEA timeout → operators flagged for cloud migration |
| W1 normal operation | Classifier p95 < 5ms at baseline load |

### Load tests

Run W1 at 300% load with HybridStream and verify:
- AODE migrates feature aggregators to cloud within ~13 seconds of threshold crossing
- Classifier p95 remains < 5ms throughout
- No records dropped (Kafka offset continuity)

---

## 14. Key Design Decisions (from paper)

These are fixed. Do not change them during implementation.

| Decision | Value | Reason |
|---|---|---|
| EWMA smoothing α | 0.2 | Suppresses sub-second jitter; responsive to 2–3s shifts |
| CPU contention κ | 2.0 | Empirically derived; M/D/1 queuing theory; profiled at 0–100% utilization |
| Hysteresis Δ_h | 0.15 | Calibrated on 48h traces; eliminates oscillation without delaying >8% SLO-budget migrations |
| Lookahead H | 30s | Matches typical AODE lead time; beyond 30s OLS accuracy degrades |
| SLO penalty M | 10 | A 10% violation inflates score by the full [0,1] range of other three factors |
| Recalibration interval | 5s | Balances responsiveness vs overhead |
| ProcessPoolExecutor | max(1, N_cpu−1) | Reserve 1 P-core for asyncio + gRPC |
| Kafka batch size | 500 | Balances throughput vs latency |
| RocksDB checkpoint interval | 30s | Under 5ms overhead at all evaluated state sizes |
| MinIO throughput assumption | 210 MB/s | Measured on testbed; used in PCTR Phase 2 time estimates |
| Batch operator nominal SLO | 3600s | Avoids Φ_lat = 0/0 division; effectively removes SLO constraint for batch |
| Schema registry | etcd `/hybridstream/schema/v1/<class>` | Looked up once per operator class per process; cached in memory |
| AODE scores operator types, not instances | W2: 3 types, not 521 instances | Keeps scoring matrix tractable; per-type instances distributed within tier by HEA |
| Migration direction translation | cloud→edge only | Only Flink Connector needs savepoint→MessagePack translation; HEA generates MessagePack directly |

---

## Next Steps

Once this plan is reviewed and approved:

1. **Start Phase 1** — write `hybridstream.proto`, schema JSONs, `hybridstream-common` package
2. **Then Phase 2** — HEA (the most complex Python component)
3. **Then Phase 3** — AODE (builds on HEA gRPC stubs)
4. **Then Phase 4** — Flink Connector (Java; can partly parallelize with Phase 3)
5. **Then Phase 5** — Workload operators (straightforward once base classes exist)
6. **Then Phase 6** — Experiment orchestration (final step before evaluation)

Each phase should have its own working tests before moving to the next.
