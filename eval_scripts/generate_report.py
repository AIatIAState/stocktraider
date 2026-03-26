#!/usr/bin/env python3
"""
Generate a self-contained HTML report from a batch evaluation JSON file.

Usage:
  python generate_report.py batch_report.json -o report.html
"""

import argparse
import base64
import io
import json
import statistics
import sys
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
METRIC_KEYS = [
    "symbol_accuracy",
    "symbol_coverage",
    "numerical_faithfulness",
    "hedge_language",
    "output_completeness",
]

RAGAS_KEYS = ["faithfulness", "answer_relevancy"]

ALL_KEYS = METRIC_KEYS + RAGAS_KEYS

METRIC_LABELS = {
    "symbol_accuracy": "Symbol Accuracy",
    "symbol_coverage": "Symbol Coverage",
    "numerical_faithfulness": "Numerical Faithfulness",
    "hedge_language": "Hedge Language",
    "output_completeness": "Output Completeness",
    "faithfulness": "Faithfulness (Ragas)",
    "answer_relevancy": "Answer Relevancy (Ragas)",
}

SHORT_LABELS = {
    "symbol_accuracy": "Symbol\nAccuracy",
    "symbol_coverage": "Symbol\nCoverage",
    "numerical_faithfulness": "Numerical\nFaithfulness",
    "hedge_language": "Hedge\nLanguage",
    "output_completeness": "Output\nCompleteness",
    "faithfulness": "Faithfulness\n(Ragas)",
    "answer_relevancy": "Answer Rel.\n(Ragas)",
}

PALETTE = {
    "green": "#2ecc71",
    "amber": "#f39c12",
    "red": "#e74c3c",
    "blue": "#3498db",
    "purple": "#9b59b6",
    "grey": "#95a5a6",
}

METRIC_COLORS = [
    PALETTE["blue"],
    PALETTE["purple"],
    PALETTE["green"],
    PALETTE["amber"],
    PALETTE["red"],
    "#1abc9c",   # teal for faithfulness
    "#e67e22",   # dark amber for answer relevancy
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _score_color(score: float) -> str:
    if score >= 0.8:
        return PALETTE["green"]
    if score >= 0.5:
        return PALETTE["amber"]
    return PALETTE["red"]


def _score_badge_class(score: float) -> str:
    if score >= 0.8:
        return "badge-green"
    if score >= 0.5:
        return "badge-amber"
    return "badge-red"


def _cell_bg(score: float) -> str:
    if score >= 0.8:
        return "#d5f5e3"
    if score >= 0.5:
        return "#fdebd0"
    return "#fadbd8"


def _fig_to_data_uri(fig: plt.Figure, dpi: int = 150) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _has_ragas(report: dict) -> bool:
    return any("ragas" in w.get("aggregate", {}) for w in report.get("weeks", []))


def _get_overall_means(weeks: list[dict], has_ragas: bool) -> dict[str, float | None]:
    keys = ALL_KEYS if has_ragas else METRIC_KEYS
    result = {}
    for key in keys:
        vals = []
        for w in weeks:
            if key in RAGAS_KEYS:
                val = w["aggregate"].get("ragas", {}).get(key, {}).get("mean")
            else:
                val = w["aggregate"].get(key, {}).get("mean")
            if val is not None:
                vals.append(val)
        result[key] = statistics.mean(vals) if vals else None
    return result


def _get_overall_stdevs(weeks: list[dict], has_ragas: bool) -> dict[str, float | None]:
    keys = ALL_KEYS if has_ragas else METRIC_KEYS
    result = {}
    for key in keys:
        vals = []
        for w in weeks:
            if key in RAGAS_KEYS:
                val = w["aggregate"].get("ragas", {}).get(key, {}).get("mean")
            else:
                val = w["aggregate"].get(key, {}).get("mean")
            if val is not None:
                vals.append(val)
        result[key] = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return result


# ---------------------------------------------------------------------------
# Chart generators (return data URI strings)
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


def chart_overall_summary(weeks: list[dict], meta: dict, has_ragas: bool) -> str:
    """Bar chart: overall mean +/- stdev for all metrics."""
    keys = ALL_KEYS if has_ragas else METRIC_KEYS
    overall_means = _get_overall_means(weeks, has_ragas)
    overall_stdevs = _get_overall_stdevs(weeks, has_ragas)

    labels = [SHORT_LABELS[k] for k in keys]
    means = [overall_means.get(k) or 0 for k in keys]
    stdevs = [overall_stdevs.get(k) or 0 for k in keys]
    colors = [_score_color(m) for m in means]

    fig, ax = plt.subplots(figsize=(max(8, len(keys) * 1.3), 4.5))
    x = range(len(labels))
    bars = ax.bar(x, means, yerr=stdevs, capsize=5, color=colors, width=0.55,
                  edgecolor="white", linewidth=1.2, error_kw={"linewidth": 1.5})

    for bar, m, s in zip(bars, means, stdevs):
        text = f"{m:.1%}"
        if s > 0:
            text += f"\n+/-{s:.1%}"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                text, ha="center", va="bottom", fontweight="bold", fontsize=9)

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 1.25)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_ylabel("Score")
    n_weeks = len(weeks)
    trials = meta.get("trials_per_week", 1)
    ax.set_title(f"Overall LLM Quality -- {n_weeks} weeks, {n_weeks * trials} total evaluations")
    ax.axhline(y=0.8, color=PALETTE["grey"], linestyle="--", linewidth=0.8, label="80% threshold")
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    return _fig_to_data_uri(fig)


