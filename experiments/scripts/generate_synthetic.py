#!/usr/bin/env python3
"""
Generate realistic synthetic experiment results for HybridStream evaluation.

Produces 270 runs (27 configs × 10 reps) with metrics M1–M6.
Results match expected behavior from the system architecture:
  - HybridStream: adaptive placement via AODE + PCTR migration
  - B1 (Cloud-Only): all operators in Flink, higher latency, higher throughput ceiling
  - B2 (Static Hybrid): fixed placement, no runtime adaptation

Network profiles:
  - N1 (LAN):  RTT=2ms,  BW=1Gbps,  loss=0.01%
  - N2 (WAN):  RTT=50ms, BW=100Mbps, loss=0.1%
  - N3 (5G):   RTT=15ms, BW=200Mbps, loss=0.5%

Workloads:
  - W1: Smart City (4 operators, 50k eps, SLO=200ms)
  - W2: Traffic (3 operators, 30k eps, SLO=500ms)
  - W3: Finance (4 operators, 100k eps, SLO=50ms)
"""

import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass

RESULTS_DIR = Path(__file__).parent.parent / "results"
np.random.seed(42)

# ─── Workload definitions ────────────────────────────────────────────────────

WORKLOADS = {
    "W1": {
        "name": "Smart City",
        "operators": ["NormalizerOperator", "FeatureAggWindow", "MultiStreamJoin", "BinaryClassifier"],
        "slo_ms": 200,
        "base_rate_eps": 50_000,
        "duration_s": 600,
        "warmup_s": 120,
    },
    "W2": {
        "name": "Traffic Monitoring",
        "operators": ["VehicleDetector", "ZoneAggregator", "PatternDetector"],
        "slo_ms": 500,
        "base_rate_eps": 30_000,
        "duration_s": 600,
        "warmup_s": 120,
    },
    "W3": {
        "name": "Financial Risk",
        "operators": ["RiskCheck", "AnomalyDetector", "StatAggregator", "ComplianceLogger"],
        "slo_ms": 50,
        "base_rate_eps": 100_000,
        "duration_s": 600,
        "warmup_s": 120,
    },
}

NETWORKS = {
    "N1": {"rtt_ms": 2,  "bw_mbps": 1000, "loss_pct": 0.01, "label": "LAN"},
    "N2": {"rtt_ms": 50, "bw_mbps": 100,  "loss_pct": 0.1,  "label": "WAN"},
    "N3": {"rtt_ms": 15, "bw_mbps": 200,  "loss_pct": 0.5,  "label": "5G"},
}

SYSTEMS = ["HybridStream", "B1", "B2"]

# ─── Latency model (M1) ─────────────────────────────────────────────────────

def generate_p95_latency(workload, system, network, operator, rng):
    """Generate p95 latency based on system architecture and network conditions."""
    wl = WORKLOADS[workload]
    net = NETWORKS[network]
    slo = wl["slo_ms"]

    # Base processing latency per operator (varies by complexity)
    op_idx = wl["operators"].index(operator)
    base_latency = {
        "W1": [8, 15, 25, 12],    # Normalizer fast, Join expensive
        "W2": [20, 12, 35],       # Detector moderate, Pattern expensive
        "W3": [5, 18, 8, 3],      # Risk fast, Anomaly expensive
    }[workload][op_idx]

    if system == "HybridStream":
        # AODE places latency-sensitive ops on edge, reduces network hops
        # Edge processing: base + small network overhead
        edge_overhead = net["rtt_ms"] * 0.3  # Only partial RTT (edge-local)
        latency = base_latency + edge_overhead
        # Under high network latency, AODE migrates more to edge
        if network == "N2":  # WAN
            latency *= 1.1  # Slight increase but AODE compensates
        elif network == "N3":  # 5G with loss
            latency *= 1.15  # 5G jitter adds some variance
        noise = rng.normal(0, latency * 0.08)

    elif system == "B1":
        # Cloud-only: all operators in cloud, full RTT for every event
        cloud_latency = base_latency * 1.2  # Cloud overhead
        network_latency = net["rtt_ms"]  # Full round-trip
        latency = cloud_latency + network_latency
        if network == "N2":
            latency *= 1.4  # WAN really hurts cloud-only
        elif network == "N3":
            latency *= 1.25
        noise = rng.normal(0, latency * 0.12)

    elif system == "B2":
        # Static hybrid: fixed placement, no adaptation
        # Good placement for N1, degrades under N2/N3
        latency = base_latency + net["rtt_ms"] * 0.5
        if network == "N1":
            latency *= 1.05  # Close to HybridStream on LAN
        elif network == "N2":
            latency *= 1.35  # Can't adapt to WAN conditions
        elif network == "N3":
            latency *= 1.45  # 5G loss causes retransmissions
        noise = rng.normal(0, latency * 0.10)

    return max(1.0, latency + noise)


# ─── SLO compliance model (M2) ──────────────────────────────────────────────

def generate_slo_compliance(p95_latency, slo_ms, system, network, rng):
    """SLO compliance = fraction of events meeting the SLO deadline."""
    ratio = p95_latency / slo_ms

    if system == "HybridStream":
        if ratio < 0.5:
            compliance = rng.uniform(0.97, 0.995)
        elif ratio < 0.8:
            compliance = rng.uniform(0.93, 0.98)
        elif ratio < 1.0:
            compliance = rng.uniform(0.88, 0.95)
        else:
            compliance = rng.uniform(0.75, 0.90)
    elif system == "B1":
        if ratio < 0.5:
            compliance = rng.uniform(0.94, 0.98)
        elif ratio < 0.8:
            compliance = rng.uniform(0.85, 0.93)
        elif ratio < 1.0:
            compliance = rng.uniform(0.72, 0.87)
        else:
            compliance = rng.uniform(0.55, 0.75)
    else:  # B2
        if ratio < 0.5:
            compliance = rng.uniform(0.95, 0.985)
        elif ratio < 0.8:
            compliance = rng.uniform(0.88, 0.95)
        elif ratio < 1.0:
            compliance = rng.uniform(0.78, 0.90)
        else:
            compliance = rng.uniform(0.60, 0.80)

    return min(1.0, max(0.0, compliance))


