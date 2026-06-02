"""
generate_backtest_charts.py

Generates aggregate result charts from the trading simulation backtest data in:
  complete-backtest-results-20260402T004302Z-3-001/complete-backtest-results/

Outputs 10 PNG charts to eval_scripts/charts/backtest/

Usage:
    python eval_scripts/generate_backtest_charts.py
    python eval_scripts/generate_backtest_charts.py --data-dir path/to/complete-backtest-results
"""

import argparse
import re
import sys
from glob import glob
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
DEFAULT_DATA_DIR = (
    SCRIPT_DIR
    / "complete-backtest-results-20260402T004302Z-3-001"
    / "complete-backtest-results"
)

NN_SP500_DIR = "simulation_results_naive_nn_sp500_2021-2025"
NN_DOW_DIR = "simulation_results_naive_nn_sp500_train_dow_test_2021-2025"
PATTERN_CSV = "Historical Patterns/pattern_recognition_backtesting.csv"

MODEL_LABELS = {
    NN_SP500_DIR: "NN (S&P 500)",
    NN_DOW_DIR: "NN (DOW->S&P 500)",
}

OUT_DIR = SCRIPT_DIR / "charts" / "backtest"

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
COLORS = {
    NN_SP500_DIR: "#2196F3",
    NN_DOW_DIR: "#FF9800",
}
GREEN = "#4CAF50"
RED = "#F44336"
GRID_ALPHA = 0.3

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": GRID_ALPHA,
    "figure.dpi": 130,
})

# ---------------------------------------------------------------------------
# S&P 500 baseline (SPY.US daily close from the project SQLite database)
# ---------------------------------------------------------------------------
DB_PATH = SCRIPT_DIR.parent / "data" / "stocks.db"


def load_spy_baseline(start_date: str, end_date: str) -> pd.DataFrame:
    """Load SPY daily closes from stocks.db, return DataFrame with date + cumul_roi columns.

    cumul_roi = percentage return relative to the first trading day in the range.
    """
    import sqlite3
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    start_int = int(start_date.replace("-", ""))
    end_int = int(end_date.replace("-", ""))
    df = pd.read_sql(
        "SELECT date, close FROM bars "
        "WHERE symbol='SPY.US' AND timeframe='daily' "
        "AND date >= ? AND date <= ? ORDER BY date",
        conn, params=(start_int, end_int),
    )
    conn.close()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    base = df["close"].iloc[0]
    df["cumul_roi"] = (df["close"] / base - 1) * 100
    return df


