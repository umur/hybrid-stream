from __future__ import annotations
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

log = logging.getLogger(__name__)
FIGURES_DIR = Path(__file__).parent.parent / "results" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif", "font.size": 10,
    "axes.labelsize": 10, "axes.titlesize": 10,
    "xtick.labelsize": 9, "ytick.labelsize": 9,
    "legend.fontsize": 9, "figure.dpi": 300,
    "savefig.dpi": 300, "savefig.bbox": "tight",
})

SYSTEM_COLORS = {"HybridStream": "#1f77b4", "B1": "#ff7f0e", "B2": "#2ca02c"}
SYSTEM_LABELS = {"HybridStream": "HybridStream", "B1": "B1 (Cloud-Only)", "B2": "B2 (Static Hybrid)"}


def plot_latency_cdf(df: pd.DataFrame, workload: str, network: str) -> Path:
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    for system in ["HybridStream", "B1", "B2"]:
        mask = ((df["workload"] == workload) & (df["network"] == network) &
                (df["system"] == system) & df["m1_p95_latency_ms"].notna())
        values = df[mask]["m1_p95_latency_ms"].values
        if len(values) == 0:
            continue
        sorted_v = np.sort(values)
        cdf = np.arange(1, len(sorted_v) + 1) / len(sorted_v)
        ax.plot(sorted_v, cdf, label=SYSTEM_LABELS[system], color=SYSTEM_COLORS[system], linewidth=1.5)

    ax.set_xlabel("p95 Latency (ms)"); ax.set_ylabel("CDF")
    ax.set_title(f"{workload} — {network}"); ax.legend(frameon=False)
    ax.grid(True, alpha=0.3, linewidth=0.5)

    out = FIGURES_DIR / f"latency_cdf_{workload}_{network}.pdf"
    fig.savefig(out); plt.close(fig)
    return out


def plot_slo_compliance_bar(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.8), sharey=True)
    networks = ["N1", "N2", "N3"]; x = np.arange(len(networks)); bw = 0.25

    for ax, workload in zip(axes, ["W1", "W2", "W3"]):
        for i, system in enumerate(["HybridStream", "B1", "B2"]):
            means = []
            for network in networks:
                mask = ((df["workload"] == workload) & (df["network"] == network) &
                        (df["system"] == system) & df["m2_slo_compliance"].notna())
                vals = df[mask]["m2_slo_compliance"].values
                means.append(vals.mean() * 100 if len(vals) > 0 else 0)
            ax.bar(x + i * bw, means, width=bw, label=SYSTEM_LABELS[system],
                   color=SYSTEM_COLORS[system], alpha=0.85)

        ax.set_xticks(x + bw); ax.set_xticklabels(networks); ax.set_title(workload)
        ax.set_ylim(0, 105); ax.yaxis.set_major_formatter(ticker.PercentFormatter())
        ax.grid(True, axis="y", alpha=0.3)

    axes[0].set_ylabel("SLO Compliance (%)")
    axes[1].legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.3))

    out = FIGURES_DIR / "slo_compliance_bar.pdf"
    fig.savefig(out); plt.close(fig)
    return out


def plot_throughput_boxplot(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.8))
    for ax, workload in zip(axes, ["W1", "W2", "W3"]):
        data, colors = [], []
        for system in ["HybridStream", "B1", "B2"]:
            mask = (df["workload"] == workload) & (df["system"] == system) & df["m3_throughput_eps"].notna()
            data.append(df[mask]["m3_throughput_eps"].values / 1e6)
            colors.append(SYSTEM_COLORS[system])
        bp = ax.boxplot(data, patch_artist=True, widths=0.5, notch=True,
                        medianprops={"color": "black", "linewidth": 2})
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color); patch.set_alpha(0.7)
        ax.set_xticklabels(["HS", "B1", "B2"]); ax.set_title(workload)
        ax.set_ylabel("Throughput (M ev/s)" if workload == "W1" else "")
        ax.grid(True, axis="y", alpha=0.3)

    out = FIGURES_DIR / "throughput_boxplot.pdf"
    fig.savefig(out); plt.close(fig)
    return out


def plot_migration_pause_distribution(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    pauses = df[(df["system"] == "HybridStream") & (df["m4_migration_pause_ms"] > 0)]["m4_migration_pause_ms"]
    if len(pauses) > 0:
        ax.hist(pauses, bins=30, color=SYSTEM_COLORS["HybridStream"], alpha=0.8, edgecolor="white")
        ax.axvline(pauses.median(), color="red", linestyle="--", linewidth=1.5, label=f"Median: {pauses.median():.0f}ms")
        ax.axvline(pauses.quantile(0.95), color="orange", linestyle="--", linewidth=1.5,
                   label=f"p95: {pauses.quantile(0.95):.0f}ms")
        ax.legend(frameon=False)
    else:
        ax.text(0.5, 0.5, "No migration data", transform=ax.transAxes, ha="center")
    ax.set_xlabel("Migration Pause Duration (ms)"); ax.set_ylabel("Count")
    ax.set_title("PCTR Migration Pause Distribution (M4)")

    out = FIGURES_DIR / "migration_pause_dist.pdf"
    fig.savefig(out); plt.close(fig)
    return out


def generate_all_figures(df: pd.DataFrame) -> list[Path]:
    paths = []
    for workload in ["W1", "W2", "W3"]:
        for network in ["N1", "N2", "N3"]:
            paths.append(plot_latency_cdf(df, workload, network))
    paths.append(plot_slo_compliance_bar(df))
    paths.append(plot_throughput_boxplot(df))
    paths.append(plot_migration_pause_distribution(df))
    log.info("Generated %d figures", len(paths))
    return paths
