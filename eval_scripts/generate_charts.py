#!/usr/bin/env python3
"""
Generate evaluation charts from single-week or batch report JSON files.

Usage:
  python generate_charts.py report.json                    # single-week report
  python generate_charts.py batch_report.json              # batch report (auto-detected)
  python generate_charts.py batch_report.json -o figures/  # custom output dir
"""

import argparse
import json
import os
import statistics

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.patches import Patch

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

PALETTE = {
    "green": "#2ecc71",
    "amber": "#f39c12",
    "red": "#e74c3c",
    "blue": "#3498db",
    "purple": "#9b59b6",
    "grey": "#95a5a6",
}

METRIC_LABELS = {
    "symbol_accuracy": "Symbol\nAccuracy",
    "symbol_coverage": "Symbol\nCoverage",
    "numerical_faithfulness": "Numerical\nFaithfulness",
    "hedge_language": "Hedge\nLanguage",
    "output_completeness": "Output\nCompleteness",
}

METRIC_KEYS = list(METRIC_LABELS.keys())


def _score_color(score: float) -> str:
    if score >= 0.8:
        return PALETTE["green"]
    if score >= 0.5:
        return PALETTE["amber"]
    return PALETTE["red"]


# ═══════════════════════════════════════════════════════════════════════════
# Single-week charts
# ═══════════════════════════════════════════════════════════════════════════

def chart_metric_overview(cm: dict, meta: dict, out_dir: str):
    metrics = {METRIC_LABELS[k]: cm[k]["score"] for k in METRIC_KEYS}
    labels = list(metrics.keys())
    values = list(metrics.values())
    colors = [_score_color(v) for v in values]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(labels, values, color=colors, width=0.55, edgecolor="white", linewidth=1.2)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.1%}", ha="center", va="bottom", fontweight="bold", fontsize=12)

    ax.set_ylim(0, 1.15)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_ylabel("Score")
    ax.set_title(f"LLM Evaluation — Custom Metrics\n{meta.get('model', '?')}  |  {meta.get('date_range', '?')}")
    ax.axhline(y=0.8, color=PALETTE["grey"], linestyle="--", linewidth=0.8, label="80% threshold")
    ax.legend(loc="lower right", fontsize=9)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "metric_overview.png"), dpi=180)
    plt.close(fig)
    print("  metric_overview.png")


def chart_symbol_accuracy(cm: dict, out_dir: str):
    acc = cm["symbol_accuracy"]
    matched = acc.get("matched", [])
    unmatched = acc.get("unmatched", [])

    if not matched and not unmatched:
        return

    fig, ax = plt.subplots(figsize=(5, 4))
    sizes = [len(matched), len(unmatched)]
    labels = [f"Matched ({len(matched)})", f"Unmatched ({len(unmatched)})"]
    colors = [PALETTE["green"], PALETTE["red"]]

    nonzero = [(s, l, c) for s, l, c in zip(sizes, labels, colors) if s > 0]
    sizes, labels, colors = zip(*nonzero) if nonzero else (sizes, labels, colors)

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, autopct="%1.0f%%",
        startangle=90, textprops={"fontsize": 11},
    )
    for t in autotexts:
        t.set_fontweight("bold")
    ax.set_title("Symbol Accuracy Breakdown")

    if unmatched:
        ax.annotate(f"Unmatched: {', '.join(unmatched)}",
                    xy=(0.5, -0.05), xycoords="axes fraction",
                    ha="center", fontsize=9, color=PALETTE["red"])

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "symbol_accuracy.png"), dpi=180)
    plt.close(fig)
    print("  symbol_accuracy.png")