def load_bah_returns(tickers: list, start_date: str, end_date: str) -> pd.DataFrame:
    """Buy-and-hold return for each ticker over the date range, from stocks.db."""
    import sqlite3
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    start_int = int(start_date.replace("-", ""))
    end_int = int(end_date.replace("-", ""))
    rows = []
    for ticker in tickers:
        df = pd.read_sql(
            "SELECT date, close FROM bars "
            "WHERE symbol=? AND timeframe='daily' "
            "AND date >= ? AND date <= ? ORDER BY date",
            conn, params=(ticker, start_int, end_int),
        )
        if len(df) < 10:
            continue
        ret = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
        rows.append({"ticker": ticker, "bah_return": ret})
    conn.close()
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_output_md(path: Path) -> pd.DataFrame:
    """Parse output.md into a DataFrame with one row per ticker.

    The file alternates: separator / ticker-header / separator / data-block
    so we use findall with a multi-line pattern across the whole text.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        r"Simulation Results for (.+?):\s*-{10,}\s*"
        r"Wallet:\s*([-\d.]+)\s*"
        r"Total Invested:\s*([-\d.]+)\s*"
        r"Earnings \(Sold\):\s*([-\d.]+)\s*"
        r"Expense \(Bought\):\s*([-\d.]+)\s*"
        r"Return on investment:\s*([-\d.]+)%\s*"
        r"Number of investments:\s*(\d+)",
        re.DOTALL,
    )
    records = []
    for m in pattern.finditer(text):
        records.append({
            "ticker": m.group(1).strip(),
            "wallet": float(m.group(2)),
            "total_invested": float(m.group(3)),
            "earnings": float(m.group(4)),
            "expenses": float(m.group(5)),
            "roi": float(m.group(6)),
            "num_investments": int(m.group(7)),
        })
    return pd.DataFrame(records)


def load_all_timeseries(sim_dir: Path) -> pd.DataFrame:
    """Load all *_data.csv files and return last-entry-per-date-per-ticker combined frame."""
    frames = []
    for csv_path in sim_dir.glob("*_data.csv"):
        df = pd.read_csv(csv_path, parse_dates=["date"])
        ticker = re.search(r"simulation_results_(.+)_data", csv_path.name)
        df["ticker"] = ticker.group(1) if ticker else csv_path.stem
        # Keep last row per date (captures final state after all intraday trades)
        df = df.groupby("date", as_index=False).last()
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_all_investments(sim_dir: Path) -> pd.DataFrame:
    """Load all *_investments.csv files from a simulation directory."""
    frames = []
    for csv_path in sim_dir.glob("*_investments.csv"):
        df = pd.read_csv(csv_path)
        ticker = re.search(r"simulation_results_(.+)_investments", csv_path.name)
        df["ticker"] = ticker.group(1) if ticker else csv_path.stem
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    combined["pnl_pct"] = (
        (combined["selling_price"] - combined["purchase_price"])
        / combined["purchase_price"]
        * 100
    )
    combined["purchase_date"] = pd.to_datetime(combined["purchase_date"])
    combined["selling_date"] = pd.to_datetime(combined["selling_date"])
    combined["holding_days"] = (
        combined["selling_date"] - combined["purchase_date"]
    ).dt.days
    return combined


# ---------------------------------------------------------------------------
# Section A — Per-Ticker Summary Charts
# ---------------------------------------------------------------------------

def chart_roi_distribution(summaries: dict, out_dir: Path):
    """Overlaid histogram + KDE of final ROI% for both NN models."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for key, df in summaries.items():
        roi = df["roi"].dropna()
        ax.hist(
            roi, bins=25, alpha=0.45, color=COLORS[key],
            label=MODEL_LABELS[key], edgecolor="white", linewidth=0.4,
        )
        # KDE overlay
        from scipy.stats import gaussian_kde
        kde = gaussian_kde(roi, bw_method=0.4)
        xs = np.linspace(roi.min() - 5, roi.max() + 5, 300)
        scale = len(roi) * (roi.max() - roi.min()) / 25
        ax.plot(xs, kde(xs) * scale, color=COLORS[key], linewidth=2)

    ax.axvline(0, color="black", linewidth=1.2, linestyle="--", label="Break-even (0%)")
    ax.set_xlabel("Final ROI (%)")
    ax.set_ylabel("Number of Tickers")
    ax.set_title("ROI Distribution Across Tickers (2021–2025)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "roi_distribution.png")
    plt.close(fig)
    print("  [OK] roi_distribution.png")


def chart_wallet_distribution(summaries: dict, out_dir: Path):
    """Boxplot of final wallet balance per model (started at $100)."""
    fig, ax = plt.subplots(figsize=(7, 5))
    data = [df["wallet"].dropna().values for df in summaries.values()]
    labels = [MODEL_LABELS[k] for k in summaries]
    bp = ax.boxplot(
        data, labels=labels, patch_artist=True, notch=False,
        medianprops={"color": "black", "linewidth": 1.5},
    )
    for patch, key in zip(bp["boxes"], summaries.keys()):
        patch.set_facecolor(COLORS[key])
        patch.set_alpha(0.7)
    ax.axhline(100, color="black", linewidth=1, linestyle="--", label="Initial $100")
    ax.set_ylabel("Final Wallet Balance ($)")
    ax.set_title("Final Wallet Balance Distribution (Initial: $100)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "wallet_distribution.png")
    plt.close(fig)
    print("  [OK] wallet_distribution.png")


def chart_win_rate(summaries: dict, out_dir: Path):
    """Grouped bar chart: % tickers with positive/negative ROI per model."""
    labels = [MODEL_LABELS[k] for k in summaries]
    win_pcts, lose_pcts = [], []
    for df in summaries.values():
        n = len(df)
        win_pcts.append(100 * (df["roi"] > 0).sum() / n)
        lose_pcts.append(100 * (df["roi"] <= 0).sum() / n)

    x = np.arange(len(labels))
    w = 0.35
    fig, ax = plt.subplots(figsize=(7, 5))
    bars_win = ax.bar(x - w / 2, win_pcts, w, label="Positive ROI", color=GREEN, alpha=0.85)
    bars_lose = ax.bar(x + w / 2, lose_pcts, w, label="Negative ROI", color=RED, alpha=0.85)

    for bar in list(bars_win) + list(bars_lose):
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2, h + 0.8,
            f"{h:.1f}%", ha="center", va="bottom", fontsize=9,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Percentage of Tickers (%)")
    ax.set_title("Win Rate: Tickers with Positive vs Negative ROI")
    ax.set_ylim(0, 110)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "win_rate.png")
    plt.close(fig)
    print("  [OK] win_rate.png")


def chart_roi_vs_trades(summaries: dict, out_dir: Path):
    """Scatter plot: num_investments vs ROI%, colored by model."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for key, df in summaries.items():
        ax.scatter(
            df["num_investments"], df["roi"],
            color=COLORS[key], label=MODEL_LABELS[key],
            alpha=0.65, s=35, edgecolors="white", linewidths=0.3,
        )
    ax.axhline(0, color="black", linewidth=1, linestyle="--", alpha=0.5)
    ax.set_xlabel("Number of Trades")
    ax.set_ylabel("Final ROI (%)")
    ax.set_title("ROI vs Number of Trades per Ticker")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "roi_vs_trades.png")
    plt.close(fig)
    print("  [OK] roi_vs_trades.png")


# ---------------------------------------------------------------------------
# Section B — Trade-Level Charts
# ---------------------------------------------------------------------------

def chart_trade_pnl_distribution(trades: dict, out_dir: Path):
    """Histogram of per-trade P&L% for each model (two subplots)."""
    keys = list(trades.keys())
    fig, axes = plt.subplots(1, len(keys), figsize=(5 * len(keys), 5), sharey=False)
    if len(keys) == 1:
        axes = [axes]

    for ax, key in zip(axes, keys):
        pnl = trades[key]["pnl_pct"].dropna()
        # Clip extreme outliers for display
        p1, p99 = np.percentile(pnl, 1), np.percentile(pnl, 99)
        pnl_clipped = pnl.clip(p1, p99)
        ax.hist(pnl_clipped, bins=50, color=COLORS[key], alpha=0.8, edgecolor="white", linewidth=0.3)
        ax.axvline(0, color="black", linewidth=1.2, linestyle="--")
        mean_pnl = pnl.mean()
        ax.axvline(mean_pnl, color=GREEN if mean_pnl >= 0 else RED,
                   linewidth=1.5, linestyle=":", label=f"Mean: {mean_pnl:.2f}%")
        ax.set_xlabel("Trade P&L (%)")
        ax.set_ylabel("Count")
        ax.set_title(MODEL_LABELS[key])
        ax.legend(fontsize=8)

    fig.suptitle("Per-Trade Profit/Loss Distribution (1st–99th percentile)", y=1.01)
    fig.tight_layout()
    fig.savefig(out_dir / "trade_pnl_distribution.png", bbox_inches="tight")
    plt.close(fig)
    print("  [OK] trade_pnl_distribution.png")


def chart_holding_period(trades: dict, out_dir: Path):
    """Overlaid histogram of holding period (days) per model."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for key, df in trades.items():
        hp = df["holding_days"].dropna()
        hp = hp[hp >= 0]
        ax.hist(
            hp, bins=30, alpha=0.5, color=COLORS[key],
            label=f"{MODEL_LABELS[key]} (median {hp.median():.0f}d)",
            edgecolor="white", linewidth=0.3,
        )
    ax.set_xlabel("Holding Period (Days)")
    ax.set_ylabel("Number of Trades")
    ax.set_title("Trade Holding Period Distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "holding_period.png")
    plt.close(fig)
    print("  [OK] holding_period.png")


def chart_trade_win_rate(trades: dict, out_dir: Path):
    """Bar chart: % of individual trades that were profitable per model."""
    labels = [MODEL_LABELS[k] for k in trades]
    win_pcts = [
        100 * (df["pnl_pct"] > 0).sum() / len(df)
        for df in trades.values()
    ]
    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(labels, win_pcts, color=[COLORS[k] for k in trades], alpha=0.85, edgecolor="white")
    for bar, pct in zip(bars, win_pcts):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
            f"{pct:.1f}%", ha="center", va="bottom", fontsize=10,
        )
    ax.set_ylabel("Profitable Trades (%)")
    ax.set_title("Individual Trade Win Rate")
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    fig.tight_layout()
    fig.savefig(out_dir / "trade_win_rate.png")
    plt.close(fig)
    print("  [OK] trade_win_rate.png")


# ---------------------------------------------------------------------------
# Section C — Pattern Recognition Charts
# ---------------------------------------------------------------------------

def chart_pattern_directional_accuracy(df: pd.DataFrame, out_dir: Path):
    """Bar chart of mean directional accuracy by interval."""
    grouped = df.groupby("interval")["directional_accuracy"].mean().sort_index()
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(
        [f"{i} min" for i in grouped.index],
        grouped.values * 100,
        color="#9C27B0", alpha=0.8, edgecolor="white",
    )
    for bar, val in zip(bars, grouped.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4,
            f"{val*100:.1f}%", ha="center", va="bottom", fontsize=9,
        )
    ax.set_xlabel("Candle Interval")
    ax.set_ylabel("Mean Directional Accuracy (%)")
    ax.set_title("Pattern Recognition: Directional Accuracy by Interval")
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    fig.tight_layout()
    fig.savefig(out_dir / "pattern_directional_accuracy.png")
    plt.close(fig)
    print("  [OK] pattern_directional_accuracy.png")


def chart_pattern_mse_comparison(df: pd.DataFrame, out_dir: Path):
    """Paired bar chart of mean MSE vs baseline MSE by interval."""
    grouped = df.groupby("interval")[["mse", "mse_baseline"]].mean().sort_index()
    intervals = [f"{i} min" for i in grouped.index]
    x = np.arange(len(intervals))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - w / 2, grouped["mse"] * 1e4, w, label="Model MSE (x10)",
           color="#2196F3", alpha=0.8, edgecolor="white")
    ax.bar(x + w / 2, grouped["mse_baseline"] * 1e4, w, label="Baseline MSE (x10)",
           color="#FF9800", alpha=0.8, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(intervals)
    ax.set_ylabel("MSE (x10)")
    ax.set_title("Pattern Recognition: Model MSE vs Baseline MSE by Interval")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "pattern_mse_comparison.png")
    plt.close(fig)
    print("  [OK] pattern_mse_comparison.png")


