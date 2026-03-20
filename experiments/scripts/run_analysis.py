#!/usr/bin/env python3
"""Run full analysis pipeline: load results → stats → figures → tables."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("analysis")

from experiments.metrics.storage import load_all_results
from experiments.analysis.stats import run_all_pairwise_comparisons, summarize_m4_migration_pauses
from experiments.analysis.plots import generate_all_figures
from experiments.analysis.tables import generate_all_tables

def main():
    log.info("Loading results...")
    df = load_all_results()
    log.info("Loaded %d rows | %d unique configs | %d systems",
             len(df), df["config_id"].nunique(), df["system"].nunique())

    # Quick summary
    print("\n📊 EXPERIMENT SUMMARY")
    print("=" * 60)
    for workload in ["W1", "W2", "W3"]:
        print(f"\n{'─'*60}")
        print(f"  {workload}")
        print(f"{'─'*60}")
        for network in ["N1", "N2", "N3"]:
            print(f"\n  Network: {network}")
            for system in ["HybridStream", "B1", "B2"]:
                mask = (df["workload"] == workload) & (df["network"] == network) & (df["system"] == system)
                subset = df[mask]
                if len(subset) == 0:
                    continue
                m1 = subset["m1_p95_latency_ms"].median()
                m2 = subset["m2_slo_compliance"].mean() * 100
                m3 = subset["m3_throughput_eps"].median() / 1000
                print(f"    {system:15s}  p95={m1:6.1f}ms  SLO={m2:5.1f}%  throughput={m3:6.1f}k eps")

    # Statistical tests
    log.info("Running Wilcoxon signed-rank tests...")
    comparisons = run_all_pairwise_comparisons(df)
    sig_count = sum(1 for c in comparisons if c.significant)
    print(f"\n📈 STATISTICAL TESTS: {sig_count}/{len(comparisons)} significant (Bonferroni-corrected)")

    # Show key results
    print("\n  Key comparisons (HybridStream vs baselines):")
    for c in comparisons:
        if c.significant and "m1_p95_latency_ms" in c.metric:
            pct = abs(c.median_diff / c.median_b) * 100 if c.median_b != 0 else 0
            direction = "lower" if c.median_diff < 0 else "higher"
            print(f"    {c.group_a_label} vs {c.group_b_label}: "
                  f"{pct:.1f}% {direction} latency (p={c.bonferroni_p:.4f}, r={c.effect_size_r:.3f})")

    # Migration pauses
    log.info("Analyzing migration pauses...")
    pause_summary = summarize_m4_migration_pauses(df)
    print(f"\n🔄 MIGRATION PAUSES (M4):")
    for _, row in pause_summary.iterrows():
        print(f"    {row['metric']:12s}: {row['value']:.1f}" if row['value'] is not None else f"    {row['metric']:12s}: N/A")

    # Generate figures
    log.info("Generating figures...")
    figures = generate_all_figures(df)
    print(f"\n📉 FIGURES: {len(figures)} generated")
    for f in figures:
        print(f"    {f.name}")

    # Generate tables
    log.info("Generating tables...")
    tables = generate_all_tables(df)
    print(f"\n📋 TABLES: {len(tables)} generated")
    for t in tables:
        print(f"    {t.name}")

    print(f"\n✅ Analysis complete! Results in experiments/results/")


if __name__ == "__main__":
    main()
