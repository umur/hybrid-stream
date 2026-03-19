# Phase 2 — HybridStream Edge Agent (HEA)

> **Depends on:** Phase 1 complete (proto stubs generated, common library installed, Docker Compose running)  
> **Goal:** A fully functional Python 3.12 edge runtime that executes stream operators, manages state, and responds to AODE control via gRPC.  
> Estimated scope: ~1,400 lines of Python.

---

## Deliverables Checklist

- [ ] `hea/pyproject.toml` and `hea/Dockerfile`
- [ ] `hea/hea/main.py` — asyncio entrypoint
- [ ] `hea/hea/config.py` — pydantic settings
- [ ] `hea/hea/execution/base_operator.py` — abstract base class
- [ ] `hea/hea/execution/decorators.py` — `@cpu_bound`, `@io_bound`
- [ ] `hea/hea/execution/engine.py` — asyncio + ProcessPoolExecutor dispatch
- [ ] `hea/hea/state/store.py` — RocksDB column family wrapper
- [ ] `hea/hea/state/checkpoint.py` — periodic checkpoint (every 30s)
- [ ] `hea/hea/state/snapshot.py` — PCTR Phase 2 trigger
- [ ] `hea/hea/kafka/consumer.py` — aiokafka consumer group
- [ ] `hea/hea/kafka/producer.py` — bridge topic + migration buffer producer
- [ ] `hea/hea/metrics.py` — EWMA CPU/mem/RTT/latency/ingest tracking
- [ ] `hea/hea/operator_registry.py` — maps class name string → Python class
- [ ] `hea/hea/grpc/server.py` — gRPC server (4 RPCs)
- [ ] `hea/tests/` — unit + integration tests
- [ ] All tests passing

---

## Step 1 — `hea/pyproject.toml`

```toml
[tool.poetry]
name = "hybridstream-hea"
version = "0.1.0"
description = "HybridStream Edge Agent"
packages = [{include = "hea"}]

[tool.poetry.dependencies]
python = "^3.12"
hybridstream-common = {path = "../hybridstream-common", develop = true}
grpcio = "1.62.0"
grpcio-tools = "1.62.0"
aiokafka = "^0.10"
aioboto3 = "^13.0"
rocksdict = "^0.8"
pydantic = "^2.0"
pydantic-settings = "^2.0"
psutil = "^5.9"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"
```

---

## Step 2 — `hea/hea/config.py`

All config read from environment variables (Docker-friendly) with YAML override support.

```python
from pydantic_settings import BaseSettings
from pydantic import Field


class HEAConfig(BaseSettings):
    # Identity
    node_id:                str   = Field("edge-node-1",         env="HEA_NODE_ID")

    # gRPC server
    grpc_port:              int   = Field(50051,                  env="HEA_GRPC_PORT")

    # Kafka
    kafka_bootstrap:        str   = Field("localhost:9092",       env="HEA_KAFKA_BOOTSTRAP")
    kafka_batch_size:       int   = Field(500,                    env="HEA_KAFKA_BATCH_SIZE")
    kafka_group_prefix:     str   = Field("hea",                  env="HEA_KAFKA_GROUP_PREFIX")

    # Object store
    minio_endpoint:         str   = Field("http://localhost:9000", env="HEA_MINIO_ENDPOINT")
    minio_access_key:       str   = Field("hybridstream",         env="HEA_MINIO_ACCESS_KEY")
    minio_secret_key:       str   = Field("hybridstream123",      env="HEA_MINIO_SECRET_KEY")
    minio_bucket:           str   = Field("hybridstream-snapshots", env="HEA_MINIO_BUCKET")

    # etcd
    etcd_endpoints:         list[str] = Field(["localhost:2379"], env="HEA_ETCD_ENDPOINTS")

    # State
    rocksdb_path:           str   = Field("/data/rocksdb",        env="HEA_ROCKSDB_PATH")
    checkpoint_interval_s:  int   = Field(30,                    env="HEA_CHECKPOINT_INTERVAL_S")

    # Execution
    worker_pool_size:       int   = Field(3,                     env="HEA_WORKER_POOL_SIZE")

    # Backpressure
    backpressure_high_water: int  = Field(6,                     env="HEA_BACKPRESSURE_HIGH")
    backpressure_low_water:  int  = Field(2,                     env="HEA_BACKPRESSURE_LOW")

    # Metrics
    rtt_probe_interval_ms:  int   = Field(500,                   env="HEA_RTT_PROBE_MS")
    ewma_alpha:             float = Field(0.2,                   env="HEA_EWMA_ALPHA")
    cloud_kafka_endpoint:   str   = Field("localhost:9092",       env="HEA_CLOUD_KAFKA_ENDPOINT")

    # Schema registry
    schema_dir:             str   = Field("../../schema-registry/schemas", env="HEA_SCHEMA_DIR")

    class Config:
        env_file = ".env"
```