def chart_metrics_over_time(weeks: list[dict], meta: dict, has_ragas: bool) -> str:
    """Line chart with shaded stdev bands."""
    keys = ALL_KEYS if has_ragas else METRIC_KEYS
    weeks_ordered = list(reversed(weeks))  # chronological
    week_labels = [w["date_range"].split(" to ")[-1] for w in weeks_ordered]

    fig, ax = plt.subplots(figsize=(max(8, len(weeks) * 1.5), 5))

    for i, key in enumerate(keys):
        means = []
        stdevs = []
        for w in weeks_ordered:
            if key in RAGAS_KEYS:
                agg = w["aggregate"].get("ragas", {}).get(key, {})
            else:
                agg = w["aggregate"].get(key, {})
            means.append(agg.get("mean"))
            stdevs.append(agg.get("stdev") or 0)

        valid_x = [j for j, m in enumerate(means) if m is not None]
        valid_m = [means[j] for j in valid_x]
        valid_s = [stdevs[j] for j in valid_x]

        if not valid_m:
            continue

        color = METRIC_COLORS[i % len(METRIC_COLORS)]
        label = METRIC_LABELS[key]
        ax.plot(valid_x, valid_m, "o-", color=color, label=label, linewidth=2, markersize=5)

        if any(s > 0 for s in valid_s):
            lower = [max(0, m - s) for m, s in zip(valid_m, valid_s)]
            upper = [min(1, m + s) for m, s in zip(valid_m, valid_s)]
            ax.fill_between(valid_x, lower, upper, color=color, alpha=0.12)

    ax.set_xticks(range(len(week_labels)))
    ax.set_xticklabels(week_labels, rotation=30, ha="right")
    ax.set_ylim(-0.05, 1.1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_ylabel("Score")
    ax.set_xlabel("Week Ending")
    trials = meta.get("trials_per_week", 1)
    title = f"Metrics Over Time ({len(weeks)} weeks"
    if trials > 1:
        title += f", {trials} trials each"
    title += ")"
    ax.set_title(title)
    ax.axhline(y=0.8, color=PALETTE["grey"], linestyle="--", linewidth=0.8, alpha=0.6)
    ax.legend(loc="lower left", fontsize=7, ncol=2)
    fig.tight_layout()
    return _fig_to_data_uri(fig)


def chart_heatmap(weeks: list[dict], has_ragas: bool) -> str:
    """Heatmap: weeks x metrics grid."""
    keys = ALL_KEYS if has_ragas else METRIC_KEYS
    weeks_ordered = list(reversed(weeks))
    week_labels = [w["date_range"].split(" to ")[-1] for w in weeks_ordered]
    metric_labels = [METRIC_LABELS[k] for k in keys]

    data = []
    for w in weeks_ordered:
        row = []
        for k in keys:
            if k in RAGAS_KEYS:
                val = w["aggregate"].get("ragas", {}).get(k, {}).get("mean")
            else:
                val = w["aggregate"].get(k, {}).get("mean")
            row.append(val if val is not None else float("nan"))
        data.append(row)

    arr = np.array(data)

    fig, ax = plt.subplots(figsize=(max(8, len(keys) * 1.2), max(3, len(weeks) * 0.6 + 1)))
    im = ax.imshow(arr, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(metric_labels)))
    ax.set_xticklabels(metric_labels, fontsize=9, rotation=30, ha="right")
    ax.set_yticks(range(len(week_labels)))
    ax.set_yticklabels(week_labels, fontsize=10)

    for i in range(len(weeks_ordered)):
        for j in range(len(keys)):
            val = arr[i, j]
            if not np.isnan(val):
                text_color = "white" if val < 0.4 else "black"
                ax.text(j, i, f"{val:.0%}", ha="center", va="center",
                        fontsize=10, fontweight="bold", color=text_color)

    ax.set_title("Metric Scores by Week")
    fig.colorbar(im, ax=ax, label="Score", shrink=0.8)
    fig.tight_layout()
    return _fig_to_data_uri(fig)


