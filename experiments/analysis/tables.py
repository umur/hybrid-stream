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