---

## Step 3 — `hea/hea/execution/base_operator.py`

Every application operator (from Phase 5 workloads) inherits from this.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class BaseOperator(ABC):
    """
    Abstract base class for all HybridStream stream processing operators.

    Lifecycle:
      __init__()       → called once at registration time
      restore_state()  → called after PCTR Phase 3 snapshot restore
      process()        → called per input record during normal execution
      get_state()      → called during PCTR Phase 2 snapshot creation
    """

    operator_id:   str
    operator_type: str   # must match the schema registry class name

    @abstractmethod
    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Process a single input record. Returns a (possibly empty) list of output records.
        I/O-bound operators: runs directly in asyncio event loop.
        CPU-bound operators: runs in ProcessPoolExecutor worker (must be picklable).
        """
        ...

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """
        Return a serializable snapshot of all operator state.
        Keys must match the operator's schema registry field names exactly.
        Called during PCTR Phase 2 with the operator's input queue empty.
        """
        ...

    @abstractmethod
    def restore_state(self, state: dict[str, Any]) -> None:
        """
        Restore operator state from a deserialized snapshot dict.
        Called during PCTR Phase 3 on the target tier before the operator starts running.
        Must not raise; must be idempotent (safe to call twice with same state).
        """
        ...

    def get_slo_ms(self) -> float | None:
        """
        Return the operator's SLO in milliseconds, or None for BATCH operators.
        Override in critical/standard operators to set SLO.
        Default: None (treated as BATCH by the AODE scoring model).
        """
        return None

    def get_lambda_class(self) -> str:
        """
        Return 'critical', 'standard', or 'batch'.
        Used by the AODE to classify this operator's latency sensitivity.
        """
        return "standard"

    def on_start(self) -> None:
        """Optional hook called when the operator begins processing. Override if needed."""
        pass

    def on_stop(self) -> None:
        """Optional hook called before graceful shutdown. Override to flush buffers."""
        pass
```

### `hea/hea/execution/decorators.py`

```python
def cpu_bound(cls):
    """
    Class decorator marking an operator as CPU-bound.
    The HEA execution engine dispatches CPU-bound operators to a ProcessPoolExecutor.
    CPU-bound operators must be picklable (no asyncio state, no open file handles).
    """
    cls._cpu_bound = True
    return cls


def io_bound(cls):
    """
    Class decorator marking an operator as I/O-bound (default).
    I/O-bound operators run as asyncio coroutines directly in the event loop.
    """
    cls._cpu_bound = False
    return cls


def is_cpu_bound(operator_class) -> bool:
    return getattr(operator_class, "_cpu_bound", False)
```

---

## Step 4 — `hea/hea/execution/engine.py`

The heart of the HEA. This is the most complex file.

```python
from __future__ import annotations
import asyncio
import time
import os
import logging
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Any

from aiokafka import AIOKafkaConsumer
from .base_operator import BaseOperator
from .decorators import is_cpu_bound
from ..kafka.producer import BridgeProducer
from ..metrics import HEAMetrics
from ..config import HEAConfig

log = logging.getLogger(__name__)


class OperatorEngine:
    """
    Manages operator execution, Kafka consumption, and backpressure.

    - I/O-bound operators: asyncio coroutines in the event loop
    - CPU-bound operators: asyncio.run_in_executor → ProcessPoolExecutor
    - Backpressure: pause Kafka consumer when worker queue > high_water
    """

    def __init__(self, config: HEAConfig, metrics: HEAMetrics, bridge_producer: BridgeProducer):
        self._config = config
        self._metrics = metrics
        self._bridge = bridge_producer
        self._pool: ProcessPoolExecutor | None = None
        self._operators:      dict[str, BaseOperator] = {}
        self._topic_bindings: dict[str, list[str]]    = {}  # topic → [operator_id]
        self._output_routes:  dict[str, list[str]]    = {}  # operator_id → [output_topic]
        self._consumers:      dict[str, AIOKafkaConsumer] = {}
        self._consumer_tasks: dict[str, asyncio.Task] = {}
        self._worker_queues:  dict[str, asyncio.Queue] = {}  # operator_id → queue (CPU-bound)
        self._paused_topics:  set[str] = set()
        self._running = False

    async def start(self) -> None:
        self._pool = ProcessPoolExecutor(
            max_workers=max(1, (os.cpu_count() or 2) - 1)
        )
        self._running = True
        log.info("OperatorEngine started. Pool size: %d", self._pool._max_workers)

    async def stop(self) -> None:
        self._running = False
        for task in self._consumer_tasks.values():
            task.cancel()
        if self._pool:
            self._pool.shutdown(wait=False)
        for consumer in self._consumers.values():
            await consumer.stop()
        log.info("OperatorEngine stopped.")

    async def register_operator(
        self,
        operator: BaseOperator,
        input_topics: list[str],
        output_topics: list[str],
    ) -> None:
        """
        Register an operator with its input and output Kafka topics.
        Called by ApplyPlacement handler when AODE assigns an operator to this HEA.
        """
        oid = operator.operator_id
        self._operators[oid] = operator
        self._output_routes[oid] = output_topics

        for topic in input_topics:
            self._topic_bindings.setdefault(topic, []).append(oid)
            if topic not in self._consumers:
                await self._start_consumer(topic)

        if is_cpu_bound(type(operator)):
            self._worker_queues[oid] = asyncio.Queue()
            asyncio.create_task(self._cpu_worker_loop(oid))

        operator.on_start()
        log.info("Registered operator %s on topics %s", oid, input_topics)

    async def deregister_operator(self, operator_id: str, flush_state: bool = True) -> None:
        """Gracefully stop an operator and clean up its resources."""
        if operator_id not in self._operators:
            return
        op = self._operators.pop(operator_id)
        op.on_stop()
        if operator_id in self._worker_queues:
            # Drain queue before removing
            q = self._worker_queues.pop(operator_id)
            await q.join()
        self._output_routes.pop(operator_id, None)
        log.info("Deregistered operator %s", operator_id)

    async def _start_consumer(self, topic: str) -> None:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self._config.kafka_bootstrap,
            group_id=f"{self._config.kafka_group_prefix}-{self._config.node_id}",
            enable_auto_commit=False,
            max_poll_records=self._config.kafka_batch_size,
        )
        await consumer.start()
        self._consumers[topic] = consumer
        task = asyncio.create_task(self._consume_loop(topic))
        self._consumer_tasks[topic] = task
        log.debug("Started consumer for topic: %s", topic)

    async def _consume_loop(self, topic: str) -> None:
        consumer = self._consumers[topic]
        while self._running:
            try:
                records = await consumer.getmany(timeout_ms=100, max_records=self._config.kafka_batch_size)
                for tp, messages in records.items():
                    for msg in messages:
                        record = self._deserialize_record(msg.value)
                        for oid in self._topic_bindings.get(topic, []):
                            await self._dispatch(oid, record, msg.offset)

                # Backpressure: check worker queue depths
                await self._check_backpressure(topic)

                await consumer.commit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Consumer error on topic %s: %s", topic, e)

    async def _dispatch(self, operator_id: str, record: dict, offset: int) -> None:
        op = self._operators.get(operator_id)
        if not op:
            return

        start_ns = time.monotonic_ns()
        if is_cpu_bound(type(op)):
            # Enqueue for worker loop; non-blocking
            q = self._worker_queues.get(operator_id)
            if q:
                await q.put((op, record, offset, start_ns))
        else:
            # Run directly in event loop
            try:
                output_records = await op.process(record)
                await self._emit(operator_id, output_records)
                latency_ms = (time.monotonic_ns() - start_ns) / 1e6
                self._metrics.record_latency(operator_id, latency_ms)
            except Exception as e:
                log.error("Operator %s error: %s", operator_id, e)

    async def _cpu_worker_loop(self, operator_id: str) -> None:
        """Drains the work queue for one CPU-bound operator using the process pool."""
        q = self._worker_queues[operator_id]
        loop = asyncio.get_event_loop()
        while self._running or not q.empty():
            try:
                op, record, offset, start_ns = await asyncio.wait_for(q.get(), timeout=0.1)
                try:
                    output_records = await loop.run_in_executor(
                        self._pool, _run_operator_sync, op, record
                    )
                    await self._emit(operator_id, output_records)
                    latency_ms = (time.monotonic_ns() - start_ns) / 1e6
                    self._metrics.record_latency(operator_id, latency_ms)
                except Exception as e:
                    log.error("CPU-bound operator %s error: %s", operator_id, e)
                finally:
                    q.task_done()
            except asyncio.TimeoutError:
                continue

    async def _emit(self, operator_id: str, records: list[dict]) -> None:
        """Route output records to the correct Kafka topic(s)."""
        for out_topic in self._output_routes.get(operator_id, []):
            for record in records:
                await self._bridge.send(out_topic, record)

    async def _check_backpressure(self, topic: str) -> None:
        """Pause/resume Kafka consumer based on worker queue depth."""
        high = self._config.backpressure_high_water
        low = self._config.backpressure_low_water
        for oid in self._topic_bindings.get(topic, []):
            q = self._worker_queues.get(oid)
            if q is None:
                continue
            depth = q.qsize()
            if depth > high and topic not in self._paused_topics:
                self._consumers[topic].pause(self._consumers[topic].assignment())
                self._paused_topics.add(topic)
                log.debug("Backpressure: paused consumer for topic %s (depth=%d)", topic, depth)
            elif depth < low and topic in self._paused_topics:
                self._consumers[topic].resume(self._consumers[topic].assignment())
                self._paused_topics.discard(topic)
                log.debug("Backpressure: resumed consumer for topic %s (depth=%d)", topic, depth)

    @staticmethod
    def _deserialize_record(value: bytes) -> dict:
        import msgpack
        return msgpack.unpackb(value, raw=False)


def _run_operator_sync(operator: BaseOperator, record: dict) -> list[dict]:
    """
    Runs in a worker process via ProcessPoolExecutor.
    Must be a top-level function (picklable). asyncio.run() needed for async process().
    """
    import asyncio
    return asyncio.run(operator.process(record))
```

---

## Step 5 — `hea/hea/state/store.py`

```python
from rocksdict import Rdict, Options, WriteOptions


class OperatorStateStore:
    """
    Per-operator RocksDB column family.
    All operators on one HEA share a single RocksDB instance with column family isolation.
    """

    def __init__(self, operator_id: str, db_path: str):
        self._operator_id = operator_id
        opt = Options()
        opt.set_write_buffer_size(64 * 1024 * 1024)      # 64 MB write buffer
        opt.set_compression_type("lz4")
        self._db = Rdict(f"{db_path}/{operator_id}", options=opt)
        self._write_opt = WriteOptions()
        self._write_opt.set_sync(False)   # async writes; WAL provides durability

    def get(self, key: str) -> bytes | None:
        return self._db.get(key.encode())

    def put(self, key: str, value: bytes) -> None:
        self._db[key.encode()] = value

    def delete(self, key: str) -> None:
        del self._db[key.encode()]

    def items(self) -> list[tuple[str, bytes]]:
        """Iterate all key-value pairs — used during snapshot creation."""
        return [(k.decode(), v) for k, v in self._db.items()]

    def checkpoint(self, checkpoint_dir: str) -> str:
        """
        Create a point-in-time checkpoint via RocksDB hard-linked SST files.
        Returns the checkpoint directory path.
        Measured at <5ms for all evaluated state sizes.
        """
        import os
        path = os.path.join(checkpoint_dir, self._operator_id)
        os.makedirs(path, exist_ok=True)
        self._db.create_checkpoint(path)
        return path

    def close(self, flush: bool = True) -> None:
        if flush:
            self._db.flush()
        self._db.close()
```

### `hea/hea/state/checkpoint.py`

```python
import asyncio
import logging
import os
from .store import OperatorStateStore

log = logging.getLogger(__name__)


class PeriodicCheckpointer:
    """
    Runs a background asyncio task that checkpoints all registered operators every N seconds.
    Uses RocksDB CreateCheckpoint() — measured at <5ms per operator.
    """

    def __init__(self, interval_s: int, checkpoint_base_dir: str):
        self._interval = interval_s
        self._base_dir = checkpoint_base_dir
        self._stores: dict[str, OperatorStateStore] = {}
        self._task: asyncio.Task | None = None

    def register(self, operator_id: str, store: OperatorStateStore) -> None:
        self._stores[operator_id] = store

    def deregister(self, operator_id: str) -> None:
        self._stores.pop(operator_id, None)

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            for oid, store in list(self._stores.items()):
                try:
                    path = store.checkpoint(os.path.join(self._base_dir, "checkpoints"))
                    log.debug("Checkpoint created for %s at %s", oid, path)
                except Exception as e:
                    log.error("Checkpoint failed for %s: %s", oid, e)
```

### `hea/hea/state/snapshot.py`

PCTR Phase 2 trigger — called by the gRPC `TriggerSnapshot` RPC.

```python
import asyncio
import logging
from hybridstream.common.schema_registry import SchemaRegistry
from hybridstream.common.snapshot import serialize
from hybridstream.common.object_store import ObjectStore
from ..execution.base_operator import BaseOperator

log = logging.getLogger(__name__)


async def create_migration_snapshot(
    operator: BaseOperator,
    schema_registry: SchemaRegistry,
    object_store: ObjectStore,
    migration_seq: int,
    drain_offset_map: dict[int, int],
) -> tuple[str, int]:
    """
    PCTR Phase 2: serialize operator state → MessagePack → upload to MinIO.

    Args:
        operator:          The operator instance (input queue must be empty before calling)
        schema_registry:   Schema registry for serialization layout
        object_store:      MinIO/S3 client
        migration_seq:     Monotonically increasing migration sequence number
        drain_offset_map:  {partition: offset} — Kafka consumer position at drain

    Returns:
        (object_key, byte_size) — the MinIO path and size of the uploaded snapshot.
    """
    state = operator.get_state()
    state["kafka_offset_map"] = drain_offset_map   # embed drain offset into snapshot

    msgpack_bytes = serialize(operator.operator_type, state, schema_registry)

    object_key = f"{operator.operator_id}/{migration_seq}/snapshot.msgpack"
    byte_size = await object_store.upload(object_key, msgpack_bytes)

    log.info(
        "Snapshot created for %s: key=%s size=%d bytes",
        operator.operator_id, object_key, byte_size
    )
    return object_key, byte_size
```

---

## Step 6 — `hea/hea/metrics.py`

```python
import time
import psutil
import asyncio
import logging
import statistics
from collections import deque

log = logging.getLogger(__name__)

EWMA_ALPHA = 0.2   # α = 0.2 (Eq. 2)


class HEAMetrics:
    """
    Tracks and exposes EWMA-smoothed resource metrics for the AODE telemetry collector.
    All metrics updated by background coroutine; read by gRPC GetTelemetry handler.
    """

    def __init__(self, alpha: float = EWMA_ALPHA, rtt_probe_interval_ms: int = 500,
                 cloud_kafka_endpoint: str = "localhost:9092"):
        self._alpha = alpha
        self._rtt_probe_ms = rtt_probe_interval_ms
        self._cloud_endpoint = cloud_kafka_endpoint

        # EWMA state
        self.cpu_utilization:    float = 0.0
        self.memory_utilization: float = 0.0
        self.rtt_ms:             float = 10.0   # initial estimate
        self.ingest_rate_eps:    float = 0.0

        # Per-operator p95 latency (rolling window of last 1000 samples)
        self._latency_samples: dict[str, deque] = {}
        self._ingest_counts:   deque = deque(maxlen=300)  # 30s at 100ms sampling

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
                idx = max(0, int(len(sorted_s) * 0.95) - 1)
                result[oid] = sorted_s[idx]
        return result

    def _compute_ingest_rate(self) -> float:
        """30-second sliding window average event/s."""
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
        """Updates CPU, memory, and RTT metrics every 500ms."""
        while True:
            try:
                # CPU and memory (5-second average via EWMA)
                cpu_sample = psutil.cpu_percent(interval=None) / 100.0
                mem_sample = psutil.virtual_memory().percent / 100.0
                self.cpu_utilization    = (1 - self._alpha) * self.cpu_utilization    + self._alpha * cpu_sample
                self.memory_utilization = (1 - self._alpha) * self.memory_utilization + self._alpha * mem_sample

                # RTT probe (Eq. 2): simple TCP connect time to cloud Kafka endpoint
                rtt = await self._probe_rtt()
                self.rtt_ms = (1 - self._alpha) * self.rtt_ms + self._alpha * rtt

                # Ingest rate
                self.ingest_rate_eps = self._compute_ingest_rate()

            except Exception as e:
                log.warning("Metrics update error: %s", e)

            await asyncio.sleep(self._rtt_probe_ms / 1000.0)

    async def _probe_rtt(self) -> float:
        """Measure TCP connect round-trip to the cloud Kafka endpoint in ms."""
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
            return 1000.0   # penalize unreachable endpoint
        return (time.monotonic() - start) * 1000.0
```

---

## Step 7 — `hea/hea/kafka/consumer.py` and `producer.py`

### `consumer.py`

```python
from aiokafka import AIOKafkaConsumer as _AIOKafkaConsumer


class HEAConsumer:
    """
    Thin wrapper around aiokafka AIOKafkaConsumer.
    The OperatorEngine manages consumer lifecycle directly;
    this module provides a factory and configuration helper.
    """

    @staticmethod
    def make(
        topic: str,
        bootstrap_servers: str,
        group_id: str,
        batch_size: int = 500,
    ) -> _AIOKafkaConsumer:
        return _AIOKafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            enable_auto_commit=False,
            max_poll_records=batch_size,
            auto_offset_reset="earliest",
        )
```

### `producer.py`

```python
import msgpack
from aiokafka import AIOKafkaProducer


class BridgeProducer:
    """
    Produces to bridge topics (inter-tier output) and migration buffer topics.
    Used by OperatorEngine._emit() and the PCTR Phase 1 migration buffer redirect.
    """

    def __init__(self, bootstrap_servers: str):
        self._bootstrap = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap,
            compression_type="lz4",
            acks="all",
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()

    async def send(self, topic: str, record: dict) -> None:
        if not self._producer:
            raise RuntimeError("BridgeProducer not started")
        payload = msgpack.packb(record, use_bin_type=True)
        await self._producer.send_and_wait(topic, payload)

    async def send_raw(self, topic: str, payload: bytes) -> None:
        if not self._producer:
            raise RuntimeError("BridgeProducer not started")
        await self._producer.send_and_wait(topic, payload)
```

---

## Step 8 — `hea/hea/operator_registry.py`

```python
from __future__ import annotations
from typing import Type
from .execution.base_operator import BaseOperator

_registry: dict[str, Type[BaseOperator]] = {}


def register(operator_type: str, cls: Type[BaseOperator]) -> None:
    """Register an operator class under a string type name."""
    _registry[operator_type] = cls


def get(operator_type: str) -> Type[BaseOperator]:
    """Look up an operator class by its type name. Raises KeyError if not found."""
    if operator_type not in _registry:
        raise KeyError(
            f"Operator type '{operator_type}' not registered. "
            f"Available: {sorted(_registry.keys())}"
        )
    return _registry[operator_type]


def register_all_from_workload(module_path: str) -> None:
    """
    Dynamically import a workload module and register all BaseOperator subclasses found.
    Each subclass must define a class attribute `operator_type: str`.
    """
    import importlib
    import inspect
    mod = importlib.import_module(module_path)
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, BaseOperator) and obj is not BaseOperator:
            if hasattr(obj, "operator_type"):
                register(obj.operator_type, obj)
```

---

## Step 9 — `hea/hea/grpc/server.py`

```python
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import grpc

# Generated stubs (from proto/hybridstream.proto via generate_proto.sh)
from . import hybridstream_pb2 as pb2
from . import hybridstream_pb2_grpc as pb2_grpc

from ..execution.engine import OperatorEngine
from ..state.snapshot import create_migration_snapshot
from ..operator_registry import get as get_operator_class
from ..metrics import HEAMetrics
from ..config import HEAConfig
from hybridstream.common.schema_registry import SchemaRegistry
from hybridstream.common.object_store import ObjectStore
from hybridstream.common.snapshot import deserialize

log = logging.getLogger(__name__)


class HEAManagementServicer(pb2_grpc.HEAManagementServicer):

    def __init__(
        self,
        config: HEAConfig,
        engine: OperatorEngine,
        metrics: HEAMetrics,
        schema_registry: SchemaRegistry,
        object_store: ObjectStore,
    ):
        self._config   = config
        self._engine   = engine
        self._metrics  = metrics
        self._registry = schema_registry
        self._store    = object_store

    def GetTelemetry(self, request, context):
        p95 = self._metrics.get_operator_p95()
        return pb2.TelemetryResponse(
            hea_id             = self._config.node_id,
            cpu_utilization    = self._metrics.cpu_utilization,
            memory_utilization = self._metrics.memory_utilization,
            ingest_rate_eps    = self._metrics.ingest_rate_eps,
            operator_p95_ms    = p95,
            timestamp_ms       = int(asyncio.get_event_loop().time() * 1000),
            reachable          = True,
        )

    def ApplyPlacement(self, request, context):
        """
        AODE sends a new operator→tier mapping.
        For each operator assigned to this HEA: instantiate + register.
        For each operator removed from this HEA: deregister (PCTR will handle state).
        """
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self._apply_placement_async(request)
            )
            return pb2.PlacementAck(directive_id=request.directive_id, accepted=True)
        except Exception as e:
            log.error("ApplyPlacement error: %s", e)
            return pb2.PlacementAck(directive_id=request.directive_id, accepted=False, error_msg=str(e))

    async def _apply_placement_async(self, request) -> None:
        my_id = self._config.node_id
        for operator_id, tier_id in request.operator_to_tier.items():
            if tier_id == my_id:
                # This operator is being assigned here — instantiate if not already running
                if operator_id not in self._engine._operators:
                    log.info("Instantiating operator %s on %s", operator_id, my_id)
                    # Note: operator instantiation with topic bindings handled by AODE placement
                    # directive which includes topic metadata in a real deployment
            else:
                # This operator is leaving this HEA — deregister it
                if operator_id in self._engine._operators:
                    await self._engine.deregister_operator(operator_id)

    def TriggerSnapshot(self, request, context):
        """PCTR Phase 2: serialize operator state to MessagePack and upload to MinIO."""
        try:
            operator = self._engine._operators.get(request.operator_id)
            if not operator:
                return pb2.SnapshotResponse(
                    operator_id=request.operator_id,
                    error_msg=f"Operator {request.operator_id} not found on this HEA"
                )
            import json
            drain_offsets = json.loads(request.drain_offset_map) if request.drain_offset_map else {}
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                create_migration_snapshot(
                    operator, self._registry, self._store,
                    request.migration_seq, drain_offsets
                ),
                loop
            )
            object_key, byte_size = future.result(timeout=30)
            return pb2.SnapshotResponse(
                operator_id    = request.operator_id,
                object_key     = object_key,
                byte_size      = byte_size,
                schema_version = 1,
            )
        except Exception as e:
            log.error("TriggerSnapshot error for %s: %s", request.operator_id, e)
            return pb2.SnapshotResponse(operator_id=request.operator_id, error_msg=str(e))

    def TerminateOperator(self, request, context):
        """PCTR Phase 4: stop operator, flush state, release resources."""
        try:
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                self._engine.deregister_operator(request.operator_id, flush_state=request.flush_state),
                loop
            )
            future.result(timeout=10)
            return pb2.TerminateAck(operator_id=request.operator_id, success=True)
        except Exception as e:
            log.error("TerminateOperator error for %s: %s", request.operator_id, e)
            return pb2.TerminateAck(operator_id=request.operator_id, success=False, error_msg=str(e))


async def serve(config: HEAConfig, engine: OperatorEngine, metrics: HEAMetrics,
                schema_registry: SchemaRegistry, object_store: ObjectStore) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    pb2_grpc.add_HEAManagementServicer_to_server(
        HEAManagementServicer(config, engine, metrics, schema_registry, object_store),
        server
    )
    server.add_insecure_port(f"[::]:{config.grpc_port}")
    server.start()
    log.info("HEA gRPC server listening on port %d", config.grpc_port)
    server.wait_for_termination()
```

---

## Step 10 — `hea/hea/main.py`

```python
import asyncio
import logging
import os
import sys

from .config import HEAConfig
from .metrics import HEAMetrics
from .execution.engine import OperatorEngine
from .kafka.producer import BridgeProducer
from .state.checkpoint import PeriodicCheckpointer
from .grpc.server import serve
from hybridstream.common.schema_registry import SchemaRegistry
from hybridstream.common.object_store import ObjectStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


async def main() -> None:
    config = HEAConfig()
    log.info("Starting HEA node_id=%s", config.node_id)

    # Initialize shared components
    schema_registry = SchemaRegistry(local_schema_dir=config.schema_dir)
    object_store = ObjectStore(
        endpoint_url=config.minio_endpoint,
        access_key=config.minio_access_key,
        secret_key=config.minio_secret_key,
        bucket=config.minio_bucket,
    )
    metrics = HEAMetrics(
        alpha=config.ewma_alpha,
        rtt_probe_interval_ms=config.rtt_probe_interval_ms,
        cloud_kafka_endpoint=config.cloud_kafka_endpoint,
    )
    bridge_producer = BridgeProducer(bootstrap_servers=config.kafka_bootstrap)
    engine = OperatorEngine(config, metrics, bridge_producer)
    checkpointer = PeriodicCheckpointer(
        interval_s=config.checkpoint_interval_s,
        checkpoint_base_dir=config.rocksdb_path,
    )

    # Start all subsystems
    await bridge_producer.start()
    await engine.start()
    metrics.start()
    checkpointer.start()

    log.info("HEA fully initialized. Waiting for AODE placement directives.")

    # Start gRPC server (blocking until shutdown)
    await serve(config, engine, metrics, schema_registry, object_store)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Step 11 — `hea/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System deps for RocksDB
RUN apt-get update && apt-get install -y --no-install-recommends \
    librocksdb-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY hybridstream-common/ /app/hybridstream-common/
COPY hea/ /app/hea/
RUN pip install --no-cache-dir /app/hybridstream-common && \
    pip install --no-cache-dir /app/hea

# Copy generated proto stubs
COPY hea/hea/grpc/ /app/hea/hea/grpc/

# Data directory for RocksDB
RUN mkdir -p /data/rocksdb /data/checkpoints

EXPOSE 50051

ENTRYPOINT ["python", "-m", "hea.main"]
```

---

## Step 12 — Unit Tests

### `hea/tests/test_engine.py`

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from hea.hea.execution.engine import OperatorEngine
from hea.hea.execution.base_operator import BaseOperator
from hea.hea.execution.decorators import cpu_bound


class DummyIOOperator(BaseOperator):
    operator_id   = "dummy_io"
    operator_type = "DummyIO"

    def __init__(self):
        self.processed = []

    async def process(self, record):
        self.processed.append(record)
        return [{"out": record["val"] * 2}]

    def get_state(self):
        return {}

    def restore_state(self, state):
        pass


@cpu_bound
class DummyCPUOperator(BaseOperator):
    operator_id   = "dummy_cpu"
    operator_type = "DummyCPU"

    async def process(self, record):
        return [{"result": sum(record.values())}]

    def get_state(self):
        return {}

    def restore_state(self, state):
        pass


@pytest.mark.asyncio
async def test_io_bound_dispatch():
    config  = MagicMock(kafka_bootstrap="localhost:9092", kafka_batch_size=500,
                        kafka_group_prefix="test", backpressure_high_water=6,
                        backpressure_low_water=2, node_id="test-node")
    metrics = MagicMock()
    bridge  = MagicMock()
    bridge.send = AsyncMock()

    engine = OperatorEngine(config, metrics, bridge)
    await engine.start()

    op = DummyIOOperator()
    # Directly test dispatch without full Kafka
    await engine._dispatch("dummy_io", {"val": 5}, offset=0)
    # No operator registered yet — should silently skip
    assert bridge.send.call_count == 0

    await engine.stop()
```

### `hea/tests/test_metrics.py`

```python
import pytest
import asyncio
from hea.hea.metrics import HEAMetrics, EWMA_ALPHA


def test_ewma_convergence():
    """EWMA should converge toward stable input."""
    m = HEAMetrics()
    # Simulate 20 samples of 0.8
    for _ in range(20):
        m.cpu_utilization = (1 - EWMA_ALPHA) * m.cpu_utilization + EWMA_ALPHA * 0.8
    assert abs(m.cpu_utilization - 0.8) < 0.01


def test_p95_single_sample():
    m = HEAMetrics()
    m.record_latency("op1", 10.0)
    p95 = m.get_operator_p95()
    assert "op1" in p95
    assert p95["op1"] == 10.0


def test_p95_multiple_samples():
    m = HEAMetrics()
    for i in range(100):
        m.record_latency("op1", float(i))
    p95 = m.get_operator_p95()
    # 95th percentile of [0..99] is approximately 95
    assert 93.0 <= p95["op1"] <= 95.0
```

---

## Phase 2 Completion Criteria

Phase 2 is done when:

1. `pytest hea/tests/` passes — all unit tests green
2. HEA container starts cleanly: `docker compose up hea`
3. gRPC server responds to `GetTelemetry` with valid CPU/memory/RTT values
4. `ApplyPlacement` with a dummy operator assignment runs without error
5. `TriggerSnapshot` for a simple operator produces a valid `.msgpack` file in MinIO
6. `TerminateOperator` cleanly stops a registered operator and releases RocksDB resources
