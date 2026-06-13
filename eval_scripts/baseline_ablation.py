#!/usr/bin/env python3
"""Ablation study: technical-only -> GPR -> GPT sentiment -> structured geo features.

Baselines:
  B0  37 technical + macro features (current XGBoostInvestor)
  B1  B0 + gpr_index scalar (Caldara-Iacoviello)
  B2  B0 + GPT-4o-mini headline sentiment score only
  B3  B0 + all 7 structured geo features from geo_features.py

Usage:
  python eval_scripts/baseline_ablation.py
  python eval_scripts/baseline_ablation.py --baselines B0 B1 --tickers SPY QQQ
  python eval_scripts/baseline_ablation.py --skip-llm   # skip B2/B3

Requirements: run from project root. Needs yfinance, xgboost, scikit-learn,
scipy, matplotlib in the active environment. Set OPENAI_API_KEY and
NEWSAPI_KEY for B2/B3.
"""

import argparse
import logging
import os
import sys
import time
import warnings
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fastapi"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from xg_boost_investor.XGBoostInvestor import XGBoostInvestor
from xg_boost_investor.Features import build_full_features

warnings.filterwarnings("ignore")
LOGGER = logging.getLogger("ablation")


def _setup_logging(log_dir: Path) -> Path:
    """Configure root logger to write timestamped lines to both stdout and a file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"ablation_{date.today():%Y-%m-%d}.log"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(log_file)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)
    return log_file


def _with_retry(fn, *args, retries: int = 3, base: float = 2.0, label: str = "call", **kwargs):
    """Run `fn` with exponential backoff retry on exception."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                wait = base * (2 ** attempt)
                LOGGER.warning("%s failed (attempt %d/%d): %s — retrying in %.1fs",
                               label, attempt + 1, retries + 1, exc, wait)
                time.sleep(wait)
            else:
                LOGGER.error("%s failed after %d retries: %s", label, retries + 1, exc)
    raise last_exc

DEFAULT_TICKERS = ["SPY", "QQQ", "LMT", "XOM", "TSM", "BA", "CVX"]
PERIODS = {
    "2022": (date(2022, 1, 1), date(2022, 12, 31)),
    "Q1_2025": (date(2025, 1, 1), date(2025, 3, 31)),
}
TRAIN_WINDOW = 252
DEFAULT_HORIZON = 5

GPR_DATA_URL = "https://www.matteoiacoviello.com/gpr_files/gpr.xlsx"
GPR_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "gpr_daily.csv"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def download_gpr_data() -> pd.Series | None:
    """Download and interpolate Caldara-Iacoviello GPR index to daily frequency."""
    if GPR_CSV_PATH.exists():
        df = pd.read_csv(GPR_CSV_PATH, index_col=0, parse_dates=True)
        return df["gpr_index"]

    print("Downloading GPR data from Caldara-Iacoviello...")
    try:
        import requests

        resp = requests.get(GPR_DATA_URL, timeout=30)
        resp.raise_for_status()
        from io import BytesIO
        df = pd.read_excel(BytesIO(resp.content), engine="openpyxl")
    except Exception as exc:
        print(f"  Could not download GPR data: {exc}")
        print("  B1 will use zeros for gpr_index.")
        return None

    gpr_col = None
    for col in df.columns:
        if "gpr" in str(col).lower() and "gprd" not in str(col).lower():
            gpr_col = col
            break
    if gpr_col is None:
        print("  Could not identify GPR column in downloaded file.")
        return None

    if "year" in df.columns.str.lower() and "month" in df.columns.str.lower():
        year_col = df.columns[df.columns.str.lower() == "year"][0]
        month_col = df.columns[df.columns.str.lower() == "month"][0]
        df["date"] = pd.to_datetime(df[[year_col, month_col]].rename(
            columns={year_col: "year", month_col: "month"}
        ).assign(day=1))
        df = df.set_index("date")[[gpr_col]].rename(columns={gpr_col: "gpr_index"})
    else:
        df = df.rename(columns={gpr_col: "gpr_index"}).set_index(df.columns[0])

    df = df[["gpr_index"]].dropna()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    full_index = pd.date_range(df.index.min(), date.today(), freq="D")
    df = df.reindex(full_index).interpolate("linear")
    df.index.name = "date"

    GPR_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(GPR_CSV_PATH)
    print(f"  Saved GPR data to {GPR_CSV_PATH}")
    return df["gpr_index"]


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, gpr_series: pd.Series | None) -> dict:
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    y_t = y_true[valid]
    y_p = y_pred[valid]

    if len(y_t) == 0:
        return {"MAE": np.nan, "RMSE": np.nan, "MAPE": np.nan, "DA": np.nan, "gers": np.nan}

    mae = float(np.mean(np.abs(y_t - y_p)))
    rmse = float(np.sqrt(np.mean((y_t - y_p) ** 2)))
    nonzero = y_t != 0
    mape = float(np.mean(np.abs((y_t[nonzero] - y_p[nonzero]) / y_t[nonzero]))) if np.any(nonzero) else np.nan
    da = float(np.mean(np.sign(y_t) == np.sign(y_p)))

    gers_val = np.nan
    if gpr_series is not None and len(gpr_series) >= len(y_t):
        try:
            from gers import compute_gers
            aligned_gpr = gpr_series.iloc[-len(y_t):]
            gers_val = compute_gers(y_t, y_p, aligned_gpr)
        except Exception:
            pass

    return {"MAE": mae, "RMSE": rmse, "MAPE": mape, "DA": da, "gers": gers_val}


