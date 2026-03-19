# Phase 5 — Workload Implementations (W1, W2, W3)

> **Depends on:** Phase 2 complete (HEA `BaseOperator` and `OperatorEngine`), Phase 4 complete (Java operator logic reference for consistency)  
> **Goal:** Three synthetic workloads that reproduce the exact evaluation scenarios described in §6.2 of the paper. Each workload is a Python package of `BaseOperator` subclasses registered with the HEA operator registry.  
> Estimated scope: ~1,600 lines of Python across W1/W2/W3.

---

## Deliverables Checklist

- [ ] `workloads/pyproject.toml`
- [ ] `workloads/w1/` — W1: Smart-city traffic monitoring (12 operators, 2M ev/s, SLO 5ms, CPU stress)
  - [ ] `normalizer.py` — 5× NormalizerOperator
  - [ ] `aggregator.py` — 5× FeatureAggWindow
  - [ ] `join.py`       — 1× MultiStreamJoin
  - [ ] `classifier.py` — 1× BinaryClassifier
  - [ ] `dag.py`        — W1 operator DAG + registration
- [ ] `workloads/w2/` — W2: Industrial IoT anomaly detection (3 op types / 521 instances, 50k ev/s, SLO 2s, memory stress)
  - [ ] `detector.py`   — VehicleDetector (500 instances)
  - [ ] `zone_agg.py`   — ZoneAggregator (20 instances)
  - [ ] `pattern.py`    — PatternDetector (1 instance)
  - [ ] `dag.py`        — W2 operator DAG + registration
- [ ] `workloads/w3/` — W3: Financial stream (30 op types, 500k ev/s, SLO 1ms, ingest spike stress)
  - [ ] `risk.py`       — 8× RiskCheck (SLO 1ms)
  - [ ] `anomaly.py`    — 4× AnomalyDetector (SLO 5ms)
  - [ ] `stat_agg.py`   — 12× StatAggregator (batch)
  - [ ] `compliance.py` — 6× ComplianceLogger (batch)
  - [ ] `dag.py`        — W3 operator DAG + registration
- [ ] `workloads/generators/` — Kafka event generators for each workload
  - [ ] `w1_generator.py`
  - [ ] `w2_generator.py`
  - [ ] `w3_generator.py`
- [ ] `workloads/tests/` — unit tests for all operator types
- [ ] All tests passing

---

## Step 1 — `workloads/pyproject.toml`

```toml
[tool.poetry]
name = "hybridstream-workloads"
version = "0.1.0"
description = "HybridStream synthetic evaluation workloads (W1, W2, W3)"
packages = [
    {include = "w1"},
    {include = "w2"},
    {include = "w3"},
    {include = "generators"},
]

[tool.poetry.dependencies]
python = "^3.12"
hybridstream-common = {path = "../hybridstream-common", develop = true}
hybridstream-hea    = {path = "../hea",                  develop = true}
aiokafka  = "^0.10"
numpy     = "^1.26"
scipy     = "^1.12"
msgpack   = "^1.0"

[tool.poetry.group.dev.dependencies]
pytest           = "^8.0"
pytest-asyncio   = "^0.23"
```

---

## Workload W1: Smart-City Traffic Monitoring

**Specification:**
- 12 operators: 5 NormalizerOperator + 5 FeatureAggWindow + 1 MultiStreamJoin + 1 BinaryClassifier
- Baseline ingest rate: 2M events/second
- SLO: 5ms end-to-end p95 latency
- Stress profile: CPU-bound (5 per-zone normalizers run in ProcessPoolExecutor)
- Input topics: `w1-raw-zone-{1..5}`
- Output topic: `w1-classified`

### `workloads/w1/normalizer.py`

```python
from __future__ import annotations
import math
from typing import Any
from hea.hea.execution.base_operator import BaseOperator
from hea.hea.execution.decorators import cpu_bound


@cpu_bound  # CPU-intensive: normalizes raw sensor values at 2M ev/s
class NormalizerOperator(BaseOperator):
    """
    Per-zone signal normalizer.
    Applies z-score normalization using a running EWMA mean and std.
    5 instances, one per traffic zone (zone_1 through zone_5).
    SLO: 5ms (part of the 5ms end-to-end chain).
    """

    operator_type = "NormalizerOperator"

    def __init__(self, operator_id: str, zone_id: str, alpha: float = 0.01):
        self.operator_id = operator_id
        self.zone_id     = zone_id
        self._alpha      = alpha    # EWMA smoothing for mean/std estimation
        self._mean       = 0.0
        self._variance   = 1.0     # Welford online variance
        self._count      = 0

    def get_slo_ms(self) -> float:
        return 5.0

    def get_lambda_class(self) -> str:
        return "standard"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        value = float(record.get("sensor_value", 0.0))

        # Welford's online algorithm for mean and variance
        self._count += 1
        delta       = value - self._mean
        self._mean += delta / self._count
        delta2      = value - self._mean
        self._variance = ((self._count - 1) * self._variance + delta * delta2) / self._count

        std = math.sqrt(max(self._variance, 1e-9))
        normalized = (value - self._mean) / std

        output = dict(record)
        output.update({
            "zone_id":          self.zone_id,
            "normalized_value": normalized,
            "sensor_mean":      self._mean,
            "sensor_std":       std,
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "zone_id":  self.zone_id,
            "mean":     self._mean,
            "variance": self._variance,
            "count":    self._count,
            "alpha":    self._alpha,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._mean     = float(state.get("mean",     0.0))
        self._variance = float(state.get("variance", 1.0))
        self._count    = int(state.get("count",      0))
        self._alpha    = float(state.get("alpha",    0.01))
```

### `workloads/w1/aggregator.py`

