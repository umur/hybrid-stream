# Phase 1 — Shared Foundation

> **Goal:** Build everything that every other component depends on.  
> No other phase can start until Phase 1 is complete.  
> Estimated scope: ~600 lines of Python, ~80 lines of Java (generated), ~200 lines of JSON schema.

---

## Deliverables Checklist

- [ ] `proto/hybridstream.proto` — complete proto3 service definition
- [ ] `scripts/generate_proto.sh` — generates Python + Java stubs
- [ ] `hybridstream-common/` — shared Python package (schema registry, snapshot utils, object store, DAG model)
- [ ] `schema-registry/schemas/v1/` — JSON schema documents for all 11 operator types
- [ ] `infra/docker-compose.yml` — local dev stack (Kafka, MinIO, etcd)
- [ ] `scripts/build_all.sh` — builds all components
- [ ] All unit tests passing for the common library

---

## Step 1 — Repository Skeleton

Create the top-level directory structure first:

```bash
cd code/

# Python components
mkdir -p hea/hea/{execution,state,kafka,grpc}
mkdir -p hea/tests
mkdir -p aode/aode/{telemetry,scoring,placement,migration,ha}
mkdir -p aode/tests
mkdir -p hybridstream-common/hybridstream/common
mkdir -p hybridstream-common/tests

# Java component
mkdir -p flink-connector/src/main/java/ai/hybridstream/connector/{grpc,snapshot,telemetry,proto}
mkdir -p flink-connector/src/test/java/ai/hybridstream/connector

# Shared proto and schema
mkdir -p proto
mkdir -p schema-registry/schemas/v1

# Workloads
mkdir -p workloads/w1_industrial_iot/operators
mkdir -p workloads/w2_smart_city/operators
mkdir -p workloads/w3_financial/operators

# Infra and experiments
mkdir -p infra/{k8s,tc-netem}
mkdir -p experiments/results
mkdir -p scripts
```

---

## Step 2 — `proto/hybridstream.proto`

This is the single source of truth for the control plane. **Write it before anything else.**

```protobuf
syntax = "proto3";

package hybridstream.v1;

option java_package = "ai.hybridstream.proto";
option java_outer_classname = "HybridStreamProto";
option java_multiple_files = true;

// ─────────────────────────────────────────────────
// Service definition — same 4 RPCs on HEA and Flink Connector
// ─────────────────────────────────────────────────

service HEAManagement {
  rpc GetTelemetry      (TelemetryRequest)    returns (TelemetryResponse);
  rpc ApplyPlacement    (PlacementDirective)  returns (PlacementAck);
  rpc TriggerSnapshot   (SnapshotRequest)     returns (SnapshotResponse);
  rpc TerminateOperator (TerminateRequest)    returns (TerminateAck);
}

// ─────────────────────────────────────────────────
// GetTelemetry
// ─────────────────────────────────────────────────

message TelemetryRequest {
  string requester_id = 1;   // AODE instance ID
}

message TelemetryResponse {
  string   hea_id              = 1;
  float    cpu_utilization     = 2;   // fraction [0.0, 1.0]
  float    memory_utilization  = 3;   // fraction [0.0, 1.0]
  float    ingest_rate_eps     = 4;   // events per second (30s sliding window)
  map<string, float> operator_p95_ms = 5;   // operator_id → p95 latency ms
  int64    timestamp_ms        = 6;   // wall clock at collection time
  bool     reachable           = 7;   // false if HEA returned an error
}

// ─────────────────────────────────────────────────
// ApplyPlacement
// ─────────────────────────────────────────────────

message PlacementDirective {
  string directive_id                    = 1;   // UUID, idempotency key
  map<string, string> operator_to_tier   = 2;   // operator_id → tier_id ("cloud" or HEA node ID)
  int64 issued_at_ms                     = 3;
}

message PlacementAck {
  string directive_id = 1;
  bool   accepted     = 2;
  string error_msg    = 3;   // non-empty only if accepted=false
}

// ─────────────────────────────────────────────────
// TriggerSnapshot
// ─────────────────────────────────────────────────

message SnapshotRequest {
  string operator_id      = 1;
  int32  migration_seq    = 2;   // monotonically increasing per operator
  string drain_offset_map = 3;   // JSON: {partition_id: offset} — Kafka consumer position
}

message SnapshotResponse {
  string operator_id     = 1;
  string object_key      = 2;   // MinIO/S3 path: "{operator_id}/{migration_seq}/snapshot.msgpack"
  int64  byte_size       = 3;
  int32  schema_version  = 4;
  string error_msg       = 5;
}

// ─────────────────────────────────────────────────
// TerminateOperator
// ─────────────────────────────────────────────────

message TerminateRequest {
  string operator_id          = 1;
  bool   flush_state          = 2;   // if true, flush RocksDB WAL before closing
  string migration_buffer_topic = 3; // migration buffer topic to deregister
}

message TerminateAck {
  string operator_id = 1;
  bool   success     = 2;
  string error_msg   = 3;
}

// ─────────────────────────────────────────────────
// Internal AODE messages (etcd persisted as JSON, not RPC)
// Defined here for documentation purposes only.
// ─────────────────────────────────────────────────

// MigrationState — persisted to etcd during PCTR
// Key: /hybridstream/migration/{operator_id}/{migration_seq}
message MigrationState {
  string operator_id    = 1;
  int32  migration_seq  = 2;
  string src_tier       = 3;
  string dst_tier       = 4;
  int32  phase          = 5;   // 1, 2, 3, or 4
  string object_key     = 6;   // set after Phase 2
  string drain_offset   = 7;   // set after Phase 1
  bool   dst_ready      = 8;   // set after Phase 3
  int64  started_at_ms  = 9;
  int64  updated_at_ms  = 10;
}
```

