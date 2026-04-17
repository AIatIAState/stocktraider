#!/usr/bin/env python3
"""
Generate comparative evaluation charts across multiple LLM models.

Usage:
  python generate_comparison.py batch_4omini.json batch_41mini.json batch_41nano.json -o charts/comparison/
"""

import argparse
import json
import os
import statistics

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
})

MODEL_COLORS = [
    "#3498db",  # blue
    "#e74c3c",  # red
    "#2ecc71",  # green
    "#f39c12",  # amber
    "#9b59b6",  # purple
    "#1abc9c",  # teal
    "#e67e22",  # orange
    "#34495e",  # dark grey
]

CUSTOM_METRIC_KEYS = [
    "symbol_accuracy",
    "symbol_coverage",
    "hedge_language",
]

RAGAS_KEYS = ["faithfulness", "answer_relevancy"]

METRIC_LABELS = {
    "symbol_accuracy": "Symbol\nAccuracy",
    "symbol_coverage": "Symbol\nCoverage",
    "hedge_language": "Hedge\nLanguage",
    "faithfulness": "RAGAS\nFaithfulness",
    "answer_relevancy": "RAGAS\nRelevancy",
}

ALL_KEYS = CUSTOM_METRIC_KEYS + RAGAS_KEYS


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_model_name(report: dict) -> str:
    """Get model name from report metadata or first successful trial."""
    meta = report.get("metadata", {})
    if meta.get("model_override"):
        return meta["model_override"]
    for week in report.get("weeks", []):
        for trial in week.get("trial_results", []):
            if "error" not in trial and trial.get("model"):
                return trial["model"]
    return "unknown"


def extract_overall_stats(report: dict) -> dict:
    """Compute overall mean and stdev for each metric across all weeks."""
    weeks = report.get("weeks", [])
    per_metric: dict[str, list[float]] = {k: [] for k in ALL_KEYS}

    for w in weeks:
        agg = w.get("aggregate", {})
        for k in CUSTOM_METRIC_KEYS:
            val = agg.get(k, {}).get("mean")
            if val is not None:
                per_metric[k].append(val)
        ragas = agg.get("ragas", {})
        for k in RAGAS_KEYS:
            val = ragas.get(k, {}).get("mean")
            if val is not None:
                per_metric[k].append(val)

    result = {}
    for k, vals in per_metric.items():
        if vals:
            result[k] = {
                "mean": statistics.mean(vals),
                "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            }
        else:
            result[k] = {"mean": 0.0, "stdev": 0.0}
    return result


def extract_all_trial_scores(report: dict) -> dict[str, list[float]]:
    """Collect individual trial scores for each metric (for box plots)."""
    per_metric: dict[str, list[float]] = {k: [] for k in ALL_KEYS}

    for w in report.get("weeks", []):
        for trial in w.get("trial_results", []):
            if "error" in trial:
                continue
            for k in CUSTOM_METRIC_KEYS:
                score = trial.get("metrics", {}).get(k, {}).get("score")
                if score is not None:
                    per_metric[k].append(score)
            ragas = trial.get("ragas_metrics", {})
            if "error" not in ragas:
                overall = ragas.get("overall", {})
                for k in RAGAS_KEYS:
                    val = overall.get(k)
                    if val is not None:
                        per_metric[k].append(val)

    return per_metric


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def chart_grouped_bars(models: list[str], stats: list[dict], out_dir: str):
    """Grouped bar chart: all metrics, one bar per model, with error bars."""
    n_models = len(models)
    n_metrics = len(ALL_KEYS)
    x = np.arange(n_metrics)
    width = 0.8 / n_models

    fig, ax = plt.subplots(figsize=(max(10, n_metrics * 1.8), 5.5))

    for i, (model, stat) in enumerate(zip(models, stats)):
        means = [stat[k]["mean"] for k in ALL_KEYS]
        stdevs = [stat[k]["stdev"] for k in ALL_KEYS]
        offset = (i - n_models / 2 + 0.5) * width
        color = MODEL_COLORS[i % len(MODEL_COLORS)]
        bars = ax.bar(x + offset, means, width * 0.9, yerr=stdevs, capsize=3,
                      label=model, color=color, alpha=0.85, edgecolor="white",
                      linewidth=0.8, error_kw={"linewidth": 1})

    ax.set_xticks(x)
    ax.set_xticklabels([METRIC_LABELS[k] for k in ALL_KEYS], fontsize=9)
    ax.set_ylim(0, 1.15)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_ylabel("Score")
    ax.set_title(f"LLM Model Comparison — {n_models} Models Across {n_metrics} Metrics")
    ax.legend(loc="lower right", fontsize=8, ncol=2)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "comparison_bars.png"), dpi=180)
    plt.close(fig)
    print("  comparison_bars.png")