```python
from __future__ import annotations
import collections
import statistics
from typing import Any
from hea.hea.execution.base_operator import BaseOperator
from hea.hea.execution.decorators import cpu_bound


@cpu_bound  # Rolling window stats across 2M ev/s is CPU-intensive
class FeatureAggWindow(BaseOperator):
    """
    Sliding window aggregator: computes sum, mean, min, max, p95 over a tumbling window.
    5 instances, one per zone.
    Window size: 1000 events.
    SLO: 5ms (contributes to end-to-end W1 chain).
    """

    operator_type = "FeatureAggWindow"

    def __init__(self, operator_id: str, zone_id: str, window_size: int = 1000):
        self.operator_id  = operator_id
        self.zone_id      = zone_id
        self._window_size = window_size
        self._window: collections.deque[float] = collections.deque(maxlen=window_size)
        self._emit_every  = 100  # Emit aggregate every 100 records (not every record)
        self._count_since_emit = 0

    def get_slo_ms(self) -> float:
        return 5.0

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        value = float(record.get("normalized_value", 0.0))
        self._window.append(value)
        self._count_since_emit += 1

        # Emit aggregate every emit_every records to reduce downstream pressure
        if self._count_since_emit < self._emit_every:
            return []

        self._count_since_emit = 0
        window_list = list(self._window)
        sorted_w    = sorted(window_list)
        p95_idx     = max(0, int(len(sorted_w) * 0.95) - 1)

        return [{
            "zone_id":         self.zone_id,
            "agg_sum":         sum(window_list),
            "agg_mean":        statistics.mean(window_list),
            "agg_min":         min(window_list),
            "agg_max":         max(window_list),
            "agg_p95":         sorted_w[p95_idx],
            "agg_stdev":       statistics.stdev(window_list) if len(window_list) > 1 else 0.0,
            "window_count":    len(window_list),
            "source_ts":       record.get("timestamp", 0),
        }]

    def get_state(self) -> dict[str, Any]:
        return {
            "zone_id":     self.zone_id,
            "window":      list(self._window),
            "window_size": self._window_size,
            "emit_every":  self._emit_every,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._window_size = int(state.get("window_size", 1000))
        self._window      = collections.deque(state.get("window", []), maxlen=self._window_size)
        self._emit_every  = int(state.get("emit_every",  100))
```

### `workloads/w1/join.py`

```python
from __future__ import annotations
import time
from typing import Any
from hea.hea.execution.base_operator import BaseOperator


class MultiStreamJoin(BaseOperator):
    """
    Joins aggregated features from all 5 zones into a single multi-zone feature vector.
    Maintains a tumbling join window: collects one aggregate per zone per window.
    Emits when all 5 zones have contributed to the current window.
    SLO: 5ms.
    """

    operator_type = "MultiStreamJoin"

    def __init__(self, operator_id: str, n_zones: int = 5, window_timeout_ms: float = 100.0):
        self.operator_id      = operator_id
        self._n_zones         = n_zones
        self._window_timeout  = window_timeout_ms / 1000.0  # convert to seconds
        self._current_window: dict[str, dict] = {}  # zone_id → latest aggregate
        self._window_start    = time.monotonic()

    def get_slo_ms(self) -> float:
        return 5.0

    def get_lambda_class(self) -> str:
        return "standard"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        zone_id = record.get("zone_id", "unknown")
        self._current_window[zone_id] = record

        now = time.monotonic()
        timeout_exceeded = (now - self._window_start) > self._window_timeout
        all_zones_present = len(self._current_window) >= self._n_zones

        if all_zones_present or timeout_exceeded:
            output = self._emit_join()
            self._current_window = {}
            self._window_start   = now
            return [output]

        return []

    def _emit_join(self) -> dict[str, Any]:
        """Merge all zone aggregates into one feature vector."""
        merged = {"join_timestamp": time.time(), "zones_present": list(self._current_window.keys())}
        for zone_id, agg in self._current_window.items():
            prefix = f"{zone_id}_"
            merged[f"{prefix}mean"] = agg.get("agg_mean", 0.0)
            merged[f"{prefix}max"]  = agg.get("agg_max",  0.0)
            merged[f"{prefix}p95"]  = agg.get("agg_p95",  0.0)
        return merged

    def get_state(self) -> dict[str, Any]:
        return {
            "n_zones":        self._n_zones,
            "window_timeout": self._window_timeout,
            "current_window": self._current_window,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._n_zones        = int(state.get("n_zones",   5))
        self._window_timeout = float(state.get("window_timeout", 0.1))
        self._current_window = state.get("current_window", {})
        self._window_start   = time.monotonic()
```

### `workloads/w1/classifier.py`

```python
from __future__ import annotations
from typing import Any
from hea.hea.execution.base_operator import BaseOperator
from hea.hea.execution.decorators import cpu_bound


@cpu_bound
class BinaryClassifier(BaseOperator):
    """
    Classifies the joined feature vector as normal/anomalous traffic.
    Uses a simple threshold-based classifier (representative of feature engineering overhead).
    Single instance at the end of the W1 pipeline.
    SLO: 5ms (critical — tail of the end-to-end chain).
    """

    operator_type = "BinaryClassifier"

    def __init__(self, operator_id: str, threshold: float = 0.6):
        self.operator_id = operator_id
        self._threshold  = threshold
        self._tp = self._fp = self._tn = self._fn = 0  # Confusion matrix counters

    def get_slo_ms(self) -> float:
        return 5.0

    def get_lambda_class(self) -> str:
        return "critical"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        # Compute a composite score from zone aggregates
        zone_maxes = [v for k, v in record.items() if k.endswith("_max")]
        score = sum(zone_maxes) / len(zone_maxes) if zone_maxes else 0.0

        label    = 1 if score >= self._threshold else 0
        confidence = score if label == 1 else (1.0 - score)

        output = dict(record)
        output.update({
            "label":      label,
            "score":      round(score, 4),
            "confidence": round(confidence, 4),
            "threshold":  self._threshold,
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "threshold": self._threshold,
            "tp": self._tp, "fp": self._fp,
            "tn": self._tn, "fn": self._fn,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._threshold = float(state.get("threshold", 0.6))
        self._tp = int(state.get("tp", 0))
        self._fp = int(state.get("fp", 0))
        self._tn = int(state.get("tn", 0))
        self._fn = int(state.get("fn", 0))
```