def chart_symbol_coverage(cm: dict, out_dir: str):
    cov = cm["symbol_coverage"]
    mentioned = cov.get("mentioned", [])
    not_mentioned = cov.get("not_mentioned", [])
    total = cov.get("total_context_symbols", len(mentioned) + len(not_mentioned))
    if total == 0:
        return

    all_syms = sorted(mentioned) + sorted(not_mentioned)
    colors = [PALETTE["green"] if s in mentioned else PALETTE["red"] for s in all_syms]

    fig, ax = plt.subplots(figsize=(max(6, len(all_syms) * 0.45), 3.5))
    ax.bar(all_syms, [1] * len(all_syms), color=colors, width=0.6, edgecolor="white")
    ax.set_yticks([])
    ax.set_title(f"Symbol Coverage — {len(mentioned)}/{total} referenced in output")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(handles=[
        Patch(facecolor=PALETTE["green"], label="Mentioned"),
        Patch(facecolor=PALETTE["red"], label="Not mentioned"),
    ], loc="upper right", fontsize=9)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "symbol_coverage.png"), dpi=180)
    plt.close(fig)
    print("  symbol_coverage.png")


def chart_numerical_faithfulness(cm: dict, out_dir: str):
    nf = cm["numerical_faithfulness"]
    details = nf.get("details", [])
    if not details:
        return

    stated = [d["stated_pct"] for d in details]
    matched = [d["matched_in_context"] for d in details]
    colors = [PALETTE["green"] if m else PALETTE["red"] for m in matched]
    labels = [f"{v:g}%" for v in stated]

    fig, ax = plt.subplots(figsize=(max(5, len(details) * 1.2), 4))
    bars = ax.bar(range(len(stated)), stated, color=colors, width=0.5, edgecolor="white")
    ax.set_xticks(range(len(stated)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("% Value Stated")
    ax.set_title(f"Numerical Faithfulness — {nf['matched']}/{nf['total_percentages_stated']} matched (±{nf['tolerance_pct_points']} pp)")

    for bar, m in zip(bars, matched):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(stated) * 0.02,
                "✓" if m else "✗", ha="center", va="bottom", fontsize=14, fontweight="bold")

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "numerical_faithfulness.png"), dpi=180)
    plt.close(fig)
    print("  numerical_faithfulness.png")


def chart_output_completeness(cm: dict, out_dir: str):
    oc = cm["output_completeness"]
    categories = ["Market Insights", "Event Impacts"]
    counts = [oc["market_insights_count"], oc["event_impacts_count"]]
    ranges = [(3, 5), (0, 5)]

    fig, ax = plt.subplots(figsize=(5, 4))
    bar_colors = [PALETTE["green"] if lo <= c <= hi else PALETTE["red"]
                  for c, (lo, hi) in zip(counts, ranges)]
    bars = ax.barh(categories, counts, color=bar_colors, height=0.4, edgecolor="white")
    for bar, count, (lo, hi) in zip(bars, counts, ranges):
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
                f"{count}  (range: {lo}–{hi})", va="center", fontsize=10)
    ax.set_xlim(0, max(counts) + 2)
    ax.set_xlabel("Bullet Count")
    ax.set_title("Output Completeness")

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "output_completeness.png"), dpi=180)
    plt.close(fig)
    print("  output_completeness.png")


# ═══════════════════════════════════════════════════════════════════════════
# Batch charts (multi-week)
# ═══════════════════════════════════════════════════════════════════════════

