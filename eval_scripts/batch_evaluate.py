#!/usr/bin/env python3
"""
Batch LLM Evaluation across multiple weekly time frames.

Iterates backward from the most recent Friday in the database,
evaluating each 7-day window N times to measure both quality and consistency.

Usage:
  python batch_evaluate.py --api-url http://localhost:8080 --weeks 4 --trials 3
  python batch_evaluate.py --api-url http://localhost:8080 --weeks 8 --trials 1 --skip-ragas
"""

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Import the single-week evaluation machinery
from evaluate_weekly_insights import (
    RAGAS_AVAILABLE,
    _build_ragas_contexts,
    _context_pct_changes,
    _context_symbols,
    _normalize_symbol,
    metric_hedge_language,
    metric_numerical_faithfulness,
    metric_output_completeness,
    metric_symbol_accuracy,
    metric_symbol_coverage,
    run_ragas,
)

METRIC_KEYS = [
    "symbol_accuracy",
    "symbol_coverage",
    "numerical_faithfulness",
    "hedge_language",
    "output_completeness",
]

RAGAS_KEYS = ["faithfulness", "answer_relevancy"]


# ---------------------------------------------------------------------------
# Discover available week end-dates by querying the API
# ---------------------------------------------------------------------------
def discover_week_ends(base_url: str, num_weeks: int) -> list[str]:
    """Walk backward from the latest data to find N week-ending Fridays."""
    base_url = base_url.rstrip("/")
    # First, fetch the latest week to learn the end date
    resp = requests.get(f"{base_url}/api/weekly-alerts", timeout=30)
    resp.raise_for_status()
    latest_end = resp.json()["end"]  # ISO date string like "2026-02-27"

    from datetime import date as _date
    end = _date.fromisoformat(latest_end)
    week_ends = []
    for _ in range(num_weeks):
        week_ends.append(end.isoformat())
        end -= timedelta(days=7)

    return week_ends


# ---------------------------------------------------------------------------
# Run one evaluation (single week, single trial)
# ---------------------------------------------------------------------------
def evaluate_one(base_url: str, end_date: str, num_tolerance: float,
                 skip_ragas: bool = False) -> dict:
    """Fetch data for one week and compute custom + Ragas metrics."""
    base_url = base_url.rstrip("/")
    params = {"end_date": end_date}

    insights_resp = requests.get(
        f"{base_url}/api/weekly-insights", params=params, timeout=120,
    )
    insights_resp.raise_for_status()
    insights = insights_resp.json()

    alerts_resp = requests.get(
        f"{base_url}/api/weekly-alerts", params=params, timeout=30,
    )
    alerts_resp.raise_for_status()
    alerts_data = alerts_resp.json()

    market_insights: list[str] = insights.get("market_insights") or []
    event_impacts: list[str] = insights.get("event_impacts") or []
    alerts: list[dict] = alerts_data.get("alerts") or []
    events: list[dict] = insights.get("events") or []

    if not market_insights:
        note = insights.get("note", "")
        return {"error": f"No market_insights: {note}", "date_range": end_date}

    output_text = " ".join(market_insights + event_impacts)
    ctx_symbols = _context_symbols(alerts)
    for entry in alerts_data.get("benchmarks") or []:
        if isinstance(entry, dict) and entry.get("symbol"):
            ctx_symbols.add(_normalize_symbol(entry["symbol"]))
    ctx_pcts = _context_pct_changes(alerts)

    date_range = f"{insights.get('start', '?')} to {insights.get('end', '?')}"

    metrics = {
        "symbol_accuracy": metric_symbol_accuracy(output_text, ctx_symbols),
        "symbol_coverage": metric_symbol_coverage(output_text, ctx_symbols),
        "numerical_faithfulness": metric_numerical_faithfulness(
            output_text, ctx_pcts, tolerance=num_tolerance
        ),
        "hedge_language": metric_hedge_language(event_impacts),
        "output_completeness": metric_output_completeness(market_insights, event_impacts),
    }

    result = {
        "date_range": date_range,
        "model": insights.get("model") or "unknown",
        "metrics": metrics,
        "raw": {
            "market_insights": market_insights,
            "event_impacts": event_impacts,
        },
    }

    # Ragas per-bullet evaluation
    if not skip_ragas and RAGAS_AVAILABLE:
        ragas_result = run_ragas(
            market_insights=market_insights,
            event_impacts=event_impacts,
            date_range=date_range,
            alerts=alerts,
            events=events,
        )
        result["ragas_metrics"] = ragas_result

    return result