---

## Workload W2: Industrial IoT Anomaly Detection

**Specification:**
- 3 operator types / 521 instances: 500 VehicleDetector (SLO 2s) + 20 ZoneAggregator + 1 PatternDetector
- Baseline ingest rate: 50k events/second
- SLO: 2s for VehicleDetector instances
- Stress profile: memory-intensive (521 concurrent operator state stores)
- AODE scoring matrix: 3×5 (operator types × tiers)

### `workloads/w2/detector.py`

```python
from __future__ import annotations
import time
import collections
from typing import Any
from hea.hea.execution.base_operator import BaseOperator


class VehicleDetector(BaseOperator):
    """
    Per-sensor vehicle detection with EWMA state.
    500 instances, each monitoring one roadside sensor.
    State per instance: ~1.2 KB (EWMA window + config).
    Total state for 500 instances: ~600 KB (memory stress).
    SLO: 2s (standard).
    """

    operator_type = "VehicleDetector"

    def __init__(self, operator_id: str, sensor_id: str, alpha: float = 0.2):
        self.operator_id = operator_id
        self._sensor_id  = sensor_id
        self._alpha      = alpha
        self._ewma_occ   = 0.0     # EWMA occupancy
        self._ewma_speed = 0.0     # EWMA speed
        self._detection_count = 0
        self._last_detection_ts: float | None = None
        # Rolling history for headway estimation (last 100 detections)
        self._detection_times: collections.deque[float] = collections.deque(maxlen=100)

    def get_slo_ms(self) -> float:
        return 2000.0  # 2s SLO

    def get_lambda_class(self) -> str:
        return "standard"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        occupancy = float(record.get("occupancy", 0.0))
        speed     = float(record.get("speed_kmh", 0.0))
        ts        = float(record.get("timestamp", time.time()))

        # EWMA update (α = 0.2, per paper §5.1.3)
        self._ewma_occ   = (1 - self._alpha) * self._ewma_occ   + self._alpha * occupancy
        self._ewma_speed = (1 - self._alpha) * self._ewma_speed + self._alpha * speed

        detected = self._ewma_occ > 0.15 and self._ewma_speed > 2.0

        if detected:
            self._detection_count += 1
            self._last_detection_ts = ts
            self._detection_times.append(ts)

        # Mean headway from detection history
        headway_s = None
        if len(self._detection_times) >= 2:
            intervals = [self._detection_times[i] - self._detection_times[i-1]
                        for i in range(1, len(self._detection_times))]
            headway_s = sum(intervals) / len(intervals)

        return [{
            "sensor_id":         self._sensor_id,
            "vehicle_detected":  detected,
            "ewma_occupancy":    round(self._ewma_occ,   4),
            "ewma_speed_kmh":    round(self._ewma_speed, 4),
            "detection_count":   self._detection_count,
            "mean_headway_s":    round(headway_s, 3) if headway_s else None,
            "timestamp":         ts,
        }]

    def get_state(self) -> dict[str, Any]:
        return {
            "sensor_id":        self._sensor_id,
            "alpha":            self._alpha,
            "ewma_occ":         self._ewma_occ,
            "ewma_speed":       self._ewma_speed,
            "detection_count":  self._detection_count,
            "last_detection_ts": self._last_detection_ts,
            "detection_times":  list(self._detection_times),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._alpha              = float(state.get("alpha",  0.2))
        self._ewma_occ           = float(state.get("ewma_occ",   0.0))
        self._ewma_speed         = float(state.get("ewma_speed",  0.0))
        self._detection_count    = int(state.get("detection_count", 0))
        self._last_detection_ts  = state.get("last_detection_ts")
        self._detection_times    = collections.deque(state.get("detection_times", []), maxlen=100)
```

### `workloads/w2/zone_agg.py`

```python
from __future__ import annotations
import time
from typing import Any
from hea.hea.execution.base_operator import BaseOperator


class ZoneAggregator(BaseOperator):
    """
    Aggregates detection counts and flow statistics per traffic zone.
    20 instances, each covering 25 sensors (500 detectors / 20 zones).
    Batch operator — no hard SLO.
    Memory stress: maintains per-sensor detection history per zone.
    """

    operator_type = "ZoneAggregator"

    def __init__(self, operator_id: str, zone_id: str, n_sensors: int = 25):
        self.operator_id   = operator_id
        self._zone_id      = zone_id
        self._n_sensors    = n_sensors
        self._sensor_counts: dict[str, int] = {}     # sensor_id → detection count
        self._zone_total   = 0
        self._last_emit_ts = time.monotonic()
        self._emit_interval = 5.0  # Emit zone summary every 5 seconds

    def get_slo_ms(self) -> float | None:
        return None  # Batch operator

    def get_lambda_class(self) -> str:
        return "batch"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        sensor_id = record.get("sensor_id", "unknown")
        detected  = bool(record.get("vehicle_detected", False))

        if detected:
            self._sensor_counts[sensor_id] = self._sensor_counts.get(sensor_id, 0) + 1
            self._zone_total += 1

        now = time.monotonic()
        if now - self._last_emit_ts >= self._emit_interval:
            self._last_emit_ts = now
            return [{
                "zone_id":          self._zone_id,
                "total_detections": self._zone_total,
                "active_sensors":   len(self._sensor_counts),
                "density":          len(self._sensor_counts) / max(self._n_sensors, 1),
                "timestamp":        time.time(),
            }]

        return []

    def get_state(self) -> dict[str, Any]:
        return {
            "zone_id":       self._zone_id,
            "n_sensors":     self._n_sensors,
            "sensor_counts": self._sensor_counts,
            "zone_total":    self._zone_total,
            "emit_interval": self._emit_interval,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._zone_id       = state.get("zone_id",      self._zone_id)
        self._n_sensors     = int(state.get("n_sensors",   25))
        self._sensor_counts = state.get("sensor_counts", {})
        self._zone_total    = int(state.get("zone_total",   0))
        self._emit_interval = float(state.get("emit_interval", 5.0))
        self._last_emit_ts  = time.monotonic()
```