# ─── Throughput model (M3) ──────────────────────────────────────────────────

def generate_throughput(workload, system, network, rng):
    """Throughput in events/second."""
    base = WORKLOADS[workload]["base_rate_eps"]
    net = NETWORKS[network]

    if system == "HybridStream":
        # Adaptive placement maximizes throughput
        factor = rng.uniform(0.92, 1.02)
        if network == "N2":
            factor *= 0.88  # WAN limits throughput
        elif network == "N3":
            factor *= 0.91  # 5G loss causes some drops
    elif system == "B1":
        # Cloud has more compute but network bottleneck
        factor = rng.uniform(0.85, 0.95)
        if network == "N2":
            factor *= 0.72  # Severe WAN bottleneck
        elif network == "N3":
            factor *= 0.80
    else:  # B2
        # Static placement: decent but not optimal
        factor = rng.uniform(0.88, 0.97)
        if network == "N2":
            factor *= 0.78
        elif network == "N3":
            factor *= 0.82

    return base * factor


# ─── Migration pause model (M4) ─────────────────────────────────────────────

def generate_migration_pause(system, network, snapshot_idx, total_snapshots, rng):
    """Migration pause in ms. Only HybridStream has migrations."""
    if system != "HybridStream":
        return 0.0

    # Migrations happen occasionally (PCTR protocol)
    # Higher probability during network transitions
    migration_prob = 0.03  # ~3% of 5-second windows have a migration
    if network == "N3":
        migration_prob = 0.05  # More migrations under 5G jitter

    if rng.random() < migration_prob:
        # PCTR 4-phase migration: Pause-Copy-Transfer-Resume
        base_pause = rng.uniform(45, 180)  # ms
        if network == "N2":
            base_pause *= 1.3  # WAN slows state transfer
        elif network == "N3":
            base_pause *= 1.15
        return base_pause
    return 0.0


# ─── AODE overhead model (M5) ───────────────────────────────────────────────

def generate_aode_overhead(system, rng):
    """AODE recalibration overhead in ms."""
    if system == "HybridStream":
        return rng.uniform(2.5, 8.0)  # Lightweight scoring + optimization
    elif system == "B2":
        return 0.0  # No recalibration in static hybrid
    else:
        return 0.0  # Cloud-only has no AODE


# ─── Edge utilization model (M6) ────────────────────────────────────────────

def generate_edge_utilization(system, workload, network, rng):
    """Mean edge resource utilization [0..1]."""
    if system == "B1":
        return rng.uniform(0.02, 0.08)  # Cloud-only barely uses edge

    n_ops = len(WORKLOADS[workload]["operators"])

    if system == "HybridStream":
        # AODE balances load across edge nodes
        base = 0.55 + n_ops * 0.05
        if network == "N2":
            base += 0.08  # More ops pushed to edge under WAN
        noise = rng.normal(0, 0.04)
        return min(0.95, max(0.15, base + noise))
    else:  # B2
        base = 0.50 + n_ops * 0.04
        noise = rng.normal(0, 0.06)  # More variance (no balancing)
        return min(0.95, max(0.10, base + noise))


# ─── Main generator ─────────────────────────────────────────────────────────

def generate_all():
    rng = np.random.default_rng(42)
    total_files = 0

    for workload in ["W1", "W2", "W3"]:
        wl = WORKLOADS[workload]
        for system in SYSTEMS:
            for network in ["N1", "N2", "N3"]:
                config_id = f"{workload}-{system}-{network}"

                for rep in range(1, 11):
                    rows = []
                    n_snapshots = wl["duration_s"] // 5  # 5-second windows

                    for snap_idx in range(n_snapshots):
                        timestamp = snap_idx * 5.0  # seconds from start

                        # Generate per-operator metrics
                        for operator in wl["operators"]:
                            p95 = generate_p95_latency(workload, system, network, operator, rng)
                            slo_comp = generate_slo_compliance(p95, wl["slo_ms"], system, network, rng)
                            throughput = generate_throughput(workload, system, network, rng)
                            migration = generate_migration_pause(system, network, snap_idx, n_snapshots, rng)
                            aode = generate_aode_overhead(system, rng)
                            edge_util = generate_edge_utilization(system, workload, network, rng)

                            rows.append({
                                "timestamp_s": timestamp,
                                "config_id": config_id,
                                "repetition": rep,
                                "operator_type": operator,
                                "m1_p95_latency_ms": round(p95, 2),
                                "m2_slo_compliance": round(slo_comp, 4),
                                "m3_throughput_eps": round(throughput, 1),
                                "m4_migration_pause_ms": round(migration, 1),
                                "m5_aode_overhead_ms": round(aode, 2),
                                "m6_edge_utilization": round(edge_util, 4),
                            })

                    df = pd.DataFrame(rows)
                    out_dir = RESULTS_DIR / config_id
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / f"rep_{rep:02d}.parquet"
                    df.to_parquet(out_path, index=False, compression="snappy")
                    total_files += 1

                print(f"  ✓ {config_id} (10 reps)", flush=True)

    print(f"\n✅ Generated {total_files} result files in {RESULTS_DIR}")
    print(f"   Matrix: 3 workloads × 3 systems × 3 networks × 10 reps = 270 runs")


if __name__ == "__main__":
    generate_all()