def chart_radar(models: list[str], stats: list[dict], out_dir: str):
    """Radar/spider chart: metric profile overlay per model."""
    labels = [METRIC_LABELS[k].replace("\n", " ") for k in ALL_KEYS]
    n = len(ALL_KEYS)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    for i, (model, stat) in enumerate(zip(models, stats)):
        values = [stat[k]["mean"] for k in ALL_KEYS]
        values += values[:1]
        color = MODEL_COLORS[i % len(MODEL_COLORS)]
        ax.plot(angles, values, "o-", linewidth=2, label=model, color=color,
                markersize=5)
        ax.fill(angles, values, alpha=0.1, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.set_title("Model Metric Profiles", y=1.08)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=9)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "comparison_radar.png"), dpi=180)
    plt.close(fig)
    print("  comparison_radar.png")


def chart_box_plots(models: list[str], trial_data: list[dict], out_dir: str):
    """Box plots: score distributions per model for each metric."""
    n_metrics = len(ALL_KEYS)
    fig, axes = plt.subplots(1, n_metrics, figsize=(n_metrics * 2.5, 5), sharey=True)

    for j, key in enumerate(ALL_KEYS):
        ax = axes[j]
        data = []
        for trial in trial_data:
            scores = trial.get(key, [])
            data.append(scores if scores else [0])

        bp = ax.boxplot(data, labels=[m.replace("gpt-", "") for m in models],
                        patch_artist=True, widths=0.6)
        for k, patch in enumerate(bp["boxes"]):
            patch.set_facecolor(MODEL_COLORS[k % len(MODEL_COLORS)])
            patch.set_alpha(0.6)

        ax.set_title(METRIC_LABELS[key], fontsize=10)
        ax.tick_params(axis="x", rotation=45, labelsize=7)
        if j == 0:
            ax.set_ylabel("Score")
        ax.set_ylim(-0.05, 1.1)
        ax.axhline(y=0.8, color="#95a5a6", linestyle="--", linewidth=0.6, alpha=0.5)

    fig.suptitle("Score Distributions by Model", fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "comparison_boxplots.png"), dpi=180,
                bbox_inches="tight")
    plt.close(fig)
    print("  comparison_boxplots.png")


# ---------------------------------------------------------------------------
# Pricing (per 1M tokens, as of March 2026)
# ---------------------------------------------------------------------------
MODEL_PRICING = {
    "gpt-3.5-turbo":  {"input": 0.50,  "output": 1.50},
    "gpt-4o-mini":    {"input": 0.15,  "output": 0.60},
    "gpt-4.1-mini":   {"input": 0.40,  "output": 1.60},
    "gpt-4.1-nano":   {"input": 0.10,  "output": 0.40},
    "gpt-5.4-mini":   {"input": 0.40,  "output": 1.60},
    "gpt-5.4-nano":   {"input": 0.10,  "output": 0.40},
}