### `workloads/w2/pattern.py`

```python
from __future__ import annotations
import collections
from typing import Any
from hea.hea.execution.base_operator import BaseOperator


class PatternDetector(BaseOperator):
    """
    Detects anomalous traffic flow patterns across zones.
    Single instance at the top of the W2 pipeline.
    Consumes zone summaries from all 20 ZoneAggregators.
    Looks for congestion waves and incident signatures.
    Batch operator — no SLO.
    """

    operator_type = "PatternDetector"

    def __init__(self, operator_id: str, congestion_threshold: float = 0.7):
        self.operator_id          = operator_id
        self._congestion_threshold = congestion_threshold
        # Zone density history: zone_id → deque of last 20 density samples
        self._zone_history: dict[str, collections.deque[float]] = {}
        self._incident_count = 0

    def get_slo_ms(self) -> float | None:
        return None  # Batch

    def get_lambda_class(self) -> str:
        return "batch"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        zone_id = record.get("zone_id", "unknown")
        density = float(record.get("density", 0.0))

        if zone_id not in self._zone_history:
            self._zone_history[zone_id] = collections.deque(maxlen=20)
        self._zone_history[zone_id].append(density)

        # Pattern: congestion wave (3+ consecutive zones above threshold)
        congested_zones = [z for z, hist in self._zone_history.items()
                          if hist and hist[-1] > self._congestion_threshold]

        incident_detected = len(congested_zones) >= 3

        if incident_detected:
            self._incident_count += 1
            return [{
                "pattern_type":      "congestion_wave",
                "congested_zones":   congested_zones,
                "incident_count":    self._incident_count,
                "severity":          len(congested_zones),
                "timestamp":         record.get("timestamp", 0),
            }]

        return []

    def get_state(self) -> dict[str, Any]:
        return {
            "congestion_threshold": self._congestion_threshold,
            "zone_history":         {k: list(v) for k, v in self._zone_history.items()},
            "incident_count":       self._incident_count,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._congestion_threshold = float(state.get("congestion_threshold", 0.7))
        self._incident_count       = int(state.get("incident_count", 0))
        raw_history = state.get("zone_history", {})
        self._zone_history = {
            k: collections.deque(v, maxlen=20) for k, v in raw_history.items()
        }
```

---

## Workload W3: Financial Stream Processing

**Specification:**
- 30 operator types: 8 RiskCheck + 4 AnomalyDetector + 12 StatAggregator + 6 ComplianceLogger
- Baseline ingest rate: 500k events/second
- SLO: 1ms (RiskCheck, critical), 5ms (AnomalyDetector)
- Stress profile: ingest spike stress (rate spikes 5× over 60 seconds)

### `workloads/w3/risk.py`

```python
from __future__ import annotations
from typing import Any
from hea.hea.execution.base_operator import BaseOperator
from hea.hea.execution.decorators import cpu_bound


@cpu_bound  # Must complete in <1ms — runs in process pool
class RiskCheck(BaseOperator):
    """
    Ultra-low latency risk exposure check.
    8 instances, each responsible for one risk category
    (credit, market, liquidity, operational, counterparty, settlement, model, reputational).
    SLO: 1ms (critical class).
    Minimal state — limit table only.
    """

    operator_type = "RiskCheck"

    # Risk category → default limit
    CATEGORIES = {
        "credit":         5_000_000.0,
        "market":        10_000_000.0,
        "liquidity":      2_000_000.0,
        "operational":    1_000_000.0,
        "counterparty":   3_000_000.0,
        "settlement":       500_000.0,
        "model":          1_500_000.0,
        "reputational":     250_000.0,
    }

    def __init__(self, operator_id: str, risk_category: str):
        self.operator_id    = operator_id
        self._risk_category = risk_category
        self._limit         = self.CATEGORIES.get(risk_category, 1_000_000.0)
        self._breach_count  = 0
        self._total_checked = 0

    def get_slo_ms(self) -> float:
        return 1.0

    def get_lambda_class(self) -> str:
        return "critical"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        exposure = float(record.get("exposure", 0.0))
        self._total_checked += 1

        exceeded = exposure > self._limit
        if exceeded:
            self._breach_count += 1

        output = dict(record)
        output.update({
            "risk_category":   self._risk_category,
            "limit":           self._limit,
            "exposure":        exposure,
            "risk_exceeded":   exceeded,
            "exposure_ratio":  exposure / self._limit if self._limit > 0 else 0.0,
            "breach_count":    self._breach_count,
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "risk_category":  self._risk_category,
            "limit":          self._limit,
            "breach_count":   self._breach_count,
            "total_checked":  self._total_checked,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._risk_category = state.get("risk_category", self._risk_category)
        self._limit         = float(state.get("limit",        1_000_000.0))
        self._breach_count  = int(state.get("breach_count",  0))
        self._total_checked = int(state.get("total_checked", 0))
```

### `workloads/w3/anomaly.py`