def chart_pattern_accuracy_by_ticker(df: pd.DataFrame, out_dir: Path):
    """Horizontal bar chart of mean directional accuracy per ticker, sorted."""
    grouped = (
        df.groupby("ticker")["directional_accuracy"]
        .mean()
        .sort_values(ascending=True)
    )
    # Limit to top/bottom for readability if too many tickers
    if len(grouped) > 40:
        grouped = pd.concat([grouped.head(20), grouped.tail(20)])

    fig, ax = plt.subplots(figsize=(8, max(6, len(grouped) * 0.28)))
    colors = [GREEN if v >= 0.5 else RED for v in grouped.values]
    ax.barh(grouped.index, grouped.values * 100, color=colors, alpha=0.8, edgecolor="white", linewidth=0.3)
    ax.axvline(50, color="black", linewidth=1, linestyle="--", label="50% (random)")
    ax.set_xlabel("Mean Directional Accuracy (%)")
    ax.set_title("Pattern Recognition: Directional Accuracy by Ticker")
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "pattern_accuracy_by_ticker.png", bbox_inches="tight")
    plt.close(fig)
    print("  [OK] pattern_accuracy_by_ticker.png")


# ---------------------------------------------------------------------------
# Section D -- Time Series Charts
# ---------------------------------------------------------------------------