def estimate_model_cost(report: dict, model: str) -> dict | None:
    """Estimate inference cost from trial count and known pricing."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return None

    # Count successful trials
    n_trials = 0
    for w in report.get("weeks", []):
        for t in w.get("trial_results", []):
            if "error" not in t:
                n_trials += 1

    # Estimate tokens per call: ~1000 input (JSON prompt), ~400 output (structured response)
    est_input_tokens = n_trials * 1000
    est_output_tokens = n_trials * 400

    input_cost = est_input_tokens * pricing["input"] / 1e6
    output_cost = est_output_tokens * pricing["output"] / 1e6
    total = input_cost + output_cost

    # Add RAGAS cost if present
    ragas_cost = sum(
        w.get("aggregate", {}).get("ragas_cost", {}).get("total_cost_usd", 0)
        for w in report.get("weeks", [])
    )

    return {
        "inference_cost": total,
        "ragas_cost": ragas_cost,
        "total_cost": total + ragas_cost,
        "n_trials": n_trials,
        "price_per_1k_input": pricing["input"],
        "price_per_1k_output": pricing["output"],
    }


def chart_cost_comparison(models: list[str], costs: list[dict | None], out_dir: str):
    """Stacked bar chart: inference cost vs RAGAS evaluation cost per model."""
    valid = [(m, c) for m, c in zip(models, costs) if c is not None]
    if not valid:
        print("  (skipped cost chart — no pricing data for these models)")
        return

    names = [m for m, _ in valid]
    inference = [c["inference_cost"] for _, c in valid]
    ragas = [c["ragas_cost"] for _, c in valid]
    totals = [c["total_cost"] for _, c in valid]

    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(max(7, len(names) * 1.5), 4.5))

    bars_inf = ax.bar(x, inference, 0.5, label="Model inference (est.)",
                      color="#3498db", edgecolor="white")
    bars_rag = ax.bar(x, ragas, 0.5, bottom=inference, label="RAGAS evaluation",
                      color="#e74c3c", edgecolor="white")

    for i, total in enumerate(totals):
        ax.text(i, total + max(totals) * 0.02, f"${total:.3f}",
                ha="center", va="bottom", fontweight="bold", fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9)
    ax.set_ylabel("Estimated Cost (USD)")
    ax.set_title("Evaluation Cost by Model")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_ylim(0, max(totals) * 1.25)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "comparison_cost.png"), dpi=180)
    plt.close(fig)
    print("  comparison_cost.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate comparative charts from multiple batch reports")
    parser.add_argument("reports", nargs="+", help="Batch report JSON files")
    parser.add_argument("-o", "--output-dir", default="charts/comparison",
                        help="Output directory (default: charts/comparison/)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    models = []
    all_stats = []
    all_trials = []
    all_costs = []
    all_reports = []

    for path in args.reports:
        with open(path) as f:
            report = json.load(f)
        model = extract_model_name(report)
        stats = extract_overall_stats(report)
        trials = extract_all_trial_scores(report)
        cost = estimate_model_cost(report, model)

        models.append(model)
        all_stats.append(stats)
        all_trials.append(trials)
        all_costs.append(cost)
        all_reports.append(report)
        print(f"Loaded {model} from {path}")

    print(f"\nGenerating comparison charts ({len(models)} models) in {args.output_dir}/")
    chart_grouped_bars(models, all_stats, args.output_dir)
    chart_radar(models, all_stats, args.output_dir)
    chart_box_plots(models, all_trials, args.output_dir)
    chart_cost_comparison(models, all_costs, args.output_dir)

    # Print summary table
    print(f"\n{'Model':<20}", end="")
    for k in ALL_KEYS:
        print(f" {METRIC_LABELS[k].replace(chr(10), ' '):>12}", end="")
    print()
    print("-" * (20 + 13 * len(ALL_KEYS)))
    for model, stat in zip(models, all_stats):
        print(f"{model:<20}", end="")
        for k in ALL_KEYS:
            m = stat[k]["mean"]
            s = stat[k]["stdev"]
            print(f" {m:>5.1%} ±{s:.1%}", end="")
        print()

    print("\nDone.")


if __name__ == "__main__":
    main()