```python
from __future__ import annotations
import math
import collections
from typing import Any
from hea.hea.execution.base_operator import BaseOperator
from hea.hea.execution.decorators import cpu_bound


@cpu_bound
class AnomalyDetector(BaseOperator):
    """
    EWMA-based anomaly detector using 3-sigma rule.
    4 instances, one per financial metric class:
    (price_deviation, volume_spike, spread_anomaly, order_flow_imbalance).
    SLO: 5ms (critical class due to trading alert sensitivity).
    """

    operator_type = "AnomalyDetector"

    def __init__(self, operator_id: str, metric_class: str, alpha: float = 0.2, z_threshold: float = 3.0):
        self.operator_id    = operator_id
        self._metric_class  = metric_class
        self._alpha         = alpha
        self._z_threshold   = z_threshold
        self._ewma_mean     = 0.0
        self._ewma_m2       = 1.0   # EWMA variance proxy
        self._anomaly_count = 0
        self._recent_zscores: collections.deque[float] = collections.deque(maxlen=100)

    def get_slo_ms(self) -> float:
        return 5.0

    def get_lambda_class(self) -> str:
        return "critical"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        value = float(record.get("value", 0.0))

        # EWMA mean update
        prev_mean = self._ewma_mean
        self._ewma_mean = (1 - self._alpha) * self._ewma_mean + self._alpha * value

        # EWMA variance update (Welford-inspired)
        delta = value - prev_mean
        self._ewma_m2 = (1 - self._alpha) * self._ewma_m2 + self._alpha * delta ** 2

        std = math.sqrt(max(self._ewma_m2, 1e-12))
        z   = abs(value - self._ewma_mean) / std if std > 0 else 0.0
        self._recent_zscores.append(z)

        is_anomaly = z > self._z_threshold
        if is_anomaly:
            self._anomaly_count += 1

        output = dict(record)
        output.update({
            "metric_class":  self._metric_class,
            "is_anomaly":    is_anomaly,
            "z_score":       round(z, 4),
            "ewma_mean":     round(self._ewma_mean, 6),
            "ewma_std":      round(std, 6),
            "anomaly_count": self._anomaly_count,
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "metric_class":   self._metric_class,
            "alpha":          self._alpha,
            "z_threshold":    self._z_threshold,
            "ewma_mean":      self._ewma_mean,
            "ewma_m2":        self._ewma_m2,
            "anomaly_count":  self._anomaly_count,
            "recent_zscores": list(self._recent_zscores),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._metric_class    = state.get("metric_class", self._metric_class)
        self._alpha           = float(state.get("alpha",       0.2))
        self._z_threshold     = float(state.get("z_threshold", 3.0))
        self._ewma_mean       = float(state.get("ewma_mean",   0.0))
        self._ewma_m2         = float(state.get("ewma_m2",     1.0))
        self._anomaly_count   = int(state.get("anomaly_count", 0))
        self._recent_zscores  = collections.deque(state.get("recent_zscores", []), maxlen=100)
```

### `workloads/w3/stat_agg.py`

```python
from __future__ import annotations
import math
from typing import Any
from hea.hea.execution.base_operator import BaseOperator


class StatAggregator(BaseOperator):
    """
    Online statistical aggregation using Welford's algorithm.
    12 instances, each covering one instrument class
    (equities, bonds, FX, commodities, derivatives, ETFs, options, futures,
     swaps, indices, crypto, structured_products).
    Batch operator — no SLO.
    """

    operator_type = "StatAggregator"

    def __init__(self, operator_id: str, instrument_class: str):
        self.operator_id       = operator_id
        self._instrument_class = instrument_class
        self._count   = 0
        self._mean    = 0.0
        self._m2      = 0.0   # Welford sum of squared deviations
        self._min     = float("inf")
        self._max     = float("-inf")

    def get_slo_ms(self) -> float | None:
        return None  # Batch

    def get_lambda_class(self) -> str:
        return "batch"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        value = float(record.get("value", 0.0))

        # Welford's online algorithm
        self._count += 1
        delta         = value - self._mean
        self._mean   += delta / self._count
        delta2        = value - self._mean
        self._m2     += delta * delta2

        self._min = min(self._min, value)
        self._max = max(self._max, value)

        variance = self._m2 / (self._count - 1) if self._count > 1 else 0.0
        std      = math.sqrt(variance)

        # Emit every 500 records
        if self._count % 500 == 0:
            return [{
                "instrument_class": self._instrument_class,
                "count":            self._count,
                "mean":             round(self._mean, 6),
                "std":              round(std, 6),
                "variance":         round(variance, 8),
                "min":              self._min,
                "max":              self._max,
            }]
        return []

    def get_state(self) -> dict[str, Any]:
        return {
            "instrument_class": self._instrument_class,
            "count":            self._count,
            "mean":             self._mean,
            "m2":               self._m2,
            "min":              self._min if self._min != float("inf")  else None,
            "max":              self._max if self._max != float("-inf") else None,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._instrument_class = state.get("instrument_class", self._instrument_class)
        self._count = int(state.get("count", 0))
        self._mean  = float(state.get("mean",  0.0))
        self._m2    = float(state.get("m2",    0.0))
        self._min   = float(state.get("min",   float("inf")))  if state.get("min") is not None  else float("inf")
        self._max   = float(state.get("max",   float("-inf"))) if state.get("max") is not None else float("-inf")
```

### `workloads/w3/compliance.py`