---

## Step 3 — Proto Code Generation

### `scripts/generate_proto.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

PROTO_DIR="$(cd "$(dirname "$0")/.." && pwd)/proto"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ Generating Python stubs..."

# HEA stubs
python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$ROOT/hea/hea/grpc" \
  --grpc_python_out="$ROOT/hea/hea/grpc" \
  "$PROTO_DIR/hybridstream.proto"

# AODE stubs (same proto, different output dir)
python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$ROOT/aode/aode/grpc" \
  --grpc_python_out="$ROOT/aode/aode/grpc" \
  "$PROTO_DIR/hybridstream.proto"

# Common package stubs (for shared deserialization helpers)
python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$ROOT/hybridstream-common/hybridstream/common/proto" \
  --grpc_python_out="$ROOT/hybridstream-common/hybridstream/common/proto" \
  "$PROTO_DIR/hybridstream.proto"

echo "→ Generating Java stubs..."
protoc \
  -I "$PROTO_DIR" \
  --java_out="$ROOT/flink-connector/src/main/java" \
  --grpc-java_out="$ROOT/flink-connector/src/main/java" \
  "$PROTO_DIR/hybridstream.proto"

echo "✓ Proto generation complete."
```

Make executable: `chmod +x scripts/generate_proto.sh`

**Dependencies needed first:**
```bash
pip install grpcio-tools==1.62.0
# Java: download protoc + protoc-gen-grpc-java and add to PATH
```

---

## Step 4 — Schema Registry JSON Documents

One JSON file per operator type. All go in `schema-registry/schemas/v1/`.

### Format specification

```json
{
  "schema_version": 1,
  "operator_class": "<ClassName>",
  "fields": [
    {
      "name": "<field_name>",
      "type": "<type>",
      "nullable": false,
      "description": "<what this field stores>"
    }
  ]
}
```

**Supported types:** `int32`, `int64`, `float32`, `float64`, `bool`, `str`, `bytes`,  
`list[<T>]`, `map[<K>, <V>]`, `tuple[<T1>, <T2>, ...]`

### `NormalizerOperator.json`

```json
{
  "schema_version": 1,
  "operator_class": "NormalizerOperator",
  "fields": [
    {"name": "kafka_offset_map", "type": "map[int32, int64]",    "nullable": false, "description": "Kafka partition → last consumed offset"},
    {"name": "watermark_ms",     "type": "int64",                "nullable": false, "description": "Current event-time watermark in ms"},
    {"name": "scale_factors",    "type": "map[str, float64]",    "nullable": false, "description": "Per-signal normalization scale factors (calibrated at startup)"}
  ]
}
```

### `FeatureAggWindow.json`

```json
{
  "schema_version": 1,
  "operator_class": "FeatureAggWindow",
  "fields": [
    {"name": "window_buffers",    "type": "list[tuple[str, int64, list[float64]]]", "nullable": false, "description": "[(key, window_start_ms, values)] per active window"},
    {"name": "accumulators",      "type": "map[str, float64]",   "nullable": false, "description": "Running aggregation accumulators per window key"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "pending_timers",    "type": "list[int64]",         "nullable": false, "description": "Fire timestamps for registered event-time timers"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Kafka partition → last consumed offset"}
  ]
}
```

### `MultiStreamJoin.json`

```json
{
  "schema_version": 1,
  "operator_class": "MultiStreamJoin",
  "fields": [
    {"name": "left_buffer",       "type": "list[tuple[str, int64, bytes]]", "nullable": false, "description": "Buffered records from left stream: (key, event_time_ms, payload)"},
    {"name": "right_buffer",      "type": "list[tuple[str, int64, bytes]]", "nullable": false, "description": "Buffered records from right stream"},
    {"name": "window_size_ms",    "type": "int64",               "nullable": false, "description": "Join window width in milliseconds"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Per-partition Kafka consumer offsets"},
    {"name": "pending_timers",    "type": "list[int64]",         "nullable": false, "description": "Window expiry timers"}
  ]
}
```

### `BinaryClassifier.json`

```json
{
  "schema_version": 1,
  "operator_class": "BinaryClassifier",
  "fields": [
    {"name": "model_weights",     "type": "bytes",               "nullable": false, "description": "Serialized sklearn/numpy model weights (MessagePack-encoded ndarray)"},
    {"name": "feature_names",     "type": "list[str]",           "nullable": false, "description": "Ordered feature column names expected by the model"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Per-partition Kafka consumer offsets"}
  ]
}
```

### `VehicleDetector.json`

```json
{
  "schema_version": 1,
  "operator_class": "VehicleDetector",
  "fields": [
    {"name": "detection_state",   "type": "map[str, int32]",     "nullable": false, "description": "Intersection ID → current vehicle count"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Per-partition Kafka consumer offsets"}
  ]
}
```

### `ZoneAggregator.json`

```json
{
  "schema_version": 1,
  "operator_class": "ZoneAggregator",
  "fields": [
    {"name": "zone_id",           "type": "str",                 "nullable": false, "description": "Zone identifier this instance aggregates"},
    {"name": "flow_counters",     "type": "map[str, int64]",     "nullable": false, "description": "Per-intersection vehicle flow counters"},
    {"name": "window_buffers",    "type": "list[tuple[int64, int64]]", "nullable": false, "description": "(event_time_ms, count) tuples in current aggregation window"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Per-partition Kafka consumer offsets"}
  ]
}
```

### `PatternDetector.json`

```json
{
  "schema_version": 1,
  "operator_class": "PatternDetector",
  "fields": [
    {"name": "pattern_state",     "type": "map[str, list[tuple[int64, float64]]]", "nullable": false, "description": "Zone ID → time-series of aggregated flow readings for CEP pattern matching"},
    {"name": "active_matches",    "type": "list[map[str, int64]]", "nullable": false, "description": "Partially matched pattern sequences with their start timestamps"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "pending_timers",    "type": "list[int64]",         "nullable": false, "description": "Pattern timeout fire timestamps"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Per-partition Kafka consumer offsets"}
  ]
}
```

### `RiskCheck.json`

```json
{
  "schema_version": 1,
  "operator_class": "RiskCheck",
  "fields": [
    {"name": "rule_id",           "type": "str",                 "nullable": false, "description": "Risk rule identifier this instance enforces"},
    {"name": "position_cache",    "type": "map[str, float64]",   "nullable": false, "description": "Instrument ID → current position size (updated per tick)"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Per-partition Kafka consumer offsets"}
  ]
}
```

### `AnomalyDetector.json`

```json
{
  "schema_version": 1,
  "operator_class": "AnomalyDetector",
  "fields": [
    {"name": "baseline_stats",    "type": "map[str, tuple[float64, float64]]", "nullable": false, "description": "Instrument → (rolling_mean, rolling_std) for Z-score anomaly detection"},
    {"name": "alert_cooldown",    "type": "map[str, int64]",     "nullable": false, "description": "Instrument → last alert timestamp (ms) for cooldown enforcement"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Per-partition Kafka consumer offsets"}
  ]
}
```

### `StatAggregator.json`

```json
{
  "schema_version": 1,
  "operator_class": "StatAggregator",
  "fields": [
    {"name": "accumulators",      "type": "map[str, list[float64]]", "nullable": false, "description": "Metric name → rolling sample buffer for statistical computation"},
    {"name": "window_buffers",    "type": "list[tuple[str, int64, float64]]", "nullable": false, "description": "[(metric_key, event_time_ms, value)] in current window"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "pending_timers",    "type": "list[int64]",         "nullable": false, "description": "Window flush fire timestamps"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Per-partition Kafka consumer offsets"}
  ]
}
```

### `ComplianceLogger.json`

```json
{
  "schema_version": 1,
  "operator_class": "ComplianceLogger",
  "fields": [
    {"name": "pending_records",   "type": "list[bytes]",         "nullable": false, "description": "Buffered compliance log entries awaiting flush to output sink"},
    {"name": "sequence_counter",  "type": "int64",               "nullable": false, "description": "Monotonically increasing compliance log entry sequence number"},
    {"name": "watermark_ms",      "type": "int64",               "nullable": false, "description": "Current event-time watermark"},
    {"name": "kafka_offset_map",  "type": "map[int32, int64]",   "nullable": false, "description": "Per-partition Kafka consumer offsets"}
  ]
}
```

---

## Step 5 — `hybridstream-common` Python Package

### `hybridstream-common/pyproject.toml`

```toml
[tool.poetry]
name = "hybridstream-common"
version = "0.1.0"
description = "Shared utilities for HybridStream components"
packages = [{include = "hybridstream"}]

[tool.poetry.dependencies]
python = "^3.12"
msgpack = "^1.0"
aioboto3 = "^13.0"
etcd3 = "^0.12"
pydantic = "^2.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"
```

### `hybridstream/common/dag_model.py`

```python
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
```

### `hybridstream/common/schema_registry.py`

```python
import json
import threading
from pathlib import Path


class SchemaRegistry:
    """
    Loads operator schemas from etcd (production) or local JSON files (dev/test).
    Caches one schema per operator class per process lifetime — no per-record overhead.
    """

    def __init__(self, etcd_client=None, local_schema_dir: str | None = None):
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._etcd = etcd_client
        self._local_dir = Path(local_schema_dir) if local_schema_dir else None

    def get_schema(self, operator_class: str, version: int = 1) -> dict:
        cache_key = f"{operator_class}:v{version}"
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
            schema = self._load(operator_class, version)
            self._cache[cache_key] = schema
            return schema

    def _load(self, operator_class: str, version: int) -> dict:
        if self._local_dir:
            path = self._local_dir / f"v{version}" / f"{operator_class}.json"
            if path.exists():
                return json.loads(path.read_text())
        if self._etcd:
            key = f"/hybridstream/schema/v{version}/{operator_class}"
            result = self._etcd.get(key)
            if result and result[0]:
                return json.loads(result[0].decode())
        raise KeyError(f"Schema not found: {operator_class} v{version}")

    def register_all_from_dir(self, schema_dir: str) -> None:
        """Bootstrap: write all local JSON schemas to etcd."""
        if not self._etcd:
            raise RuntimeError("etcd client required for registration")
        for path in Path(schema_dir).rglob("*.json"):
            data = json.loads(path.read_text())
            key = f"/hybridstream/schema/v{data['schema_version']}/{data['operator_class']}"
            self._etcd.put(key, json.dumps(data))
```

### `hybridstream/common/snapshot.py`

```python
import msgpack
from .schema_registry import SchemaRegistry


def serialize(operator_class: str, state: dict, registry: SchemaRegistry) -> bytes:
    """
    Serialize operator state dict to MessagePack bytes using the schema registry layout.
    Embeds schema_version as header field for cross-language deserialization.
    """
    schema = registry.get_schema(operator_class)
    doc = {"schema_version": schema["schema_version"], "operator_class": operator_class}
    for field_def in schema["fields"]:
        name = field_def["name"]
        doc[name] = state.get(name)
    return msgpack.packb(doc, use_bin_type=True)


def deserialize(data: bytes, registry: SchemaRegistry) -> dict:
    """
    Deserialize MessagePack bytes to state dict.
    Reads schema_version and operator_class from header — no prior knowledge needed.
    """
    doc = msgpack.unpackb(data, raw=False)
    operator_class = doc["operator_class"]
    schema = registry.get_schema(operator_class, doc["schema_version"])
    return {f["name"]: doc.get(f["name"]) for f in schema["fields"]}
```

### `hybridstream/common/object_store.py`

```python
import aioboto3
from botocore.config import Config


class ObjectStore:
    """aioboto3-backed async object store for MinIO/S3 snapshot storage."""

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ):
        self._session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self._endpoint = endpoint_url
        self._bucket = bucket
        self._config = Config(retries={"max_attempts": 3, "mode": "adaptive"})

    async def upload(self, key: str, data: bytes) -> int:
        """Upload bytes; returns byte size. Idempotent (overwrite safe)."""
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            config=self._config,
        ) as s3:
            await s3.put_object(Bucket=self._bucket, Key=key, Body=data)
        return len(data)

    async def download(self, key: str) -> bytes:
        """Download bytes by key."""
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            config=self._config,
        ) as s3:
            response = await s3.get_object(Bucket=self._bucket, Key=key)
            return await response["Body"].read()

    async def exists(self, key: str) -> bool:
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            config=self._config,
        ) as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except s3.exceptions.ClientError:
                return False
```

---

## Step 6 — Docker Compose (Local Dev Stack)

### `infra/docker-compose.yml`

```yaml
version: "3.9"

services:

  kafka:
    image: apache/kafka:3.6.1
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka:9093"
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LOG_DIRS: /var/lib/kafka/data
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
    volumes:
      - kafka_data:/var/lib/kafka/data
    healthcheck:
      test: ["CMD", "kafka-topics.sh", "--bootstrap-server", "localhost:9092", "--list"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:RELEASE.2024-01-01T00-00-00Z
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: hybridstream
      MINIO_ROOT_PASSWORD: hybridstream123
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 3

  etcd:
    image: quay.io/coreos/etcd:v3.5.12
    ports:
      - "2379:2379"
      - "2380:2380"
    environment:
      ETCD_NAME: etcd0
      ETCD_DATA_DIR: /etcd-data
      ETCD_LISTEN_CLIENT_URLS: http://0.0.0.0:2379
      ETCD_ADVERTISE_CLIENT_URLS: http://etcd:2379
      ETCD_LISTEN_PEER_URLS: http://0.0.0.0:2380
      ETCD_INITIAL_ADVERTISE_PEER_URLS: http://etcd:2380
      ETCD_INITIAL_CLUSTER: "etcd0=http://etcd:2380"
      ETCD_INITIAL_CLUSTER_TOKEN: hybridstream-cluster
      ETCD_INITIAL_CLUSTER_STATE: new
    volumes:
      - etcd_data:/etcd-data
    healthcheck:
      test: ["CMD", "etcdctl", "--endpoints=http://localhost:2379", "endpoint", "health"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  kafka_data:
  minio_data:
  etcd_data:
```

---

## Step 7 — Unit Tests for Common Library

### `hybridstream-common/tests/test_dag_model.py`

```python
import pytest
from hybridstream.common.dag_model import OperatorDAG, OperatorNode, Dependency, LambdaClass


def make_simple_dag() -> OperatorDAG:
    ops = [
        OperatorNode("A", "NormalizerOperator", LambdaClass.STANDARD, None),
        OperatorNode("B", "FeatureAggWindow",   LambdaClass.STANDARD, None),
        OperatorNode("C", "BinaryClassifier",   LambdaClass.CRITICAL, 5.0),
    ]
    deps = [Dependency("A", "B"), Dependency("B", "C")]
    return OperatorDAG(ops, deps)


def test_topological_order():
    dag = make_simple_dag()
    order = dag.topological_order()
    assert order.index("A") < order.index("B")
    assert order.index("B") < order.index("C")


def test_upstream_ids():
    dag = make_simple_dag()
    assert dag.upstream_ids("C") == ["B"]
    assert dag.upstream_ids("A") == []


def test_cycle_detection():
    ops = [
        OperatorNode("X", "NormalizerOperator", LambdaClass.STANDARD, None),
        OperatorNode("Y", "FeatureAggWindow",   LambdaClass.STANDARD, None),
    ]
    deps = [Dependency("X", "Y"), Dependency("Y", "X")]
    dag = OperatorDAG(ops, deps)
    with pytest.raises(ValueError, match="cycle"):
        dag.topological_order()
```

### `hybridstream-common/tests/test_snapshot.py`

```python
import pytest
import os
from hybridstream.common.schema_registry import SchemaRegistry
from hybridstream.common.snapshot import serialize, deserialize

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "../../schema-registry/schemas")


def test_normalizer_roundtrip():
    registry = SchemaRegistry(local_schema_dir=SCHEMA_DIR)
    state = {
        "kafka_offset_map": {0: 1000, 1: 2000},
        "watermark_ms": 1700000000000,
        "scale_factors": {"temp": 0.01, "vibration": 0.001},
    }
    raw = serialize("NormalizerOperator", state, registry)
    restored = deserialize(raw, registry)
    assert restored["watermark_ms"] == state["watermark_ms"]
    assert restored["scale_factors"] == state["scale_factors"]


def test_schema_version_in_header():
    registry = SchemaRegistry(local_schema_dir=SCHEMA_DIR)
    import msgpack
    state = {"kafka_offset_map": {0: 1}, "watermark_ms": 0, "scale_factors": {}}
    raw = serialize("NormalizerOperator", state, registry)
    doc = msgpack.unpackb(raw, raw=False)
    assert doc["schema_version"] == 1
    assert doc["operator_class"] == "NormalizerOperator"
```

---

## Step 8 — `scripts/build_all.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ Generating proto stubs..."
"$ROOT/scripts/generate_proto.sh"

echo "→ Installing hybridstream-common..."
cd "$ROOT/hybridstream-common" && pip install -e .

echo "→ Installing hea..."
cd "$ROOT/hea" && pip install -e .

echo "→ Installing aode..."
cd "$ROOT/aode" && pip install -e .

echo "→ Building flink-connector..."
cd "$ROOT/flink-connector" && mvn clean package -q

echo "✓ All components built."
```

---

## Phase 1 Completion Criteria

Phase 1 is done when:

1. `scripts/generate_proto.sh` runs without error and produces `.py` stubs in `hea/`, `aode/`, `hybridstream-common/`, and `.java` stubs in `flink-connector/`
2. All 11 schema JSON files exist in `schema-registry/schemas/v1/`
3. `pytest hybridstream-common/tests/` passes all tests (DAG model + snapshot round-trips for all 11 operator types)
4. `docker compose -f infra/docker-compose.yml up -d` starts Kafka, MinIO, and etcd healthy
5. `scripts/build_all.sh` completes without error
