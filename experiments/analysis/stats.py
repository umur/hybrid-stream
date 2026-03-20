from __future__ import annotations
import logging
import warnings
from dataclasses import dataclass
import numpy as np
import pandas as pd
import scipy.stats as stats

log = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    metric:           str
    group_a_label:    str
    group_b_label:    str
    n_a:              int
    n_b:              int
    median_a:         float
    median_b:         float
    median_diff:      float
    wilcoxon_stat:    float
    wilcoxon_p:       float
    bonferroni_p:     float
    significant:      bool
    effect_size_r:    float
    effect_magnitude: str
    bootstrap_ci_lo:  float
    bootstrap_ci_hi:  float


def wilcoxon_comparison(
    group_a: np.ndarray,
    group_b: np.ndarray,
    metric: str,
    label_a: str,
    label_b: str,
    n_comparisons: int = 1,
    n_bootstrap:   int = 9999,
    alpha:         float = 0.05,
) -> ComparisonResult:
    """
    Wilcoxon signed-rank test with Bonferroni correction and bootstrap CI.
    Rationale: latency distributions are right-skewed (§6.5).
    """
    assert len(group_a) == len(group_b), "Groups must be matched"
    n = len(group_a)

    diffs_check = group_a - group_b
    if np.all(diffs_check == 0):
        return ComparisonResult(
            metric=metric, group_a_label=label_a, group_b_label=label_b,
            n_a=n, n_b=n,
            median_a=float(np.median(group_a)), median_b=float(np.median(group_b)),
            median_diff=0.0, wilcoxon_stat=0.0, wilcoxon_p=1.0,
            bonferroni_p=1.0, significant=False,
            effect_size_r=0.0, effect_magnitude="small",
            bootstrap_ci_lo=0.0, bootstrap_ci_hi=0.0,
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stat, p_value = stats.wilcoxon(group_a, group_b, alternative="two-sided")

    p_bonferroni = min(p_value * n_comparisons, 1.0)

    n_pairs = n * (n + 1) / 2
    r = float(1 - (2 * stat / n_pairs)) if n_pairs > 0 else 0.0
    r = max(-1.0, min(1.0, r))

    abs_r = abs(r)
    magnitude = "small" if abs_r < 0.3 else "medium" if abs_r < 0.5 else "large"

    rng = np.random.default_rng(42)
    diffs = group_a - group_b
    boot_medians = [np.median(rng.choice(diffs, size=n, replace=True)) for _ in range(n_bootstrap)]
    ci_lo, ci_hi = np.percentile(boot_medians, [2.5, 97.5])

    return ComparisonResult(
        metric=metric, group_a_label=label_a, group_b_label=label_b,
        n_a=n, n_b=n,
        median_a=float(np.median(group_a)), median_b=float(np.median(group_b)),
        median_diff=float(np.median(group_a) - np.median(group_b)),
        wilcoxon_stat=float(stat), wilcoxon_p=float(p_value),
        bonferroni_p=float(p_bonferroni), significant=bool(p_bonferroni < alpha),
        effect_size_r=r, effect_magnitude=magnitude,
        bootstrap_ci_lo=float(ci_lo), bootstrap_ci_hi=float(ci_hi),
    )


def run_all_pairwise_comparisons(df: pd.DataFrame) -> list[ComparisonResult]:
    """54 pairwise comparisons: 3 workloads × 3 networks × 2 pairs × 3 metrics."""
    results = []
    n_total = 54

    for workload in ["W1", "W2", "W3"]:
        for network in ["N1", "N2", "N3"]:
            def get_reps(system: str, metric: str) -> np.ndarray:
                mask = ((df["workload"] == workload) & (df["network"] == network) & (df["system"] == system))
                return np.array(df[mask].groupby("repetition")[metric].mean().values)

            for metric in ["m1_p95_latency_ms", "m2_slo_compliance", "m3_throughput_eps"]:
                hs = get_reps("HybridStream", metric)
                b1 = get_reps("B1", metric)
                b2 = get_reps("B2", metric)

                if len(hs) == len(b1) == len(b2) == 10:
                    prefix = f"{workload}/{network}"
                    results.append(wilcoxon_comparison(hs, b1, metric, f"{prefix}/HybridStream", f"{prefix}/B1", n_total))
                    results.append(wilcoxon_comparison(hs, b2, metric, f"{prefix}/HybridStream", f"{prefix}/B2", n_total))

    log.info("Ran %d comparisons (%d significant)", len(results), sum(1 for r in results if r.significant))
    return results


def summarize_m4_migration_pauses(df: pd.DataFrame) -> pd.DataFrame:
    pauses = df[df["m4_migration_pause_ms"] > 0]["m4_migration_pause_ms"]
    return pd.DataFrame({
        "metric": ["count", "min_ms", "median_ms", "p95_ms", "max_ms", "mean_ms"],
        "value": [
            len(pauses),
            pauses.min() if len(pauses) > 0 else None,
            pauses.median() if len(pauses) > 0 else None,
            pauses.quantile(0.95) if len(pauses) > 0 else None,
            pauses.max() if len(pauses) > 0 else None,
            pauses.mean() if len(pauses) > 0 else None,
        ]
    })