```python
from __future__ import annotations
import time
from typing import Any
from hea.hea.execution.base_operator import BaseOperator


class ComplianceLogger(BaseOperator):
    """
    Records compliance-relevant events for regulatory audit trail.
    6 instances, one per compliance domain:
    (mifid2, dodd_frank, basel3, sox, gdpr, aml).
    Batch operator — latency-insensitive; durability is the priority.
    State is append-only: log sequence number + event type counts.
    """

    operator_type = "ComplianceLogger"

    DOMAINS = ["mifid2", "dodd_frank", "basel3", "sox", "gdpr", "aml"]

    def __init__(self, operator_id: str, compliance_domain: str):
        self.operator_id       = operator_id
        self._domain           = compliance_domain
        self._log_seq          = 0
        self._event_counts: dict[str, int] = {}
        self._first_event_ts: float | None = None
        self._last_event_ts:  float | None = None

    def get_slo_ms(self) -> float | None:
        return None  # Batch — durability > speed

    def get_lambda_class(self) -> str:
        return "batch"

    async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        event_type = str(record.get("event_type", "unknown"))
        ts         = float(record.get("timestamp", time.time()))

        self._log_seq += 1
        self._event_counts[event_type] = self._event_counts.get(event_type, 0) + 1

        if self._first_event_ts is None:
            self._first_event_ts = ts
        self._last_event_ts = ts

        output = dict(record)
        output.update({
            "compliance_domain":  self._domain,
            "log_sequence":       self._log_seq,
            "compliance_logged":  True,
            "event_type_counts":  dict(self._event_counts),
            "logged_at":          time.time(),
        })
        return [output]

    def get_state(self) -> dict[str, Any]:
        return {
            "domain":          self._domain,
            "log_seq":         self._log_seq,
            "event_counts":    self._event_counts,
            "first_event_ts":  self._first_event_ts,
            "last_event_ts":   self._last_event_ts,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._domain          = state.get("domain",         self._domain)
        self._log_seq         = int(state.get("log_seq",    0))
        self._event_counts    = state.get("event_counts",   {})
        self._first_event_ts  = state.get("first_event_ts")
        self._last_event_ts   = state.get("last_event_ts")
```

---

## DAG Registrations

### `workloads/w1/dag.py`

```python
from hea.hea.operator_registry import register
from .normalizer  import NormalizerOperator
from .aggregator  import FeatureAggWindow
from .join        import MultiStreamJoin
from .classifier  import BinaryClassifier


def register_w1_operators():
    """Register all W1 operator types with the HEA operator registry."""
    register("NormalizerOperator", NormalizerOperator)
    register("FeatureAggWindow",   FeatureAggWindow)
    register("MultiStreamJoin",    MultiStreamJoin)
    register("BinaryClassifier",   BinaryClassifier)


def build_w1_pipeline(engine) -> list:
    """
    Instantiate W1 operators and return (operator, input_topics, output_topics) triples.
    Caller passes these to engine.register_operator().

    W1 DAG:
      w1-raw-zone-{1..5} → NormalizerOperator (5×) → FeatureAggWindow (5×)
                                                     → MultiStreamJoin (1×)
                                                     → BinaryClassifier (1×)
                                                     → w1-classified
    """
    pipeline = []
    ZONES = ["zone_1", "zone_2", "zone_3", "zone_4", "zone_5"]

    normalizers = []
    for zone in ZONES:
        op = NormalizerOperator(
            operator_id=f"normalizer-{zone}",
            zone_id=zone,
        )
        pipeline.append((op, [f"w1-raw-{zone}"], [f"w1-norm-{zone}"]))
        normalizers.append(op)

    aggregators = []
    for zone in ZONES:
        op = FeatureAggWindow(
            operator_id=f"agg-{zone}",
            zone_id=zone,
        )
        pipeline.append((op, [f"w1-norm-{zone}"], [f"w1-agg-{zone}"]))
        aggregators.append(op)

    join = MultiStreamJoin(operator_id="multi-join", n_zones=5)
    pipeline.append((join, [f"w1-agg-{z}" for z in ZONES], ["w1-joined"]))

    classifier = BinaryClassifier(operator_id="classifier")
    pipeline.append((classifier, ["w1-joined"], ["w1-classified"]))

    return pipeline
```

### `workloads/w2/dag.py`

```python
from hea.hea.operator_registry import register
from .detector  import VehicleDetector
from .zone_agg  import ZoneAggregator
from .pattern   import PatternDetector


def register_w2_operators():
    register("VehicleDetector", VehicleDetector)
    register("ZoneAggregator",  ZoneAggregator)
    register("PatternDetector", PatternDetector)


def build_w2_pipeline(engine) -> list:
    """
    W2 DAG:
      w2-sensors → VehicleDetector (500×) → ZoneAggregator (20×)
                                           → PatternDetector (1×)
                                           → w2-incidents
    """
    pipeline = []
    N_SENSORS = 500
    N_ZONES   = 20
    sensors_per_zone = N_SENSORS // N_ZONES  # 25

    # 500 VehicleDetector instances
    for i in range(N_SENSORS):
        zone_idx = i // sensors_per_zone
        zone_id  = f"zone_{zone_idx + 1:02d}"
        op = VehicleDetector(
            operator_id=f"detector-{i:04d}",
            sensor_id=f"sensor_{i:04d}",
        )
        pipeline.append((op, ["w2-sensors"], [f"w2-detections-{zone_id}"]))

    # 20 ZoneAggregator instances
    for i in range(N_ZONES):
        zone_id = f"zone_{i + 1:02d}"
        op = ZoneAggregator(
            operator_id=f"zone-agg-{zone_id}",
            zone_id=zone_id,
        )
        pipeline.append((op, [f"w2-detections-{zone_id}"], [f"w2-zone-{zone_id}"]))

    # 1 PatternDetector
    zone_topics = [f"w2-zone-zone_{i+1:02d}" for i in range(N_ZONES)]
    op = PatternDetector(operator_id="pattern-detector")
    pipeline.append((op, zone_topics, ["w2-incidents"]))

    return pipeline
```

### `workloads/w3/dag.py`