def _compute_annual_gain(ts: pd.DataFrame) -> pd.DataFrame:
    """Helper: per-ticker annual ROI change from the strategy time series."""
    ts = ts.copy()
    ts["year"] = ts["date"].dt.year
    year_end = ts.groupby(["year", "ticker"])["roi"].last()
    year_start = ts.groupby(["year", "ticker"])["roi"].first()
    annual_gain = (year_end - year_start).reset_index()
    annual_gain.columns = ["year", "ticker", "annual_roi"]
    return annual_gain


def _spy_annual_returns(spy: pd.DataFrame) -> dict:
    """Compute SPY annual price return (%) from daily close data."""
    spy = spy.copy()
    spy["year"] = spy["date"].dt.year
    first = spy.groupby("year")["close"].first()
    last = spy.groupby("year")["close"].last()
    return ((last / first - 1) * 100).to_dict()


def chart_roi_over_time(ts: pd.DataFrame, label: str, out_dir: Path, spy: pd.DataFrame):
    """Single long-run chart: median cumulative ROI vs SPY cumulative return.

    Both series start at 0% on the first trading day and represent
    cumulative % return on an initial $100 investment.
    The y-axis is fixed so both series are easy to compare.
    """
    ts = ts.copy()
    ts["week"] = ts["date"].dt.to_period("W").dt.start_time
    grouped = ts.groupby(["week", "ticker"])["roi"].last().reset_index()
    weekly = grouped.groupby("week")["roi"].agg(
        median="median", q25=lambda x: x.quantile(0.25), q75=lambda x: x.quantile(0.75)
    ).reset_index()

    fig, ax = plt.subplots(figsize=(12, 5))

    # Strategy IQR band — clamp top to keep SPY on the same visible scale
    q75_clipped = weekly["q75"].clip(upper=100)
    ax.fill_between(weekly["week"], weekly["q25"], q75_clipped,
                    alpha=0.22, color="#2196F3", label="Strategy 25th-75th percentile")
    ax.plot(weekly["week"], weekly["median"], color="#2196F3", linewidth=2,
            label="Strategy median cumulative return")

    # SPY — same cumulative % return starting from the same date
    if not spy.empty:
        # Align SPY to the strategy's first week using exact date merge
        spy_daily = spy.set_index("date")["cumul_roi"]
        # Map each strategy week to the nearest available SPY trading day
        strategy_dates = weekly["week"].values
        spy_aligned = spy_daily.reindex(
            spy_daily.index.union(pd.DatetimeIndex(strategy_dates))
        ).interpolate(method="time").reindex(pd.DatetimeIndex(strategy_dates))
        ax.plot(weekly["week"], spy_aligned.values, color="#FF9800", linewidth=2,
                linestyle="--", label="SPY (S&P 500) cumulative return")

    ax.axhline(0, color="black", linewidth=1, linestyle="--", alpha=0.4)

    # Fix y-axis so both series are clearly readable
    all_vals = list(weekly["median"])
    if not spy.empty:
        all_vals += list(spy_aligned.dropna())
    ymax = max(100, max(all_vals) * 1.15)
    ymin = min(-20, min(all_vals) * 1.15)
    ax.set_ylim(ymin, ymax)

    # Year bands
    years = sorted(weekly["week"].dt.year.unique())
    for i, yr in enumerate(years):
        yr_data = weekly[weekly["week"].dt.year == yr]
        if yr_data.empty:
            continue
        ax.axvspan(yr_data["week"].min(), yr_data["week"].max(),
                   alpha=0.04 if i % 2 == 0 else 0, color="gray")
        mid = yr_data["week"].min() + (yr_data["week"].max() - yr_data["week"].min()) / 2
        ax.text(mid, ymin + 1, str(yr), ha="center", va="bottom",
                fontsize=8, color="gray", alpha=0.7)

    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Return on $100 (%)")
    ax.set_title(f"Cumulative Return Over Time - {label} vs SPY")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%+.0f%%"))
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "roi_over_time.png")
    plt.close(fig)
    print("  [OK] roi_over_time.png")


