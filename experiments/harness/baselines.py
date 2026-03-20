from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Literal

log = logging.getLogger(__name__)
BaselineType = Literal["B1", "B2"]


@dataclass
class B1Config:
    """Cloud-only Flink deployment: c5.4xlarge, 4 TMs × 2 slots."""
    flink_master:       str = "flink-master:8081"
    task_managers:      int = 4
    slots_per_tm:       int = 2
    jvm_heap_gb:        int = 6
    rocksdb_checkpoint: str = "s3://hybridstream-checkpoints/b1"


@dataclass
class B2Config:
    """Static hybrid: best offline placement, never adapts at runtime."""
    static_placement: dict
    edge_nodes: list[str] = field(default_factory=lambda: ["edge-node-1", "edge-node-2", "edge-node-3", "edge-node-4"])
    cloud_endpoint: str = "cloud:9092"


B2_PLACEMENTS = {
    ("W1", "N1"): {"NormalizerOperator": "edge-node-1", "FeatureAggWindow": "edge-node-2", "MultiStreamJoin": "edge-node-3", "BinaryClassifier": "edge-node-4"},
    ("W1", "N2"): {"NormalizerOperator": "edge-node-1", "FeatureAggWindow": "edge-node-2", "MultiStreamJoin": "cloud",        "BinaryClassifier": "cloud"},
    ("W1", "N3"): {"NormalizerOperator": "edge-node-1", "FeatureAggWindow": "edge-node-2", "MultiStreamJoin": "edge-node-3", "BinaryClassifier": "edge-node-4"},
    ("W2", "N1"): {"VehicleDetector": "edge-node-1", "ZoneAggregator": "edge-node-2", "PatternDetector": "cloud"},
    ("W2", "N2"): {"VehicleDetector": "edge-node-1", "ZoneAggregator": "edge-node-2", "PatternDetector": "cloud"},
    ("W2", "N3"): {"VehicleDetector": "edge-node-1", "ZoneAggregator": "edge-node-3", "PatternDetector": "edge-node-4"},
    ("W3", "N1"): {"RiskCheck": "cloud",        "AnomalyDetector": "edge-node-1", "StatAggregator": "edge-node-2", "ComplianceLogger": "edge-node-3"},
    ("W3", "N2"): {"RiskCheck": "cloud",        "AnomalyDetector": "cloud",        "StatAggregator": "edge-node-1", "ComplianceLogger": "edge-node-2"},
    ("W3", "N3"): {"RiskCheck": "edge-node-1", "AnomalyDetector": "edge-node-2", "StatAggregator": "edge-node-3", "ComplianceLogger": "edge-node-4"},
}


async def setup_baseline_b1(config: B1Config, workload: str) -> None:
    log.info("B1 ready: %d TMs × %d slots = %d task slots for %s",
             config.task_managers, config.slots_per_tm,
             config.task_managers * config.slots_per_tm, workload)


async def setup_baseline_b2(workload: str, network: str) -> B2Config:
    key = (workload, network)
    placement = B2_PLACEMENTS.get(key)
    if not placement:
        raise ValueError(f"No B2 static placement defined for {key}")
    config = B2Config(static_placement=placement)
    log.info("B2 static placement for %s/%s: %s", workload, network, placement)
    return config