```python
from hea.hea.operator_registry import register
from .risk       import RiskCheck
from .anomaly    import AnomalyDetector
from .stat_agg   import StatAggregator
from .compliance import ComplianceLogger


def register_w3_operators():
    register("RiskCheck",        RiskCheck)
    register("AnomalyDetector",  AnomalyDetector)
    register("StatAggregator",   StatAggregator)
    register("ComplianceLogger", ComplianceLogger)


def build_w3_pipeline(engine) -> list:
    """
    W3 DAG: 30 operator types, 500k ev/s financial stream.
      w3-trades → RiskCheck (8×) → AnomalyDetector (4×)
                                  → StatAggregator (12×)
                                  → ComplianceLogger (6×)
                                  → w3-output
    """
    pipeline = []

    # 8 RiskCheck instances (one per risk category)
    for category in RiskCheck.CATEGORIES:
        op = RiskCheck(operator_id=f"risk-{category}", risk_category=category)
        pipeline.append((op, ["w3-trades"], [f"w3-risk-{category}"]))

    # 4 AnomalyDetector instances
    metric_classes = ["price_deviation", "volume_spike", "spread_anomaly", "order_flow_imbalance"]
    for mc in metric_classes:
        op = AnomalyDetector(operator_id=f"anomaly-{mc}", metric_class=mc)
        pipeline.append((op, ["w3-trades"], [f"w3-anomaly-{mc}"]))

    # 12 StatAggregator instances
    instruments = [
        "equities", "bonds", "fx", "commodities", "derivatives", "etfs",
        "options", "futures", "swaps", "indices", "crypto", "structured_products"
    ]
    for instr in instruments:
        op = StatAggregator(operator_id=f"stat-{instr}", instrument_class=instr)
        pipeline.append((op, ["w3-trades"], [f"w3-stats-{instr}"]))

    # 6 ComplianceLogger instances
    for domain in ComplianceLogger.DOMAINS:
        op = ComplianceLogger(operator_id=f"compliance-{domain}", compliance_domain=domain)
        pipeline.append((op, ["w3-trades"], [f"w3-compliance-{domain}"]))

    return pipeline
```

---

## Event Generators

### `workloads/generators/w1_generator.py`

```python
"""
W1 Traffic sensor event generator.
Produces 2M events/second across 5 zone topics.
"""

import asyncio
import time
import random
import msgpack
from aiokafka import AIOKafkaProducer


async def generate_w1(bootstrap_servers: str, rate_eps: int = 2_000_000):
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        compression_type="lz4",
        acks=1,  # Relaxed acks for max throughput in generator
    )
    await producer.start()

    ZONES     = ["zone_1", "zone_2", "zone_3", "zone_4", "zone_5"]
    interval  = len(ZONES) / rate_eps  # seconds between batches per topic

    print(f"W1 generator: {rate_eps:,} ev/s across {len(ZONES)} zones")

    try:
        while True:
            batch_start = time.monotonic()
            for zone in ZONES:
                record = {
                    "zone_id":      zone,
                    "sensor_value": random.gauss(50.0, 15.0),  # synthetic sensor readings
                    "timestamp":    time.time(),
                    "seq":          int(time.time() * 1e6),
                }
                payload = msgpack.packb(record, use_bin_type=True)
                await producer.send(f"w1-raw-{zone}", payload)

            elapsed = time.monotonic() - batch_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    finally:
        await producer.stop()


if __name__ == "__main__":
    import sys
    bootstrap = sys.argv[1] if len(sys.argv) > 1 else "localhost:9092"
    rate      = int(sys.argv[2]) if len(sys.argv) > 2 else 2_000_000
    asyncio.run(generate_w1(bootstrap, rate))
```

### `workloads/generators/w3_generator.py`

```python
"""
W3 Financial trade event generator with ingest spike stress.
Baseline: 500k ev/s. Spike: 5× for 60 seconds every 10 minutes.
"""

import asyncio
import time
import random
import msgpack
from aiokafka import AIOKafkaProducer


async def generate_w3(bootstrap_servers: str, baseline_eps: int = 500_000):
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        compression_type="lz4",
        acks=1,
    )
    await producer.start()

    spike_active   = False
    spike_start    = 0.0
    SPIKE_DURATION = 60.0      # seconds
    SPIKE_INTERVAL = 600.0     # every 10 minutes
    SPIKE_FACTOR   = 5         # 5× baseline during spike

    print(f"W3 generator: {baseline_eps:,} ev/s baseline, {baseline_eps * SPIKE_FACTOR:,} ev/s during spikes")

    RISK_CATEGORIES = ["credit", "market", "liquidity", "operational",
                       "counterparty", "settlement", "model", "reputational"]
    EVENT_TYPES = ["trade", "order", "cancel", "modification", "settlement"]

    try:
        last_spike_ts = time.monotonic()

        while True:
            now = time.monotonic()

            # Spike management
            if not spike_active and (now - last_spike_ts) >= SPIKE_INTERVAL:
                spike_active = True
                spike_start  = now
                print(f"W3: Ingest spike started at {time.strftime('%H:%M:%S')}")

            if spike_active and (now - spike_start) >= SPIKE_DURATION:
                spike_active   = False
                last_spike_ts  = now
                print(f"W3: Ingest spike ended")

            current_rate = baseline_eps * SPIKE_FACTOR if spike_active else baseline_eps
            batch_size   = max(1, current_rate // 1000)  # 1ms batches

            for _ in range(batch_size):
                category = random.choice(RISK_CATEGORIES)
                record = {
                    "instrument":   f"INST-{random.randint(1, 10000):05d}",
                    "event_type":   random.choice(EVENT_TYPES),
                    "exposure":     abs(random.gauss(500_000, 200_000)),
                    "value":        random.gauss(100.0, 20.0),
                    "risk_category": category,
                    "timestamp":    time.time(),
                }
                payload = msgpack.packb(record, use_bin_type=True)
                await producer.send("w3-trades", payload)

            await asyncio.sleep(0.001)  # 1ms batch interval

    finally:
        await producer.stop()


if __name__ == "__main__":
    import sys
    bootstrap = sys.argv[1] if len(sys.argv) > 1 else "localhost:9092"
    rate      = int(sys.argv[2]) if len(sys.argv) > 2 else 500_000
    asyncio.run(generate_w3(bootstrap, rate))
```