def _diebold_mariano(e1: np.ndarray, e2: np.ndarray) -> float:
    """Diebold-Mariano test statistic (H0: equal forecast accuracy)."""
    d = e1 ** 2 - e2 ** 2
    valid = np.isfinite(d)
    if valid.sum() < 2:
        return np.nan
    d = d[valid]
    t_stat, _ = stats.ttest_1samp(d, 0)
    return float(t_stat)


def _build_geo_features_df(tickers: list[str], start: date, end: date, baseline: str, geo_extractor=None) -> pd.DataFrame | None:
    if baseline == "B1":
        if not GPR_CSV_PATH.exists():
            LOGGER.warning("GPR file not found; using zeros for gpr_index in B1")
            date_range = pd.date_range(start, end, freq="D")
            return pd.DataFrame({"Date": date_range, "gpr_index": 0.0})
        gpr = pd.read_csv(GPR_CSV_PATH, index_col=0, parse_dates=True)["gpr_index"]
        date_range = pd.date_range(start, end, freq="D")
        gpr_daily = gpr.reindex(date_range).interpolate("linear")
        result = pd.DataFrame({"Date": gpr_daily.index, "gpr_index": gpr_daily.values})
        return result

    if baseline in ("B2", "B3") and geo_extractor is not None:
        rows = []
        current = start
        while current <= end:
            try:
                feats = geo_extractor.get_geo_features("SPY", current.isoformat())
                row = {"Date": pd.Timestamp(current)}
                if baseline == "B2":
                    row["geo_sentiment_score"] = feats.get("geo_sentiment_score", 0.0)
                else:
                    row.update(feats)
                rows.append(row)
            except Exception:
                pass
            current += timedelta(days=1)
        if rows:
            return pd.DataFrame(rows)

    if baseline == "B2b":
        try:
            import requests as _req
            from finbert_features import aggregate_daily_sentiment
            newsapi_key = os.getenv("NEWSAPI_KEY") or os.getenv("NEWSAPI_API_KEY")
            rows = []
            current = start
            while current <= end:
                headlines: list[str] = []
                if newsapi_key:
                    try:
                        resp = _req.get(
                            "https://newsapi.org/v2/everything",
                            params={"q": "stock market geopolitical", "from": current.isoformat(),
                                    "to": current.isoformat(), "language": "en",
                                    "sortBy": "relevancy", "pageSize": 5},
                            headers={"X-Api-Key": newsapi_key},
                            timeout=10,
                        )
                        articles = resp.json().get("articles", [])
                        headlines = [a.get("title", "") for a in articles if a.get("title")]
                    except Exception:
                        pass
                score = aggregate_daily_sentiment(headlines)
                rows.append({"Date": pd.Timestamp(current), "finbert_sentiment": score})
                current += timedelta(days=1)
            if rows:
                return pd.DataFrame(rows)
        except ImportError:
            print("  finbert_features not available - skipping B2b")
    return None