def chart_yearly_roi(ts: pd.DataFrame, label: str, out_dir: Path, spy: pd.DataFrame):
    """Grouped bar chart: strategy mean annual return vs SPY annual return, same scale."""
    annual_gain = _compute_annual_gain(ts)
    summary = annual_gain.groupby("year")["annual_roi"].agg(
        mean="mean", std="std", median="median"
    ).reset_index()

    spy_returns = _spy_annual_returns(spy) if not spy.empty else {}

    x = np.arange(len(summary))
    # Narrower bars when SPY is present so both fit side-by-side
    w = 0.38 if spy_returns else 0.55

    fig, ax = plt.subplots(figsize=(9, 5))

    # Strategy bars
    strat_colors = [GREEN if v >= 0 else RED for v in summary["mean"]]
    strat_bars = ax.bar(x - w / 2, summary["mean"], w,
                        yerr=summary["std"], capsize=5,
                        color=strat_colors, alpha=0.8, edgecolor="white",
                        error_kw={"elinewidth": 1.2, "ecolor": "gray"},
                        label="Strategy (mean +/- std)")
    for bar, mean_val, med_val in zip(strat_bars, summary["mean"], summary["median"]):
        h = bar.get_height()
        offset = 1.2 if h >= 0 else -3
        ax.text(bar.get_x() + bar.get_width() / 2, h + offset,
                f"mean {mean_val:+.1f}%\nmed {med_val:+.1f}%",
                ha="center", va="bottom" if h >= 0 else "top", fontsize=7.5)

    # SPY bars — same type and scale
    if spy_returns:
        spy_vals = [spy_returns.get(yr, np.nan) for yr in summary["year"]]
        spy_colors = [GREEN if (not np.isnan(v) and v >= 0) else RED for v in spy_vals]
        spy_bars = ax.bar(x + w / 2, spy_vals, w,
                          color=spy_colors, alpha=0.5, edgecolor="#E65100",
                          linewidth=1.2, label="SPY annual return")
        for bar, val in zip(spy_bars, spy_vals):
            if not np.isnan(val):
                h = bar.get_height()
                offset = 1.2 if h >= 0 else -3
                ax.text(bar.get_x() + bar.get_width() / 2, h + offset,
                        f"{val:+.1f}%", ha="center",
                        va="bottom" if h >= 0 else "top", fontsize=7.5, color="#E65100")

    ax.axhline(0, color="black", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(summary["year"].astype(str))
    ax.set_xlabel("Year")
    ax.set_ylabel("Annual Return (%)")
    ax.set_title(f"Annual Return per Year - {label} vs SPY")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%+.0f%%"))
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "yearly_roi_bar.png")
    plt.close(fig)
    print("  [OK] yearly_roi_bar.png")