---

## Unit Tests

### `workloads/tests/test_w1_operators.py`

```python
import asyncio
import pytest
from w1.normalizer  import NormalizerOperator
from w1.aggregator  import FeatureAggWindow
from w1.join        import MultiStreamJoin
from w1.classifier  import BinaryClassifier


@pytest.mark.asyncio
async def test_normalizer_state_roundtrip():
    op = NormalizerOperator("norm-1", "zone_1")
    for i in range(100):
        await op.process({"sensor_value": float(i), "timestamp": float(i)})
    state = op.get_state()
    op2 = NormalizerOperator("norm-1", "zone_1")
    op2.restore_state(state)
    assert abs(op2._mean - op._mean) < 1e-9


@pytest.mark.asyncio
async def test_normalizer_output_format():
    op = NormalizerOperator("norm-1", "zone_1")
    result = await op.process({"sensor_value": 50.0, "timestamp": 0.0})
    assert len(result) == 1
    assert "normalized_value" in result[0]
    assert "zone_id" in result[0]


@pytest.mark.asyncio
async def test_feature_agg_emits_on_interval():
    op = FeatureAggWindow("agg-1", "zone_1", window_size=1000)
    results = []
    for i in range(200):
        out = await op.process({"normalized_value": float(i), "timestamp": float(i)})
        results.extend(out)
    # Should emit at i=99 and i=199
    assert len(results) == 2
    assert "agg_mean" in results[0]
    assert "agg_p95"  in results[0]


@pytest.mark.asyncio
async def test_binary_classifier_state_roundtrip():
    op = BinaryClassifier("clf-1", threshold=0.5)
    state = op.get_state()
    op2 = BinaryClassifier("clf-1")
    op2.restore_state(state)
    assert op2._threshold == 0.5


@pytest.mark.asyncio
async def test_multi_join_emits_when_all_zones_present():
    op = MultiStreamJoin("join-1", n_zones=3, window_timeout_ms=5000.0)
    out1 = await op.process({"zone_id": "zone_1", "agg_mean": 1.0, "agg_max": 2.0, "agg_p95": 1.5})
    out2 = await op.process({"zone_id": "zone_2", "agg_mean": 2.0, "agg_max": 3.0, "agg_p95": 2.5})
    out3 = await op.process({"zone_id": "zone_3", "agg_mean": 3.0, "agg_max": 4.0, "agg_p95": 3.5})
    assert len(out1) == 0
    assert len(out2) == 0
    assert len(out3) == 1  # Emits after all 3 zones present
    assert "zone_1_mean" in out3[0]
```

### `workloads/tests/test_w3_operators.py`

```python
import asyncio
import pytest
from w3.risk       import RiskCheck
from w3.anomaly    import AnomalyDetector
from w3.stat_agg   import StatAggregator
from w3.compliance import ComplianceLogger


@pytest.mark.asyncio
async def test_risk_check_exceeds_limit():
    op = RiskCheck("risk-credit", "credit")
    result = await op.process({"exposure": 99_999_999.0, "timestamp": 0.0})
    assert result[0]["risk_exceeded"] is True
    assert result[0]["breach_count"] == 1


@pytest.mark.asyncio
async def test_risk_check_under_limit():
    op = RiskCheck("risk-credit", "credit")
    result = await op.process({"exposure": 1.0, "timestamp": 0.0})
    assert result[0]["risk_exceeded"] is False


@pytest.mark.asyncio
async def test_anomaly_detector_state_roundtrip():
    op = AnomalyDetector("anomaly-1", "price_deviation")
    for v in [100.0, 102.0, 98.0, 101.0, 99.0]:
        await op.process({"value": v, "timestamp": 0.0})
    state = op.get_state()
    op2 = AnomalyDetector("anomaly-1", "price_deviation")
    op2.restore_state(state)
    assert abs(op2._ewma_mean - op._ewma_mean) < 1e-9


@pytest.mark.asyncio
async def test_stat_aggregator_welford():
    op = StatAggregator("stat-fx", "fx")
    for i in range(1, 11):
        await op.process({"value": float(i), "timestamp": 0.0})
    # Mean of 1..10 = 5.5
    assert abs(op._mean - 5.5) < 0.001


@pytest.mark.asyncio
async def test_compliance_logger_sequence():
    op = ComplianceLogger("compliance-aml", "aml")
    for i in range(5):
        await op.process({"event_type": "trade", "timestamp": float(i)})
    state = op.get_state()
    assert state["log_seq"] == 5
    assert state["event_counts"]["trade"] == 5
```

---

## Phase 5 Completion Criteria

Phase 5 is done when:

1. `pytest workloads/tests/` passes — all operator unit tests green
2. All operators implement `process()`, `get_state()`, `restore_state()` correctly
3. `get_state()` → `restore_state()` roundtrip is lossless for all operator types
4. State snapshots are schema-registry-compatible (keys match JSON schema field names)
5. W1 generator produces measurable events at 2M ev/s target (verify with `kafka-consumer-groups` lag)
6. W3 generator correctly applies 5× spike pattern (verify in generator logs)
7. All operators registered via `dag.py` with correct type strings matching schema-registry
8. W2 builds correctly: 500 VehicleDetector + 20 ZoneAggregator + 1 PatternDetector = 521 instances
