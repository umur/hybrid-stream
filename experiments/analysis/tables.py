from __future__ import annotations
import logging
from pathlib import Path
from .stats import ComparisonResult

log = logging.getLogger(__name__)
TABLES_DIR = Path(__file__).parent.parent / "results" / "tables"
TABLES_DIR.mkdir(parents=True, exist_ok=True)


def generate_comparison_table_latex(results: list[ComparisonResult]) -> str:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Pairwise statistical comparisons (Wilcoxon signed-rank, Bonferroni-corrected). "
        r"Significant results ($p_{\text{Bonf.}} < 0.05$) shown in bold.}",
        r"\label{tab:statistical_comparisons}",
        r"\small",
        r"\begin{tabular}{lllrrrrr}",
        r"\toprule",
        r"Workload & Network & Comparison & Metric & Median A & Median B & $p_{\text{Bonf.}}$ & $r$ \\",
        r"\midrule",
    ]

    METRIC_SHORT = {
        "m1_p95_latency_ms": "M1 (p95 ms)",
        "m2_slo_compliance": "M2 (SLO %)",
        "m3_throughput_eps": "M3 (ev/s)",
    }

    for r in results:
        parts_a  = r.group_a_label.split("/")
        workload = parts_a[0] if len(parts_a) > 0 else ""
        network  = parts_a[1] if len(parts_a) > 1 else ""
        sys_a    = parts_a[2] if len(parts_a) > 2 else r.group_a_label
        sys_b    = r.group_b_label.split("/")[-1] if "/" in r.group_b_label else r.group_b_label
        metric   = METRIC_SHORT.get(r.metric, r.metric)

        row = (
            f"{workload} & {network} & {sys_a} vs {sys_b} & "
            f"{metric} & {r.median_a:.2f} & {r.median_b:.2f} & "
            f"{r.bonferroni_p:.4f} & {r.effect_size_r:.3f}"
        )
        if r.significant:
            row = r"\textbf{" + row + r"}"
        lines.append(row + r" \\")

    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def save_comparison_table(results: list[ComparisonResult]) -> Path:
    latex    = generate_comparison_table_latex(results)
    out_path = TABLES_DIR / "comparison_table.tex"
    out_path.write_text(latex)
    log.info("Saved LaTeX table: %s", out_path)
    return out_path


def generate_summary_table(df) -> Path:
    """Generate a summary table with median M1–M6 per config."""
    import pandas as pd

    rows = []
    for workload in ["W1", "W2", "W3"]:
        for network in ["N1", "N2", "N3"]:
            for system in ["HybridStream", "B1", "B2"]:
                mask = (df["workload"] == workload) & (df["network"] == network) & (df["system"] == system)
                subset = df[mask]
                if len(subset) == 0:
                    continue
                rows.append({
                    "Workload": workload, "Network": network, "System": system,
                    "M1 p95 (ms)": f"{subset['m1_p95_latency_ms'].median():.1f}",
                    "M2 SLO (%)": f"{subset['m2_slo_compliance'].mean()*100:.1f}",
                    "M3 Throughput (k)": f"{subset['m3_throughput_eps'].median()/1000:.1f}",
                    "M4 Pause (ms)": f"{subset['m4_migration_pause_ms'][subset['m4_migration_pause_ms']>0].median():.0f}" if (subset['m4_migration_pause_ms']>0).any() else "—",
                    "M5 AODE (ms)": f"{subset['m5_aode_overhead_ms'].mean():.1f}",
                    "M6 Edge Util": f"{subset['m6_edge_utilization'].mean():.2f}",
                })

    summary = pd.DataFrame(rows)
    out_path = TABLES_DIR / "summary_table.csv"
    summary.to_csv(out_path, index=False)

    # Also generate LaTeX
    latex_lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{Median metrics across all experimental configurations (10 repetitions each).}",
        r"\label{tab:summary_results}",
        r"\small",
        r"\begin{tabular}{lll|rrrrrr}",
        r"\toprule",
        r"W & Net & System & M1 p95 (ms) & M2 SLO (\%) & M3 (k ev/s) & M4 Pause (ms) & M5 AODE (ms) & M6 Edge \\",
        r"\midrule",
    ]
    for _, row in summary.iterrows():
        line = f"{row['Workload']} & {row['Network']} & {row['System']} & "
        line += f"{row['M1 p95 (ms)']} & {row['M2 SLO (%)']} & {row['M3 Throughput (k)']} & "
        line += f"{row['M4 Pause (ms)']} & {row['M5 AODE (ms)']} & {row['M6 Edge Util']}"
        latex_lines.append(line + r" \\")
    latex_lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]

    tex_path = TABLES_DIR / "summary_table.tex"
    tex_path.write_text("\n".join(latex_lines))
    log.info("Saved summary table: %s", out_path)
    return out_path


def generate_all_tables(df) -> list:
    """Generate all publication tables."""
    from .stats import run_all_pairwise_comparisons
    comparisons = run_all_pairwise_comparisons(df)
    paths = [
        save_comparison_table(comparisons),
        generate_summary_table(df),
    ]
    return paths