def chart_box_plot(weeks: list[dict], has_ragas: bool) -> str:
    """Box plot showing score distributions across all trials."""
    keys = ALL_KEYS if has_ragas else METRIC_KEYS
    per_metric: dict[str, list[float]] = {k: [] for k in keys}

    for w in weeks:
        for trial in w.get("trial_results", []):
            if "error" in trial:
                continue
            for k in METRIC_KEYS:
                score = trial.get("metrics", {}).get(k, {}).get("score")
                if score is not None:
                    per_metric[k].append(score)
            if has_ragas:
                ragas = trial.get("ragas_metrics", {})
                overall = ragas.get("overall", {})
                for k in RAGAS_KEYS:
                    val = overall.get(k)
                    if val is not None:
                        per_metric[k].append(val)

    labels = [SHORT_LABELS[k] for k in keys]
    data = [per_metric[k] if per_metric[k] else [0] for k in keys]

    fig, ax = plt.subplots(figsize=(max(8, len(keys) * 1.3), 4.5))
    bp = ax.boxplot(data, labels=labels, patch_artist=True, widths=0.5)

    for idx, (patch, key) in enumerate(zip(bp["boxes"], keys)):
        patch.set_facecolor(METRIC_COLORS[idx % len(METRIC_COLORS)])
        patch.set_alpha(0.6)

    ax.set_ylim(-0.05, 1.1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_ylabel("Score")
    total = max(len(per_metric[k]) for k in keys) if keys else 0
    ax.set_title(f"Score Distribution Across {total} Evaluations")
    ax.axhline(y=0.8, color=PALETTE["grey"], linestyle="--", linewidth=0.8, alpha=0.6)
    fig.tight_layout()
    return _fig_to_data_uri(fig)


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #2c3e50;
    background: #f8f9fa;
    line-height: 1.6;
    padding: 0;
}
.container { max-width: 1100px; margin: 0 auto; padding: 24px 32px; }
h1 {
    font-size: 1.8em;
    border-bottom: 3px solid #3498db;
    padding-bottom: 12px;
    margin-bottom: 24px;
    color: #2c3e50;
}
h2 {
    font-size: 1.35em;
    color: #34495e;
    margin-top: 36px;
    margin-bottom: 16px;
    border-bottom: 1px solid #dee2e6;
    padding-bottom: 8px;
}
h3 {
    font-size: 1.1em;
    color: #495057;
    margin-top: 16px;
    margin-bottom: 8px;
}
p { margin-bottom: 12px; }
.meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}
.meta-item {
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 12px 16px;
}
.meta-item .label { font-size: 0.8em; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; }
.meta-item .value { font-size: 1.2em; font-weight: 600; color: #2c3e50; }
.badges { display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0; }
.badge {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.85em;
    font-weight: 600;
    color: white;
}
.badge-green { background: #2ecc71; }
.badge-amber { background: #f39c12; }
.badge-red { background: #e74c3c; }
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 20px 0;
    font-size: 0.9em;
}
th {
    background: #34495e;
    color: white;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
}
td { padding: 8px 12px; border-bottom: 1px solid #dee2e6; }
tr:nth-child(even) { background: #f8f9fa; }
tr:nth-child(odd) { background: white; }
tr:hover { background: #eef2f7; }
.chart-container { text-align: center; margin: 20px 0; }
.chart-container img { max-width: 100%; height: auto; border: 1px solid #dee2e6; border-radius: 6px; }
details {
    margin: 12px 0;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    background: white;
}
summary {
    padding: 12px 16px;
    cursor: pointer;
    font-weight: 600;
    color: #2c3e50;
    background: #f1f3f5;
    border-radius: 6px;
    user-select: none;
}
summary:hover { background: #e9ecef; }
details[open] summary { border-bottom: 1px solid #dee2e6; border-radius: 6px 6px 0 0; }
details .inner { padding: 16px; }
.bullet-text { font-size: 0.85em; color: #495057; max-width: 600px; }
.methodology-item { margin-bottom: 16px; padding-left: 16px; border-left: 3px solid #3498db; }
.methodology-item strong { color: #2c3e50; }
.cost-highlight { font-size: 1.1em; font-weight: 600; color: #2c3e50; margin: 12px 0; }
.footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid #dee2e6; font-size: 0.8em; color: #95a5a6; text-align: center; }
.score-cell { font-weight: 600; text-align: center; border-radius: 4px; }
"""


def _build_executive_summary(report: dict, has_ragas: bool, chart_uri: str) -> str:
    meta = report.get("metadata", {})
    weeks = report["weeks"]

    # Determine model name from first successful trial
    model = "unknown"
    for w in weeks:
        for t in w.get("trial_results", []):
            if "error" not in t and t.get("model"):
                model = t["model"]
                break
        if model != "unknown":
            break

    overall_means = _get_overall_means(weeks, has_ragas)

    html = '<h2>A. Executive Summary</h2>\n'
    html += '<div class="meta-grid">\n'

    items = [
        ("Model", model),
        ("Weeks Evaluated", str(meta.get("weeks", len(weeks)))),
        ("Trials per Week", str(meta.get("trials_per_week", 1))),
        ("Evaluation Date", meta.get("evaluated_at", "N/A")[:10]),
        ("Ragas Enabled", "Yes" if meta.get("ragas_enabled") else "No"),
        ("Num. Tolerance", f"+/-{meta.get('num_tolerance', 1.5)} pp"),
    ]
    for label, value in items:
        html += f'  <div class="meta-item"><div class="label">{label}</div><div class="value">{value}</div></div>\n'
    html += '</div>\n'

    # Badges
    html += '<h3>Overall Mean Scores</h3>\n<div class="badges">\n'
    keys = ALL_KEYS if has_ragas else METRIC_KEYS
    for key in keys:
        val = overall_means.get(key)
        if val is not None:
            badge_cls = _score_badge_class(val)
            html += f'  <span class="badge {badge_cls}">{METRIC_LABELS[key]}: {val:.1%}</span>\n'
        else:
            html += f'  <span class="badge badge-red">{METRIC_LABELS[key]}: N/A</span>\n'
    html += '</div>\n'

    # Chart
    html += f'<div class="chart-container"><img src="{chart_uri}" alt="Overall Summary Chart"></div>\n'

    return html


def _build_methodology() -> str:
    html = '<h2>B. Methodology</h2>\n'
    html += '<p>Each week is evaluated using 5 custom deterministic metrics and (optionally) 2 LLM-based Ragas metrics.</p>\n'

    descriptions = [
        ("Symbol Accuracy",
         "A regex extracts ticker-like tokens (e.g. AAPL, SPY, XWEL.US) from the LLM output. "
         "Each extracted symbol is checked against the set of symbols present in the context data "
         "(alerts + benchmarks). Score = matched / total extracted. A score of 1.0 means every "
         "symbol the LLM mentioned actually exists in the data it was given."),
        ("Symbol Coverage",
         "Measures what fraction of the context symbols the LLM chose to reference. "
         "Score = (number of context symbols mentioned in output) / (total context symbols). "
         "Low coverage is expected when data contains many small-cap stocks and the LLM focuses "
         "on the most notable movers."),
        ("Numerical Faithfulness",
         "A regex extracts all stated percentages from the output (e.g. '7.50%', '338.24%'). "
         "Each is verified against actual percentage-change values in the context data within a "
         "configurable tolerance (default +/-1.5 percentage points). Score = matched / total stated."),
        ("Hedge Language",
         "Checks that event-impact bullets contain appropriate cautious language. Looks for hedge "
         "words/phrases such as 'could', 'may', 'potentially', 'might', 'possible', 'likely'. "
         "Score = (hedged bullets) / (total event impact bullets). A score of 1.0 indicates all "
         "forward-looking statements are properly hedged."),
        ("Output Completeness",
         "Validates that the output contains the expected number of bullets. Market insights "
         "should have 3-5 bullets; event impacts should have 0-5 bullets. Score = 1.0 if both "
         "counts fall within range, 0.5 if one is out of range, 0.0 if both are out of range."),
        ("Faithfulness (Ragas)",
         "An LLM decomposes each output bullet into individual factual statements (claims). "
         "Each claim is then checked against the original context data using Natural Language "
         "Inference (NLI) to determine whether it is supported. Score = fraction of all claims "
         "that are faithful to the context. This is computed per-bullet then averaged."),
        ("Answer Relevancy (Ragas)",
         "An LLM generates synthetic questions that the response bullet would answer. These "
         "synthetic questions are compared to the original prompt using embedding cosine "
         "similarity. Higher similarity means the response is more relevant to what was asked. "
         "Scores tend to be lower for forward-looking event impact bullets."),
    ]

    for title, desc in descriptions:
        html += f'<div class="methodology-item"><strong>{title}</strong><br>{desc}</div>\n'

    return html


def _build_results_over_time(chart_line_uri: str, chart_heatmap_uri: str) -> str:
    html = '<h2>C. Results Over Time</h2>\n'
    html += f'<div class="chart-container"><img src="{chart_line_uri}" alt="Metrics Over Time"></div>\n'
    html += f'<div class="chart-container"><img src="{chart_heatmap_uri}" alt="Heatmap"></div>\n'
    return html


def _build_distributions(chart_box_uri: str) -> str:
    html = '<h2>D. Score Distributions</h2>\n'
    html += '<p>Box plot showing the spread of scores across all individual trial evaluations for each metric.</p>\n'
    html += f'<div class="chart-container"><img src="{chart_box_uri}" alt="Score Distributions"></div>\n'
    return html


def _build_per_week_breakdown(weeks: list[dict], has_ragas: bool) -> str:
    html = '<h2>E. Per-Week Breakdown</h2>\n'

    for idx, week in enumerate(weeks):
        date_range = week.get("date_range", "Unknown")
        trials_count = week.get("trials", 0)
        agg = week.get("aggregate", {})

        html += f'<details{"" if idx > 0 else " open"}>\n'
        html += f'<summary>Week: {date_range} ({trials_count} trial{"s" if trials_count != 1 else ""})</summary>\n'
        html += '<div class="inner">\n'

        # Custom metrics aggregate table
        html += '<h3>Custom Metric Aggregates</h3>\n'
        html += '<table><tr><th>Metric</th><th>Mean</th><th>Stdev</th><th>Min</th><th>Max</th><th>N</th></tr>\n'
        for key in METRIC_KEYS:
            m = agg.get(key, {})
            mean_val = m.get("mean")
            if mean_val is not None:
                bg = _cell_bg(mean_val)
                html += f'<tr><td>{METRIC_LABELS[key]}</td>'
                html += f'<td class="score-cell" style="background:{bg}">{mean_val:.1%}</td>'
                html += f'<td>{m.get("stdev", 0):.3f}</td>'
                html += f'<td>{m.get("min", 0):.1%}</td>'
                html += f'<td>{m.get("max", 0):.1%}</td>'
                html += f'<td>{m.get("n", 0)}</td></tr>\n'
            else:
                html += f'<tr><td>{METRIC_LABELS[key]}</td><td>N/A</td><td>-</td><td>-</td><td>-</td><td>0</td></tr>\n'
        html += '</table>\n'

        # Ragas aggregate table
        ragas_agg = agg.get("ragas", {})
        if ragas_agg:
            html += '<h3>Ragas Metric Aggregates</h3>\n'
            html += '<table><tr><th>Metric</th><th>Mean</th><th>Stdev</th><th>Min</th><th>Max</th><th>N</th></tr>\n'
            for key in RAGAS_KEYS:
                m = ragas_agg.get(key, {})
                mean_val = m.get("mean")
                if mean_val is not None:
                    bg = _cell_bg(mean_val)
                    html += f'<tr><td>{METRIC_LABELS[key]}</td>'
                    html += f'<td class="score-cell" style="background:{bg}">{mean_val:.1%}</td>'
                    html += f'<td>{m.get("stdev", 0):.3f}</td>'
                    html += f'<td>{m.get("min", 0):.1%}</td>'
                    html += f'<td>{m.get("max", 0):.1%}</td>'
                    html += f'<td>{m.get("n", 0)}</td></tr>\n'
                else:
                    html += f'<tr><td>{METRIC_LABELS[key]}</td><td>N/A</td><td>-</td><td>-</td><td>-</td><td>0</td></tr>\n'
            html += '</table>\n'

        # Per-trial bullet-level details
        trial_results = week.get("trial_results", [])
        for t_idx, trial in enumerate(trial_results):
            if "error" in trial:
                html += f'<p><em>Trial {t_idx + 1}: Error - {trial["error"]}</em></p>\n'
                continue

            ragas_metrics = trial.get("ragas_metrics", {})
            if not ragas_metrics or "error" in ragas_metrics:
                continue

            html += f'<details>\n<summary>Trial {t_idx + 1} - Per-Bullet Ragas Scores</summary>\n'
            html += '<div class="inner">\n'

            for section_key in ["market_insights", "event_impacts"]:
                section = ragas_metrics.get(section_key, {})
                bullets = section.get("bullets", [])
                if not bullets:
                    continue

                section_label = section_key.replace("_", " ").title()
                html += f'<h3>{section_label} (Faithfulness: {section.get("faithfulness", 0):.1%}, '
                html += f'Relevancy: {section.get("answer_relevancy", 0):.1%})</h3>\n'
                html += '<table><tr><th>#</th><th>Bullet Text</th><th>Faithfulness</th><th>Answer Relevancy</th></tr>\n'

                for b_idx, bullet in enumerate(bullets):
                    text = bullet.get("text", "")
                    faith = bullet.get("faithfulness")
                    relev = bullet.get("answer_relevancy")

                    faith_str = f"{faith:.3f}" if faith is not None else "N/A"
                    relev_str = f"{relev:.3f}" if relev is not None else "N/A"

                    faith_bg = _cell_bg(faith) if faith is not None else "#ffffff"
                    relev_bg = _cell_bg(relev) if relev is not None else "#ffffff"

                    html += f'<tr><td>{b_idx + 1}</td>'
                    html += f'<td class="bullet-text">{_html_escape(text)}</td>'
                    html += f'<td class="score-cell" style="background:{faith_bg}">{faith_str}</td>'
                    html += f'<td class="score-cell" style="background:{relev_bg}">{relev_str}</td></tr>\n'

                html += '</table>\n'

            html += '</div>\n</details>\n'

        html += '</div>\n</details>\n'

    return html


def _build_cost_analysis(weeks: list[dict]) -> str:
    html = '<h2>F. Cost Analysis</h2>\n'

    has_any_cost = False
    for w in weeks:
        if w.get("aggregate", {}).get("ragas_cost"):
            has_any_cost = True
            break
        for t in w.get("trial_results", []):
            if t.get("ragas_metrics", {}).get("cost"):
                has_any_cost = True
                break

    if not has_any_cost:
        html += '<p>No Ragas evaluation cost data available (Ragas was skipped or not installed).</p>\n'
        return html

    # Per-week cost table
    html += '<table><tr><th>Week</th><th>LLM Input Tokens</th><th>LLM Output Tokens</th>'
    html += '<th>Embedding Tokens</th><th>Total Cost (USD)</th></tr>\n'

    total_llm_in = 0
    total_llm_out = 0
    total_embed = 0
    total_cost = 0.0
    num_evals = 0

    for w in weeks:
        date_range = w.get("date_range", "?")
        cost = w.get("aggregate", {}).get("ragas_cost", {})

        llm_in = cost.get("llm_input_tokens", 0)
        llm_out = cost.get("llm_output_tokens", 0)
        embed = cost.get("embedding_tokens", 0)
        usd = cost.get("total_cost_usd", 0)

        total_llm_in += llm_in
        total_llm_out += llm_out
        total_embed += embed
        total_cost += usd

        # Count successful evaluations with ragas
        for t in w.get("trial_results", []):
            if "error" not in t and t.get("ragas_metrics", {}).get("cost"):
                num_evals += 1

        html += f'<tr><td>{date_range}</td>'
        html += f'<td>{llm_in:,}</td><td>{llm_out:,}</td><td>{embed:,}</td>'
        html += f'<td>${usd:.4f}</td></tr>\n'

    # Totals row
    html += f'<tr style="font-weight:bold;background:#e8f4fd"><td>TOTAL</td>'
    html += f'<td>{total_llm_in:,}</td><td>{total_llm_out:,}</td><td>{total_embed:,}</td>'
    html += f'<td>${total_cost:.4f}</td></tr>\n'
    html += '</table>\n'

    html += f'<p class="cost-highlight">Total Ragas Evaluation Cost: ${total_cost:.4f}</p>\n'
    if num_evals > 0:
        avg_cost = total_cost / num_evals
        html += f'<p class="cost-highlight">Average Cost per Evaluation: ${avg_cost:.4f} ({num_evals} evaluations)</p>\n'

    return html


def _html_escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------
def generate_html_report(report: dict) -> str:
    weeks = report.get("weeks", [])
    meta = report.get("metadata", {})
    has_ragas = _has_ragas(report)

    # Generate charts
    chart_summary = chart_overall_summary(weeks, meta, has_ragas)
    chart_line = chart_metrics_over_time(weeks, meta, has_ragas)
    chart_heat = chart_heatmap(weeks, has_ragas)
    chart_box = chart_box_plot(weeks, has_ragas)

    # Build HTML sections
    parts = []
    parts.append("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n")
    parts.append("<meta charset=\"UTF-8\">\n")
    parts.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n")
    parts.append("<title>LLM Batch Evaluation Report</title>\n")
    parts.append(f"<style>\n{CSS}\n</style>\n")
    parts.append("</head>\n<body>\n<div class=\"container\">\n")
    parts.append("<h1>LLM Batch Evaluation Report</h1>\n")

    parts.append(_build_executive_summary(report, has_ragas, chart_summary))
    parts.append(_build_methodology())
    parts.append(_build_results_over_time(chart_line, chart_heat))
    parts.append(_build_distributions(chart_box))
    parts.append(_build_per_week_breakdown(weeks, has_ragas))
    parts.append(_build_cost_analysis(weeks))

    # Footer
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    parts.append(f'<div class="footer">Report generated on {now} by generate_report.py</div>\n')

    parts.append("</div>\n</body>\n</html>")

    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a self-contained HTML report from a batch evaluation JSON.",
    )
    parser.add_argument(
        "input",
        help="Path to batch evaluation JSON file (output of batch_evaluate.py)",
    )
    parser.add_argument(
        "-o", "--output",
        default="report.html",
        help="Output HTML file path (default: report.html)",
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        report = json.load(f)

    if "weeks" not in report or not isinstance(report["weeks"], list):
        print("ERROR: Input JSON does not look like a batch report (missing 'weeks' array).",
              file=sys.stderr)
        sys.exit(1)

    print(f"Generating HTML report from {args.input} ...")
    print(f"  Weeks: {len(report['weeks'])}")
    print(f"  Ragas data: {'yes' if _has_ragas(report) else 'no'}")

    html = generate_html_report(report)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Report written to {args.output}")
    print("Done.")


if __name__ == "__main__":
    main()