def _csv_row(record: dict) -> dict:
    """Strip in-memory-only columns (those prefixed with '_') from a record."""
    return {k: v for k, v in record.items() if not k.startswith("_")}


def _append_record(record: dict, csv_path: Path) -> None:
    """Append one row to the CSV checkpoint file, writing header if new."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([_csv_row(record)])
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    df.to_csv(csv_path, mode="a", header=write_header, index=False)


def _load_completed(csv_path: Path) -> set[tuple[str, str, str]]:
    """Return set of (period, ticker, baseline) triples already in the checkpoint."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return set()
    try:
        df = pd.read_csv(csv_path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return set()
    if df.empty or not {"period", "ticker", "baseline"}.issubset(df.columns):
        return set()
    return set(zip(df["period"].astype(str), df["ticker"].astype(str), df["baseline"].astype(str)))


def run_ablation(
    tickers: list[str],
    baselines: list[str],
    skip_llm: bool = False,
    csv_path: Path | None = None,
    max_failures: int = 20,
) -> pd.DataFrame:
    gpr_series = download_gpr_data()

    geo_extractor = None
    if not skip_llm and any(b in baselines for b in ("B2", "B3")):
        try:
            from geo_features import GeoFeatureExtractor
            geo_extractor = GeoFeatureExtractor()
        except ImportError:
            LOGGER.warning("geo_features.py not found - skipping B2/B3")
            baselines = [b for b in baselines if b not in ("B2", "B3")]

    if csv_path is None:
        csv_path = RESULTS_DIR / "ablation_results.csv"
    completed = _load_completed(csv_path)
    if completed:
        LOGGER.info("Resuming from %d completed rows in %s", len(completed), csv_path)

    total = len(PERIODS) * len(tickers) * len(baselines)
    iteration = 0
    consecutive_failures = 0
    run_start = time.time()
    records: list[dict] = []  # in-memory only, used for Diebold-Mariano vs B0 in same run
    step = max(1, DEFAULT_HORIZON // 2)

    for period_name, (period_start, period_end) in PERIODS.items():
        LOGGER.info("== Period: %s (%s - %s) ==", period_name, period_start, period_end)

        for ticker in tickers:
            # Skip the expensive feature build if every baseline for this ticker is done
            if all((period_name, ticker, b) in completed for b in baselines):
                LOGGER.info("  %s/%s: all baselines complete, skipping feature build",
                            period_name, ticker)
                iteration += len(baselines)
                continue

            LOGGER.info("  Ticker: %s", ticker)

            train_start = period_start - timedelta(days=TRAIN_WINDOW + 60)
            try:
                full_features, full_labels = _with_retry(
                    build_full_features, [ticker],
                    start_date=train_start, end_date=period_end,
                    retries=3, base=5.0, label=f"build_full_features({ticker})",
                )
            except Exception as exc:
                LOGGER.error("Feature build failed for %s after retries: %s", ticker, exc)
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    LOGGER.error("Hit --max-failures=%d limit, aborting", max_failures)
                    break
                iteration += len(baselines)
                continue

            full_features["Date"] = pd.to_datetime(full_features["Date"])

            period_mask = (
                (full_features["Date"] >= pd.Timestamp(period_start))
                & (full_features["Date"] <= pd.Timestamp(period_end))
            )
            eval_indices = full_features.index[period_mask].tolist()

            if len(eval_indices) < step * 5:
                LOGGER.warning("Not enough eval data for %s in %s", ticker, period_name)
                iteration += len(baselines)
                continue

            for baseline in baselines:
                iteration += 1
                if (period_name, ticker, baseline) in completed:
                    LOGGER.info("  [%d/%d] period=%s ticker=%s baseline=%s — already complete, skipping",
                                iteration, total, period_name, ticker, baseline)
                    continue

                elapsed = time.time() - run_start
                LOGGER.info("  [%d/%d] period=%s ticker=%s baseline=%s elapsed=%.0fs",
                            iteration, total, period_name, ticker, baseline, elapsed)

                geo_df = None
                if baseline != "B0":
                    geo_df = _build_geo_features_df(
                        [ticker], period_start, period_end, baseline, geo_extractor
                    )
                    if geo_df is None and baseline in ("B1", "B2", "B3"):
                        LOGGER.warning("    No geo data for %s, skipping", baseline)
                        continue

                y_true_all = []
                y_pred_all = []

                eval_dates = full_features.loc[eval_indices, "Date"].values
                window_starts = list(range(0, len(eval_indices) - DEFAULT_HORIZON, step))

                for wi in window_starts:
                    eval_idx = eval_indices[wi]
                    eval_date = full_features.loc[eval_idx, "Date"]

                    train_mask = full_features["Date"] < eval_date
                    train_df = full_features[train_mask].tail(TRAIN_WINDOW).copy()
                    train_labels = full_labels[train_df.index]

                    if len(train_df) < 30:
                        continue

                    if geo_df is not None:
                        try:
                            train_df = train_df.merge(geo_df, on="Date", how="left")
                            geo_cols = [c for c in geo_df.columns if c != "Date"]
                            train_df[geo_cols] = train_df[geo_cols].fillna(0)
                        except Exception:
                            pass

                    test_slice = eval_indices[wi : wi + DEFAULT_HORIZON]
                    test_df = full_features.loc[test_slice].copy()
                    test_labels = full_labels[test_df.index]

                    if geo_df is not None:
                        try:
                            test_df = test_df.merge(geo_df, on="Date", how="left")
                            test_df[geo_cols] = test_df[geo_cols].fillna(0)
                        except Exception:
                            pass

                    xgb = XGBoostInvestor()
                    try:
                        X_train, y_train = xgb.prepare_training(train_df.copy(), train_labels.copy())
                        xgb.build_model()
                        xgb.train(X_train, y_train)
                        split_idx = int(len(X_train) * 0.8)
                        xgb.calibrate(X_train[split_idx:], y_train[split_idx:])

                        dummy = pd.DataFrame({"ret_1d": [0.0] * len(test_df)})
                        X_test, y_test, _, _ = xgb.prepare_predictions(test_df.copy(), dummy)
                        y_pred = xgb.predict(X_test)

                        y_true_all.extend(test_labels.values[:len(y_pred)])
                        y_pred_all.extend(y_pred)
                    except Exception as exc:
                        LOGGER.warning("  window wi=%d skipped: %s", wi, exc)
                        continue

                if len(y_true_all) == 0:
                    continue

                y_true_arr = np.array(y_true_all)
                y_pred_arr = np.array(y_pred_all)

                gpr_slice = None
                if gpr_series is not None:
                    period_dates = pd.date_range(period_start, period_end, freq="D")
                    gpr_slice = gpr_series.reindex(period_dates).interpolate("linear")
                    if len(gpr_slice) > len(y_true_arr):
                        gpr_slice = gpr_slice.iloc[-len(y_true_arr):]

                metrics = _compute_metrics(y_true_arr, y_pred_arr, gpr_slice)

                dm_stat = np.nan
                if baseline != "B0":
                    b0_key = (ticker, period_name, "B0")
                    b0_pred = next(
                        (r.get("_y_pred") for r in records if (r["ticker"], r["period"], r["baseline"]) == b0_key),
                        None,
                    )
                    if b0_pred is not None:
                        e_b0 = np.array(b0_pred) - y_true_arr[:len(b0_pred)]
                        e_bk = y_pred_arr[:len(b0_pred)] - y_true_arr[:len(b0_pred)]
                        dm_stat = _diebold_mariano(e_b0, e_bk)

                record = {
                    "baseline": baseline,
                    "ticker": ticker,
                    "period": period_name,
                    "n_samples": len(y_true_arr),
                    "MAE": metrics["MAE"],
                    "RMSE": metrics["RMSE"],
                    "MAPE": metrics["MAPE"],
                    "DA": metrics["DA"],
                    "gers": metrics["gers"],
                    "DM_vs_B0": dm_stat,
                    "_y_pred": y_pred_arr.tolist(),
                }
                records.append(record)
                _append_record(record, csv_path)
                completed.add((period_name, ticker, baseline))
                consecutive_failures = 0
                LOGGER.info("      DA=%.4f MAE=%.6f n=%d", metrics["DA"], metrics["MAE"], len(y_true_arr))

            if consecutive_failures >= max_failures:
                break
        if consecutive_failures >= max_failures:
            break

    # Return cumulative CSV contents (so plotting in main() uses both resumed and new rows)
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def plot_results(df: pd.DataFrame, output_dir: Path) -> None:
    if df.empty:
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    metric_cols = ["DA", "MAE", "RMSE", "MAPE", "gers"]

    for period in df["period"].unique():
        fig, axes = plt.subplots(1, len(metric_cols), figsize=(20, 5))
        period_df = df[df["period"] == period]

        for ax, metric in zip(axes, metric_cols):
            means = period_df.groupby("baseline")[metric].mean()
            means = means[means.index.isin(["B0", "B1", "B2", "B3", "B2b"])]
            if means.empty:
                ax.set_visible(False)
                continue
            colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2"]
            bars = ax.bar(means.index, means.values, color=colors[:len(means)])
            ax.set_title(f"{metric} ({period})")
            ax.set_xlabel("Baseline")
            ax.set_ylabel(metric)
            for bar in bars:
                h = bar.get_height()
                if np.isfinite(h):
                    ax.text(bar.get_x() + bar.get_width() / 2, h, f"{h:.4f}", ha="center", va="bottom", fontsize=8)

        fig.suptitle(f"Ablation Study - {period}", fontsize=14)
        plt.tight_layout()
        out_path = output_dir / f"ablation_{period}.png"
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved chart: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="XGBoost ablation study for geopolitical features")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--baselines", nargs="+", default=["B0", "B1", "B2", "B3"], choices=["B0", "B1", "B2", "B3", "B2b"])
    parser.add_argument("--skip-llm", action="store_true", help="Skip B2 and B3 (no LLM calls)")
    parser.add_argument("--output", type=Path, default=RESULTS_DIR)
    parser.add_argument("--max-failures", type=int, default=20,
                        help="Abort after N consecutive iteration-level failures")
    parser.add_argument("--reset", action="store_true",
                        help="Delete the existing ablation_results.csv and start fresh")
    args = parser.parse_args()

    log_file = _setup_logging(args.output)
    LOGGER.info("Tickers: %s", args.tickers)
    LOGGER.info("Baselines: %s", args.baselines)
    LOGGER.info("Periods: %s", list(PERIODS.keys()))
    LOGGER.info("Log file: %s", log_file)

    csv_path = args.output / "ablation_results.csv"
    if args.reset and csv_path.exists():
        LOGGER.info("--reset: removing existing %s", csv_path)
        csv_path.unlink()

    df = run_ablation(
        tickers=args.tickers,
        baselines=args.baselines,
        skip_llm=args.skip_llm,
        csv_path=csv_path,
        max_failures=args.max_failures,
    )

    if df.empty:
        LOGGER.warning("No results generated.")
        return

    LOGGER.info("Saved: %s", csv_path)
    LOGGER.info("Summary (mean across tickers):")
    summary = df.groupby(["baseline", "period"])[["DA", "MAE", "RMSE", "MAPE", "gers"]].mean()
    LOGGER.info("\n%s", summary.to_string())

    plot_results(df, args.output)


if __name__ == "__main__":
    main()