def chart_yearly_win_rate(ts: pd.DataFrame, label: str, out_dir: Path, spy: pd.DataFrame):
    """Grouped bar chart: per year, % of tickers gaining vs losing.
    SPY annual return shown as a text annotation above each year group.
    """
    annual_gain = _compute_annual_gain(ts)
    summary = annual_gain.groupby("year")[["annual_roi"]].apply(
        lambda g: pd.Series({
            "win_pct": 100 * (g["annual_roi"] > 0).mean(),
            "lose_pct": 100 * (g["annual_roi"] <= 0).mean(),
        }),
        include_groups=False,
    ).reset_index()

    spy_returns = _spy_annual_returns(spy) if not spy.empty else {}
    years = summary["year"].astype(str).tolist()
    x = np.arange(len(years))
    w = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    bars_win = ax.bar(x - w / 2, summary["win_pct"], w, label="Tickers gained", color=GREEN, alpha=0.85)
    bars_lose = ax.bar(x + w / 2, summary["lose_pct"], w, label="Tickers lost/flat", color=RED, alpha=0.85)
    for bar in list(bars_win) + list(bars_lose):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.8,
                f"{h:.0f}%", ha="center", va="bottom", fontsize=8)

    # Annotate SPY annual return above each year
    if spy_returns:
        for xi, yr in zip(x, summary["year"]):
            val = spy_returns.get(yr, np.nan)
            if not np.isnan(val):
                color = "#2e7d32" if val >= 0 else "#b71c1c"
                ax.text(xi, 107, f"SPY {val:+.1f}%", ha="center", va="bottom",
                        fontsize=8, color=color, fontweight="bold")
        # Add a dummy handle for the legend
        from matplotlib.lines import Line2D
        spy_handle = Line2D([0], [0], color="none", label="SPY annual return shown above bars")
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles + [spy_handle], labels + ["SPY annual return shown above bars"],
                  loc="lower right", fontsize=8)
    else:
        ax.legend()

    ax.set_xticks(x)
    ax.set_xticklabels(summary["year"].astype(str))
    ax.set_ylabel("Percentage of Tickers (%)")
    ax.set_ylim(0, 120)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.set_title(f"Annual Win Rate by Year - {label} vs SPY")
    fig.tight_layout()
    fig.savefig(out_dir / "yearly_win_rate.png")
    plt.close(fig)
    print("  [OK] yearly_win_rate.png")