def batch_chart_metrics_over_time(weeks: list[dict], meta: dict, out_dir: str):
    """Line chart: each metric score across weeks (mean ± stdev if trials > 1)."""
    week_labels = [w["date_range"].split(" to ")[-1] for w in weeks]  # use end date
    week_labels.reverse()
    weeks_ordered = list(reversed(weeks))  # chronological order

    fig, ax = plt.subplots(figsize=(max(8, len(weeks) * 1.5), 5))

    metric_colors = [PALETTE["blue"], PALETTE["purple"], PALETTE["green"],
                     PALETTE["amber"], PALETTE["red"]]

    for i, key in enumerate(METRIC_KEYS):
        means = []
        stdevs = []
        for w in weeks_ordered:
            agg = w["aggregate"][key]
            means.append(agg["mean"])
            stdevs.append(agg.get("stdev") or 0)

        valid_means = [m for m in means if m is not None]
        if not valid_means:
            continue

        x = list(range(len(means)))
        valid_x = [j for j, m in enumerate(means) if m is not None]
        valid_m = [m for m in means if m is not None]
        valid_s = [stdevs[j] for j in valid_x]

        color = metric_colors[i % len(metric_colors)]
        label = METRIC_LABELS[key].replace("\n", " ")
        ax.plot(valid_x, valid_m, "o-", color=color, label=label, linewidth=2, markersize=6)

        if any(s > 0 for s in valid_s):
            lower = [max(0, m - s) for m, s in zip(valid_m, valid_s)]
            upper = [min(1, m + s) for m, s in zip(valid_m, valid_s)]
            ax.fill_between(valid_x, lower, upper, color=color, alpha=0.15)

    ax.set_xticks(range(len(week_labels)))
    ax.set_xticklabels(week_labels, rotation=30, ha="right")
    ax.set_ylim(-0.05, 1.1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_ylabel("Score")
    ax.set_xlabel("Week Ending")
    trials = meta.get("trials_per_week", 1)
    title = f"LLM Evaluation Metrics Over Time ({len(weeks)} weeks"
    if trials > 1:
        title += f", {trials} trials each"
    title += ")"
    ax.set_title(title)
    ax.axhline(y=0.8, color=PALETTE["grey"], linestyle="--", linewidth=0.8, alpha=0.6)
    ax.legend(loc="lower left", fontsize=8, ncol=2)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "metrics_over_time.png"), dpi=180)
    plt.close(fig)
    print("  metrics_over_time.png")


def batch_chart_overall_summary(weeks: list[dict], meta: dict, out_dir: str):
    """Bar chart: overall mean ± stdev across all weeks for each metric."""
    overall: dict[str, list[float]] = {k: [] for k in METRIC_KEYS}
    for w in weeks:
        for k in METRIC_KEYS:
            val = w["aggregate"][k]["mean"]
            if val is not None:
                overall[k].append(val)

    labels = [METRIC_LABELS[k] for k in METRIC_KEYS]
    means = [statistics.mean(overall[k]) if overall[k] else 0 for k in METRIC_KEYS]
    stdevs = [statistics.stdev(overall[k]) if len(overall[k]) > 1 else 0 for k in METRIC_KEYS]
    colors = [_score_color(m) for m in means]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = range(len(labels))
    bars = ax.bar(x, means, yerr=stdevs, capsize=5, color=colors, width=0.55,
                  edgecolor="white", linewidth=1.2, error_kw={"linewidth": 1.5})

    for bar, m, s in zip(bars, means, stdevs):
        text = f"{m:.1%}"
        if s > 0:
            text += f"\n±{s:.1%}"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                text, ha="center", va="bottom", fontweight="bold", fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.2)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_ylabel("Score")
    n_weeks = len(weeks)
    trials = meta.get("trials_per_week", 1)
    ax.set_title(f"Overall LLM Quality — {n_weeks} weeks, {n_weeks * trials} total evaluations")
    ax.axhline(y=0.8, color=PALETTE["grey"], linestyle="--", linewidth=0.8, label="80% threshold")
    ax.legend(loc="lower right", fontsize=9)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "overall_summary.png"), dpi=180)
    plt.close(fig)
    print("  overall_summary.png")