# ---------------------------------------------------------------------------
# Aggregate across trials for one week
# ---------------------------------------------------------------------------
def aggregate_trials(trial_results: list[dict]) -> dict:
    """Compute mean and stdev of metric scores across trials."""
    scores_by_metric: dict[str, list[float]] = {k: [] for k in METRIC_KEYS}

    for trial in trial_results:
        if "error" in trial:
            continue
        for key in METRIC_KEYS:
            score = trial["metrics"][key].get("score")
            if score is not None:
                scores_by_metric[key].append(score)

    summary = {}
    for key, vals in scores_by_metric.items():
        if vals:
            summary[key] = {
                "mean": round(statistics.mean(vals), 3),
                "stdev": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0,
                "min": round(min(vals), 3),
                "max": round(max(vals), 3),
                "n": len(vals),
            }
        else:
            summary[key] = {"mean": None, "stdev": None, "n": 0}

    # Aggregate Ragas scores
    ragas_scores: dict[str, list[float]] = {k: [] for k in RAGAS_KEYS}
    ragas_costs: dict[str, float] = {
        "llm_input_tokens": 0, "llm_output_tokens": 0,
        "embedding_tokens": 0, "total_cost_usd": 0.0,
    }
    for trial in trial_results:
        ragas = trial.get("ragas_metrics", {})
        if "error" in ragas:
            continue
        overall = ragas.get("overall", {})
        for key in RAGAS_KEYS:
            val = overall.get(key)
            if val is not None:
                ragas_scores[key].append(val)
        cost = ragas.get("cost", {})
        for ck in ragas_costs:
            ragas_costs[ck] += cost.get(ck, 0)

    ragas_summary = {}
    for key, vals in ragas_scores.items():
        if vals:
            ragas_summary[key] = {
                "mean": round(statistics.mean(vals), 3),
                "stdev": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0,
                "min": round(min(vals), 3),
                "max": round(max(vals), 3),
                "n": len(vals),
            }
        else:
            ragas_summary[key] = {"mean": None, "stdev": None, "n": 0}

    if any(ragas_scores.values()):
        summary["ragas"] = ragas_summary
        summary["ragas_cost"] = {k: round(v, 6) for k, v in ragas_costs.items()}

    return summary


# ---------------------------------------------------------------------------
# Print summary table
# ---------------------------------------------------------------------------
def print_summary(all_weeks: list[dict], has_ragas: bool = False) -> None:
    print("\n" + "=" * 100)
    print("  Batch LLM Evaluation Summary")
    print("=" * 100)

    header = f"  {'Week':<25} {'SymAcc':>7} {'SymCov':>7} {'NumFth':>7} {'Hedge':>7} {'Compl':>7}"
    if has_ragas:
        header += f" {'Faith':>7} {'Relev':>7}"
    print(header)
    print("  " + "-" * (73 + (16 if has_ragas else 0)))

    for week in all_weeks:
        date_range = week["date_range"]
        agg = week["aggregate"]
        row = f"  {date_range:<25}"
        for key in METRIC_KEYS:
            val = agg[key]["mean"]
            if val is not None:
                row += f" {val:>6.1%}"
            else:
                row += f" {'N/A':>7}"
        if has_ragas:
            ragas_agg = agg.get("ragas", {})
            for key in RAGAS_KEYS:
                val = ragas_agg.get(key, {}).get("mean")
                if val is not None:
                    row += f" {val:>6.1%}"
                else:
                    row += f" {'N/A':>7}"
        if week.get("trials", 1) > 1:
            row += f"  (n={week['trials']})"
        print(row)

    # Overall averages
    print("  " + "-" * (73 + (16 if has_ragas else 0)))
    overall: dict[str, list[float]] = {k: [] for k in METRIC_KEYS + RAGAS_KEYS}
    for week in all_weeks:
        for key in METRIC_KEYS:
            val = week["aggregate"][key]["mean"]
            if val is not None:
                overall[key].append(val)
        for key in RAGAS_KEYS:
            val = week["aggregate"].get("ragas", {}).get(key, {}).get("mean")
            if val is not None:
                overall[key].append(val)

    row = f"  {'OVERALL MEAN':<25}"
    for key in METRIC_KEYS:
        vals = overall[key]
        row += f" {statistics.mean(vals):>6.1%}" if vals else f" {'N/A':>7}"
    if has_ragas:
        for key in RAGAS_KEYS:
            vals = overall[key]
            row += f" {statistics.mean(vals):>6.1%}" if vals else f" {'N/A':>7}"
    print(row)

    # Total cost
    total_cost = sum(
        w["aggregate"].get("ragas_cost", {}).get("total_cost_usd", 0)
        for w in all_weeks
    )
    if total_cost > 0:
        print(f"\n  Total Ragas evaluation cost: ${total_cost:.4f}")

    print("=" * 100)