def chart_strategy_vs_bah(summaries: dict, bah: pd.DataFrame, spy_cumul: float, out_dir: Path):
    """Horizontal bar chart: strategy ROI vs buy-and-hold return, one row per ticker.

    Tickers sorted by buy-and-hold return. Bars are paired so the two metrics
    are directly comparable on the same scale.
    """
    key = next(iter(summaries))
    strat = summaries[key][["ticker", "roi"]].copy()
    merged = strat.merge(bah, on="ticker").sort_values("bah_return")

    n = len(merged)
    fig, ax = plt.subplots(figsize=(10, max(8, n * 0.28)))

    y = np.arange(n)
    h = 0.38

    # Buy-and-hold bars
    bah_colors = [GREEN if v >= 0 else RED for v in merged["bah_return"]]
    ax.barh(y + h / 2, merged["bah_return"], h, color=bah_colors,
            alpha=0.55, label="Buy-and-hold return")

    # Strategy bars
    strat_colors = [GREEN if v >= 0 else RED for v in merged["roi"]]
    ax.barh(y - h / 2, merged["roi"], h, color=strat_colors,
            alpha=0.85, label="Strategy ROI")

    # SPY reference line
    ax.axvline(spy_cumul, color="#FF9800", linewidth=1.5, linestyle="--",
               label=f"SPY {spy_cumul:+.1f}%")
    ax.axvline(0, color="black", linewidth=0.8, alpha=0.4)

    ax.set_yticks(y)
    ax.set_yticklabels(merged["ticker"].str.replace(".US", "", regex=False), fontsize=7)
    ax.set_xlabel("Total Return over Backtest Period (%)")
    ax.set_title(
        f"Strategy ROI vs Buy-and-Hold per Ticker\n"
        f"Strategy beats B&H on {(merged['roi'] > merged['bah_return']).sum()}/{n} tickers"
    )
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%+.0f%%"))
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_dir / "strategy_vs_bah.png", bbox_inches="tight")
    plt.close(fig)
    print("  [OK] strategy_vs_bah.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate backtest result charts")
    parser.add_argument(
        "--data-dir", type=Path, default=DEFAULT_DATA_DIR,
        help="Path to complete-backtest-results directory",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=OUT_DIR,
        help="Output directory for charts",
    )
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    out_dir: Path = args.out_dir

    if not data_dir.exists():
        print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output -> {out_dir}\n")

    # ------------------------------------------------------------------
    # Load NN simulation summaries
    # ------------------------------------------------------------------
    sim_dirs = {
        NN_SP500_DIR: data_dir / NN_SP500_DIR,
        NN_DOW_DIR: data_dir / NN_DOW_DIR,
    }
    summaries = {}
    trades = {}
    timeseries = {}
    for key, sim_dir in sim_dirs.items():
        if not sim_dir.exists():
            print(f"  [!] Skipping missing directory: {sim_dir.name}")
            continue
        output_md = sim_dir / "output.md"
        inv_csvs = list(sim_dir.glob("*_investments.csv"))
        if not output_md.exists() and not inv_csvs:
            print(f"  [!] Skipping empty directory: {sim_dir.name}")
            continue
        print(f"Loading {MODEL_LABELS[key]} ...")
        if output_md.exists():
            summaries[key] = parse_output_md(output_md)
            print(f"  {len(summaries[key])} tickers parsed from output.md")
        if inv_csvs:
            trades[key] = load_all_investments(sim_dir)
            print(f"  {len(trades[key])} trades loaded from investments CSVs")
        data_csvs = list(sim_dir.glob("*_data.csv"))
        if data_csvs:
            timeseries[key] = load_all_timeseries(sim_dir)
            print(f"  {len(timeseries[key])} time series rows loaded")

    # ------------------------------------------------------------------
    # Load SPY baseline from database
    # ------------------------------------------------------------------
    print("\nLoading SPY baseline from database ...")
    spy_df = load_spy_baseline("2021-01-01", "2024-12-31")
    if spy_df.empty:
        print("  [!] SPY data not found in database - baseline will be omitted")
    else:
        print(f"  {len(spy_df)} daily SPY closes loaded "
              f"({spy_df['date'].min().date()} to {spy_df['date'].max().date()})")

    # ------------------------------------------------------------------
    # Load buy-and-hold returns for all strategy tickers
    # ------------------------------------------------------------------
    bah_df = pd.DataFrame()
    if summaries:
        all_tickers = list(next(iter(summaries.values()))["ticker"])
        print(f"\nLoading buy-and-hold returns for {len(all_tickers)} tickers ...")
        bah_df = load_bah_returns(all_tickers, "2021-01-01", "2024-12-31")
        print(f"  {len(bah_df)} tickers loaded from database")

    # ------------------------------------------------------------------
    # Load pattern recognition data
    # ------------------------------------------------------------------
    pattern_csv = data_dir / PATTERN_CSV
    pattern_df = None
    if pattern_csv.exists():
        print(f"\nLoading pattern recognition data ...")
        pattern_df = pd.read_csv(pattern_csv)
        print(f"  {len(pattern_df)} rows, {pattern_df['ticker'].nunique()} tickers")
    else:
        print(f"  [!] Pattern CSV not found: {pattern_csv}")

    # ------------------------------------------------------------------
    # Generate charts
    # ------------------------------------------------------------------
    print("\nGenerating charts ...")

    spy_cumul = float((spy_df["cumul_roi"].iloc[-1]) if not spy_df.empty else 0)

    if summaries:
        chart_roi_distribution(summaries, out_dir)
        chart_wallet_distribution(summaries, out_dir)
        chart_win_rate(summaries, out_dir)
        chart_roi_vs_trades(summaries, out_dir)
        if not bah_df.empty:
            chart_strategy_vs_bah(summaries, bah_df, spy_cumul, out_dir)

    if trades and any(len(t) > 0 for t in trades.values()):
        nonempty = {k: v for k, v in trades.items() if len(v) > 0}
        chart_trade_pnl_distribution(nonempty, out_dir)
        chart_holding_period(nonempty, out_dir)
        chart_trade_win_rate(nonempty, out_dir)

    if pattern_df is not None:
        chart_pattern_directional_accuracy(pattern_df, out_dir)
        chart_pattern_mse_comparison(pattern_df, out_dir)
        chart_pattern_accuracy_by_ticker(pattern_df, out_dir)

    # Time-series charts (use first available model with data)
    for key, ts_df in timeseries.items():
        if ts_df.empty:
            continue
        label = MODEL_LABELS[key]
        chart_roi_over_time(ts_df, label, out_dir, spy_df)
        chart_yearly_roi(ts_df, label, out_dir, spy_df)
        chart_yearly_win_rate(ts_df, label, out_dir, spy_df)
        break  # Only one model has time series data

    print(f"\nDone. Charts saved to: {out_dir}")


if __name__ == "__main__":
    main()