def batch_chart_heatmap(weeks: list[dict], out_dir: str):
    """Heatmap: weeks × metrics."""
    week_labels = [w["date_range"].split(" to ")[-1] for w in reversed(weeks)]
    weeks_ordered = list(reversed(weeks))
    metric_labels = [METRIC_LABELS[k].replace("\n", " ") for k in METRIC_KEYS]

    data = []
    for w in weeks_ordered:
        row = []
        for k in METRIC_KEYS:
            val = w["aggregate"][k]["mean"]
            row.append(val if val is not None else float("nan"))
        data.append(row)

    arr = np.array(data)

    fig, ax = plt.subplots(figsize=(8, max(3, len(weeks) * 0.6 + 1)))
    im = ax.imshow(arr, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(metric_labels)))
    ax.set_xticklabels(metric_labels, fontsize=10)
    ax.set_yticks(range(len(week_labels)))
    ax.set_yticklabels(week_labels, fontsize=10)

    # Annotate cells
    for i in range(len(weeks_ordered)):
        for j in range(len(METRIC_KEYS)):
            val = arr[i, j]
            if not np.isnan(val):
                text_color = "white" if val < 0.4 else "black"
                ax.text(j, i, f"{val:.0%}", ha="center", va="center",
                        fontsize=11, fontweight="bold", color=text_color)

    ax.set_title("Metric Scores by Week")
    fig.colorbar(im, ax=ax, label="Score", shrink=0.8)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "heatmap.png"), dpi=180)
    plt.close(fig)
    print("  heatmap.png")


def batch_chart_consistency(weeks: list[dict], out_dir: str):
    """Box plot showing score distributions across all trials (if trials > 1)."""
    # Collect all individual trial scores per metric
    per_metric: dict[str, list[float]] = {k: [] for k in METRIC_KEYS}
    for w in weeks:
        for trial in w.get("trial_results", []):
            if "error" in trial:
                continue
            for k in METRIC_KEYS:
                score = trial["metrics"][k].get("score")
                if score is not None:
                    per_metric[k].append(score)

    if not any(per_metric.values()):
        return

    labels = [METRIC_LABELS[k].replace("\n", " ") for k in METRIC_KEYS]
    data = [per_metric[k] for k in METRIC_KEYS]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bp = ax.boxplot(data, labels=labels, patch_artist=True, widths=0.5)

    metric_colors = [PALETTE["blue"], PALETTE["purple"], PALETTE["green"],
                     PALETTE["amber"], PALETTE["red"]]
    for patch, color in zip(bp["boxes"], metric_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    ax.set_ylim(-0.05, 1.1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_ylabel("Score")
    total = sum(len(d) for d in data) // len(METRIC_KEYS)
    ax.set_title(f"Score Distribution Across {total} Evaluations")
    ax.axhline(y=0.8, color=PALETTE["grey"], linestyle="--", linewidth=0.8, alpha=0.6)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "consistency.png"), dpi=180)
    plt.close(fig)
    print("  consistency.png")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate evaluation charts")
    parser.add_argument("report", help="Path to report JSON file (single or batch)")
    parser.add_argument("-o", "--output-dir", default="charts",
                        help="Output directory (default: charts/)")
    args = parser.parse_args()

    with open(args.report) as f:
        report = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    # Auto-detect batch vs single-week report
    if "weeks" in report and isinstance(report["weeks"], list):
        # Batch report
        weeks = report["weeks"]
        meta = report.get("metadata", {})
        print(f"Generating batch charts ({len(weeks)} weeks) in {args.output_dir}/")
        batch_chart_metrics_over_time(weeks, meta, args.output_dir)
        batch_chart_overall_summary(weeks, meta, args.output_dir)
        batch_chart_heatmap(weeks, args.output_dir)
        batch_chart_consistency(weeks, args.output_dir)
    else:
        # Single-week report
        cm = report["custom_metrics"]
        meta = report.get("metadata", {})
        print(f"Generating charts in {args.output_dir}/")
        chart_metric_overview(cm, meta, args.output_dir)
        chart_symbol_accuracy(cm, args.output_dir)
        chart_symbol_coverage(cm, args.output_dir)
        chart_numerical_faithfulness(cm, args.output_dir)
        chart_output_completeness(cm, args.output_dir)

    print("Done.")


if __name__ == "__main__":
    main()
