#!/usr/bin/env python3
"""Bulk-fetch geopolitical/market headlines from Alpha Vantage NEWS_SENTIMENT.

Parameterized over an arbitrary date range and slice granularity so it can both
probe coverage density (``--probe``) and do a full pull into
results/headlines_cache.jsonl. The ablation script reads from that cached file.

Usage:
  export ALPHA_VANTAGE_API_KEY="<your_key>"

  # Probe recent months to find dense windows (prints counts, writes nothing):
  python eval_scripts/prefetch_headlines.py --start 2025-04 --end 2026-06 \
         --granularity monthly --probe

  # Full pull of chosen windows at weekly granularity (fresh cache):
  python eval_scripts/prefetch_headlines.py --start 2025-10 --end 2026-06 \
         --granularity weekly --reset
"""
import argparse
import calendar
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("ALPHAVANTAGE_API_KEY")
if not API_KEY:
    sys.exit("ERROR: set ALPHA_VANTAGE_API_KEY before running this script")

OUTPUT = Path(__file__).resolve().parent.parent / "results" / "headlines_cache.jsonl"
ENDPOINT = "https://www.alphavantage.co/query"

# Broad market + macro + geopolitical topics (OR-combined by Alpha Vantage).
# Wider than the original geopolitical-only filter to maximise headline volume.
DEFAULT_TOPICS = "financial_markets,economy_macro,economy_monetary,economy_fiscal"
# Fallback when topic-filtered volume is thin: query by major market ETFs/megacaps.
FALLBACK_TICKERS = "SPY,QQQ,DIA,AAPL,MSFT"


def _parse_month(s: str) -> date:
    """Parse 'YYYY-MM' to the first day of that month."""
    parts = s.split("-")
    return date(int(parts[0]), int(parts[1]), 1)


def _month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _gen_slices(start: date, end: date, granularity: str) -> list[tuple[date, date]]:
    """Yield (slice_start, slice_end) date pairs covering [start, end_of_end_month]."""
    final = _month_end(end)
    slices: list[tuple[date, date]] = []
    if granularity == "monthly":
        cur = start
        while cur <= final:
            slices.append((cur, _month_end(cur)))
            # advance to first of next month
            cur = (_month_end(cur) + timedelta(days=1))
    else:  # weekly
        cur = start
        while cur <= final:
            wk_end = min(cur + timedelta(days=6), final)
            slices.append((cur, wk_end))
            cur = wk_end + timedelta(days=1)
    return slices


def _fmt(d: date, end_of_day: bool = False) -> str:
    return d.strftime("%Y%m%dT2359") if end_of_day else d.strftime("%Y%m%dT0000")


def _fetch(slice_start: date, slice_end: date, use_tickers: bool) -> tuple[list, str]:
    """Return (feed, status) for one Alpha Vantage call. status is '' on success."""
    params = {
        "function": "NEWS_SENTIMENT",
        "time_from": _fmt(slice_start),
        "time_to": _fmt(slice_end, end_of_day=True),
        "sort": "LATEST",
        "limit": "1000",
        "apikey": API_KEY,
    }
    if use_tickers:
        params["tickers"] = FALLBACK_TICKERS
    else:
        params["topics"] = DEFAULT_TOPICS
    try:
        resp = requests.get(ENDPOINT, params=params, timeout=30)
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return [], f"ERROR: {exc}"
    if "Information" in data or "Note" in data:
        return [], (data.get("Information") or data.get("Note", "rate limited"))
    return data.get("feed", []), ""


def _load_existing() -> dict[str, list[str]]:
    existing: dict[str, list[str]] = {}
    if not OUTPUT.exists():
        return existing
    with OUTPUT.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if row.get("date") and isinstance(row.get("titles"), list):
                    existing[row["date"]] = row["titles"]
            except (json.JSONDecodeError, TypeError):
                pass
    return existing


def main() -> None:
    ap = argparse.ArgumentParser(description="Alpha Vantage headline prefetcher")
    ap.add_argument("--start", required=True, help="start month YYYY-MM (inclusive)")
    ap.add_argument("--end", required=True, help="end month YYYY-MM (inclusive)")
    ap.add_argument("--granularity", choices=["weekly", "monthly"], default="weekly")
    ap.add_argument("--probe", action="store_true",
                    help="print per-slice counts only; do not write the cache")
    ap.add_argument("--reset", action="store_true",
                    help="overwrite the cache instead of resuming/merging")
    ap.add_argument("--tickers", action="store_true",
                    help="query by FALLBACK_TICKERS instead of topics (denser for some periods)")
    args = ap.parse_args()

    start = _parse_month(args.start)
    end = _parse_month(args.end)
    slices = _gen_slices(start, end, args.granularity)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    existing = {} if (args.reset or args.probe) else _load_existing()
    if existing:
        print(f"Resuming: merging into {len(existing)} cached dates")

    date_to_titles: dict[str, list[str]] = {k: list(v) for k, v in existing.items()}

    for i, (s_start, s_end) in enumerate(slices, 1):
        label = f"{s_start.isoformat()}..{s_end.isoformat()}"
        print(f"[{i}/{len(slices)}] {label}", end=" ", flush=True)

        feed, status = _fetch(s_start, s_end, use_tickers=args.tickers)
        if status:
            print(f"-> {status}")
            if status.startswith("ERROR"):
                continue
            print("Rate limit reached — wait then re-run (resumes unless --reset).")
            break

        slice_dates: set[str] = set()
        for article in feed:
            raw = article.get("time_published", "")[:8]  # YYYYMMDD
            if len(raw) == 8:
                ds = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
                title = article.get("title", "").strip()
                if title:
                    slice_dates.add(ds)
                    if not args.probe:
                        date_to_titles.setdefault(ds, []).append(title)
        print(f"-> {len(feed)} articles across {len(slice_dates)} dates")

        if i < len(slices):
            time.sleep(13)  # stay within 25 req/day free limit

    if args.probe:
        print("\nProbe complete (nothing written). "
              "Pick the densest contiguous windows and re-run without --probe.")
        return

    with OUTPUT.open("w", encoding="utf-8") as f:
        for ds in sorted(date_to_titles):
            f.write(json.dumps({"date": ds, "titles": date_to_titles[ds][:30]}) + "\n")

    total = sum(len(v) for v in date_to_titles.values())
    print(f"\nDone. {len(date_to_titles)} dates / {total} titles -> {OUTPUT}")
    print("Next: set PERIODS in baseline_ablation.py to these windows, then run the ablation.")


if __name__ == "__main__":
    main()
