from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd
from .collector import MetricSnapshot

log = logging.getLogger(__name__)
RESULTS_DIR = Path(__file__).parent.parent / "results"


def save_snapshots(snapshots: list[MetricSnapshot], config_id: str, repetition: int) -> Path | None:
    if not snapshots:
        log.warning("No snapshots to save for %s rep %d", config_id, repetition)
        return None

    output_dir = RESULTS_DIR / config_id
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for snap in snapshots:
        all_op_types = set(snap.m1_p95_latency_ms) | set(snap.m2_slo_compliance)
        if not all_op_types:
            rows.append({
                "timestamp_s": snap.timestamp, "config_id": snap.config_id,
                "repetition": snap.repetition, "operator_type": "_global",
                "m1_p95_latency_ms": None, "m2_slo_compliance": None,
                "m3_throughput_eps": snap.m3_throughput_eps,
                "m4_migration_pause_ms": snap.m4_migration_pause_ms,
                "m5_aode_overhead_ms": snap.m5_aode_overhead_ms,
                "m6_edge_utilization": snap.m6_edge_utilization,
            })
        else:
            for op_type in all_op_types:
                rows.append({
                    "timestamp_s": snap.timestamp, "config_id": snap.config_id,
                    "repetition": snap.repetition, "operator_type": op_type,
                    "m1_p95_latency_ms": snap.m1_p95_latency_ms.get(op_type),
                    "m2_slo_compliance": snap.m2_slo_compliance.get(op_type),
                    "m3_throughput_eps": snap.m3_throughput_eps,
                    "m4_migration_pause_ms": snap.m4_migration_pause_ms,
                    "m5_aode_overhead_ms": snap.m5_aode_overhead_ms,
                    "m6_edge_utilization": snap.m6_edge_utilization,
                })

    df = pd.DataFrame(rows)
    out_path = output_dir / f"rep_{repetition:02d}.parquet"
    df.to_parquet(out_path, index=False, compression="snappy")
    log.info("Saved %d rows to %s", len(rows), out_path)
    return out_path


def load_all_results() -> pd.DataFrame:
    all_dfs = [pd.read_parquet(f) for f in RESULTS_DIR.rglob("*.parquet")]
    if not all_dfs:
        raise FileNotFoundError(f"No results found in {RESULTS_DIR}")

    combined = pd.concat(all_dfs, ignore_index=True)
    parsed = combined["config_id"].str.split("-", n=2, expand=True)
    if parsed.shape[1] < 3:
        raise ValueError("config_id must have format 'workload-system-network'")
    combined["workload"] = parsed[0]
    combined["system"]   = parsed[1]
    combined["network"]  = parsed[2]
    combined = combined[combined["timestamp_s"] >= 120].copy()  # Skip warmup period (120s)

    log.info("Loaded %d rows from %d result files", len(combined), len(all_dfs))
    return combined