# ---------------------------------------------------------------------------
# GERS summary (reads ablation_results.csv if available)
# ---------------------------------------------------------------------------
def print_gers_summary(ablation_csv: str | None = None) -> None:
    """Print GERS scores from ablation_results.csv if it exists."""
    import importlib.util

    if ablation_csv is None:
        default_path = Path(__file__).resolve().parent.parent / "results" / "ablation_results.csv"
        ablation_csv = str(default_path) if default_path.exists() else None

    if ablation_csv is None or not Path(ablation_csv).exists():
        return

    if importlib.util.find_spec("pandas") is None:
        return

    try:
        import pandas as pd
        df = pd.read_csv(ablation_csv)
        if "gers" not in df.columns or "baseline" not in df.columns:
            return

        print("\n" + "=" * 60)
        print("  GERS (Geopolitical Event Response Score) by Baseline")
        print("=" * 60)
        summary = df.groupby(["baseline", "period"])["gers"].mean().unstack(fill_value=float("nan"))
        print(summary.to_string())
        print("=" * 60)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch LLM evaluation across multiple weeks.",
    )
    parser.add_argument(
        "--api-url", required=True, metavar="URL",
        help="Base URL of running backend",
    )
    parser.add_argument(
        "--weeks", type=int, default=4,
        help="Number of weeks to evaluate (default: 4)",
    )
    parser.add_argument(
        "--trials", type=int, default=1,
        help="Number of trials per week (default: 1)",
    )
    parser.add_argument(
        "--output", metavar="FILE", default="batch_report.json",
        help="Output JSON file (default: batch_report.json)",
    )
    parser.add_argument(
        "--num-tolerance", type=float, default=1.5,
        help="Tolerance for numerical faithfulness (default: 1.5 pp)",
    )
    parser.add_argument(
        "--delay", type=float, default=2.0,
        help="Delay in seconds between API calls (default: 2.0)",
    )
    parser.add_argument(
        "--skip-ragas", action="store_true",
        help="Skip Ragas evaluation (saves OpenAI API cost)",
    )
    parser.add_argument(
        "--patch", metavar="FILE",
        help="Patch an existing report: re-run failed weeks (or specific weeks via --patch-weeks)",
    )
    parser.add_argument(
        "--patch-weeks", nargs="+", metavar="DATE",
        help="Specific week end-dates to re-run (e.g. 2026-01-30 2026-01-23)",
    )
    parser.add_argument(
        "--gers-results", metavar="FILE", default=None,
        help="Path to ablation_results.csv; prints GERS summary alongside LLM metrics",
    )
    args = parser.parse_args()

    if not args.skip_ragas and not RAGAS_AVAILABLE:
        print("WARNING: ragas not installed, running custom metrics only.", file=sys.stderr)
        args.skip_ragas = True

    # ── Patch mode: re-run failed weeks from an existing report ──
    if args.patch:
        with open(args.patch, encoding="utf-8") as f:
            existing = json.load(f)

        all_weeks = existing["weeks"]
        meta = existing["metadata"]
        trials_per_week = meta.get("trials_per_week", 1)

        # Find weeks to re-run: explicit dates or auto-detect failures
        failed_weeks = []
        if args.patch_weeks:
            target_dates = set(args.patch_weeks)
            for i, week in enumerate(all_weeks):
                if week["week_end"] in target_dates:
                    failed_weeks.append(i)
            missing = target_dates - {all_weeks[i]["week_end"] for i in failed_weeks}
            if missing:
                print(f"WARNING: dates not found in report: {', '.join(missing)}")
        else:
            for i, week in enumerate(all_weeks):
                has_errors = any("error" in t for t in week.get("trial_results", []))
                agg = week.get("aggregate", {})
                no_data = agg.get("symbol_accuracy", {}).get("mean") is None
                zero_score = agg.get("symbol_accuracy", {}).get("mean") == 0.0
                if has_errors or no_data or zero_score:
                    failed_weeks.append(i)

        if not failed_weeks:
            print("No failed weeks found — report is complete!")
            sys.exit(0)

        print(f"Found {len(failed_weeks)} week(s) to re-evaluate:")
        for i in failed_weeks:
            print(f"  {all_weeks[i]['week_end']}")

        total_calls = len(failed_weeks) * trials_per_week
        call_num = 0

        for i in failed_weeks:
            week_end = all_weeks[i]["week_end"]
            print(f"\n── Re-evaluating week ending {week_end} ──")
            trial_results = []

            for trial in range(trials_per_week):
                call_num += 1
                label = f"  Trial {trial + 1}/{trials_per_week}" if trials_per_week > 1 else "  Evaluating"
                print(f"{label} ({call_num}/{total_calls}) ...", end=" ", flush=True)

                try:
                    result = evaluate_one(
                        args.api_url, week_end, meta.get("num_tolerance", 1.5),
                        skip_ragas=args.skip_ragas,
                    )
                    if "error" in result:
                        print(f"SKIP: {result['error']}")
                    else:
                        scores = [
                            result["metrics"][k]["score"]
                            for k in METRIC_KEYS
                            if result["metrics"][k].get("score") is not None
                        ]
                        avg = statistics.mean(scores) if scores else 0
                        ragas_info = ""
                        ragas_overall = result.get("ragas_metrics", {}).get("overall", {})
                        if ragas_overall:
                            f_val = ragas_overall.get("faithfulness", "?")
                            r_val = ragas_overall.get("answer_relevancy", "?")
                            ragas_info = f" | faith={f_val} rel={r_val}"
                        print(f"avg={avg:.1%}{ragas_info}")
                    trial_results.append(result)
                except Exception as exc:
                    print(f"ERROR: {exc}")
                    trial_results.append({"error": str(exc), "date_range": week_end})

                if call_num < total_calls:
                    time.sleep(args.delay)

            agg = aggregate_trials(trial_results)
            first_ok = next((t for t in trial_results if "error" not in t), None)
            date_range = first_ok["date_range"] if first_ok else week_end

            # Replace the failed week in the report
            all_weeks[i] = {
                "date_range": date_range,
                "week_end": week_end,
                "trials": trials_per_week,
                "aggregate": agg,
                "trial_results": trial_results,
            }

        has_ragas = any("ragas" in w["aggregate"] for w in all_weeks)
        print_summary(all_weeks, has_ragas=has_ragas)

        existing["weeks"] = all_weeks
        existing["metadata"]["patched_at"] = datetime.utcnow().isoformat() + "Z"

        out_path = args.output
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, default=str)
        print(f"\nPatched report saved to {out_path}")
        return

    # ── Normal mode: full evaluation ──
    print(f"Discovering {args.weeks} week windows from {args.api_url} ...")
    week_ends = discover_week_ends(args.api_url, args.weeks)
    print(f"  Week end dates: {', '.join(week_ends)}")
    if not args.skip_ragas:
        print(f"  Ragas enabled — estimated cost: ~${args.weeks * args.trials * 0.007:.2f}")

    all_weeks = []
    total_calls = args.weeks * args.trials
    call_num = 0

    for week_end in week_ends:
        print(f"\n── Week ending {week_end} ──")
        trial_results = []

        for trial in range(args.trials):
            call_num += 1
            label = f"  Trial {trial + 1}/{args.trials}" if args.trials > 1 else "  Evaluating"
            print(f"{label} ({call_num}/{total_calls}) ...", end=" ", flush=True)

            try:
                result = evaluate_one(
                    args.api_url, week_end, args.num_tolerance,
                    skip_ragas=args.skip_ragas,
                )
                if "error" in result:
                    print(f"SKIP: {result['error']}")
                else:
                    scores = [
                        result["metrics"][k]["score"]
                        for k in METRIC_KEYS
                        if result["metrics"][k].get("score") is not None
                    ]
                    avg = statistics.mean(scores) if scores else 0
                    ragas_info = ""
                    ragas_overall = result.get("ragas_metrics", {}).get("overall", {})
                    if ragas_overall:
                        f_val = ragas_overall.get("faithfulness", "?")
                        r_val = ragas_overall.get("answer_relevancy", "?")
                        ragas_info = f" | faith={f_val} rel={r_val}"
                    print(f"avg={avg:.1%}{ragas_info}")
                trial_results.append(result)
            except Exception as exc:
                print(f"ERROR: {exc}")
                trial_results.append({"error": str(exc), "date_range": week_end})

            if call_num < total_calls:
                time.sleep(args.delay)

        agg = aggregate_trials(trial_results)
        first_ok = next((t for t in trial_results if "error" not in t), None)
        date_range = first_ok["date_range"] if first_ok else week_end

        all_weeks.append({
            "date_range": date_range,
            "week_end": week_end,
            "trials": args.trials,
            "aggregate": agg,
            "trial_results": trial_results,
        })

    has_ragas = any("ragas" in w["aggregate"] for w in all_weeks)
    print_summary(all_weeks, has_ragas=has_ragas)

    # Save full report
    report = {
        "metadata": {
            "weeks": args.weeks,
            "trials_per_week": args.trials,
            "num_tolerance": args.num_tolerance,
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
            "api_url": args.api_url,
            "ragas_enabled": not args.skip_ragas,
        },
        "weeks": all_weeks,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to {args.output}")

    print_gers_summary(args.gers_results)


if __name__ == "__main__":
    main()
