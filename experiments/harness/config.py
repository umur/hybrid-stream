from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal
import itertools

Workload = Literal["W1", "W2", "W3"]
System   = Literal["HybridStream", "B1", "B2"]
Network  = Literal["N1", "N2", "N3"]


@dataclass
class NetworkProfile:
    name:           Network
    rtt_ms:         int
    bandwidth_mbps: int
    jitter_ms:      int

    def tc_netem_args(self, interface: str) -> str:
        delay_ms = self.rtt_ms // 2
        return (
            f"tc qdisc add dev {interface} root netem "
            f"delay {delay_ms}ms {self.jitter_ms}ms "
            f"rate {self.bandwidth_mbps}mbit"
        )

    def tc_netem_clear(self, interface: str) -> str:
        return f"tc qdisc del dev {interface} root"


NETWORK_PROFILES: dict[Network, NetworkProfile] = {
    "N1": NetworkProfile("N1", rtt_ms=10,  bandwidth_mbps=1000, jitter_ms=1),
    "N2": NetworkProfile("N2", rtt_ms=50,  bandwidth_mbps=100,  jitter_ms=5),
    "N3": NetworkProfile("N3", rtt_ms=150, bandwidth_mbps=50,   jitter_ms=15),
}


@dataclass
class WorkloadConfig:
    name:             Workload
    ingest_rate_eps:  int
    slo_ms:           float
    duration_s:       int = 3600
    warmup_s:         int = 600
    generator_module: str = ""


WORKLOAD_CONFIGS: dict[Workload, WorkloadConfig] = {
    "W1": WorkloadConfig("W1", ingest_rate_eps=2_000_000, slo_ms=5.0,    generator_module="generators.w1_generator"),
    "W2": WorkloadConfig("W2", ingest_rate_eps=50_000,    slo_ms=2000.0, generator_module="generators.w2_generator"),
    "W3": WorkloadConfig("W3", ingest_rate_eps=500_000,   slo_ms=1.0,    generator_module="generators.w3_generator"),
}


@dataclass
class ExperimentConfig:
    workload:    Workload
    system:      System
    network:     Network
    repetitions: int = 10

    @property
    def config_id(self) -> str:
        return f"{self.workload}-{self.system}-{self.network}"


def build_experiment_matrix() -> list[ExperimentConfig]:
    """63 configs = 3 workloads × 3 systems × 3 networks = 27; ×10 reps = 270 total runs."""
    configs = []
    for w, s, n in itertools.product(["W1", "W2", "W3"], ["HybridStream", "B1", "B2"], ["N1", "N2", "N3"]):
        configs.append(ExperimentConfig(workload=w, system=s, network=n))
    return configs


EXPERIMENT_MATRIX = build_experiment_matrix()
assert len(EXPERIMENT_MATRIX) == 27
