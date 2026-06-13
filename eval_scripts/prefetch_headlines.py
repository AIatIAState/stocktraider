#!/usr/bin/env python3
"""One-time bulk-fetch of geopolitical/market headlines from Alpha Vantage.

Fetches 15 monthly slices (2022 full year + Q1 2025) using the free
NEWS_SENTIMENT endpoint and writes results/headlines_cache.jsonl.
Only needs to run once — the ablation script reads from the cached file.

Usage:
  export ALPHA_VANTAGE_API_KEY="<your_key>"
  python eval_scripts/prefetch_headlines.py
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("ALPHAVANTAGE_API_KEY")
if not API_KEY:
    sys.exit("ERROR: set ALPHA_VANTAGE_API_KEY before running this script")

OUTPUT = Path(__file__).resolve().parent.parent / "results" / "headlines_cache.jsonl"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Load already-cached dates so a partial run can resume
existing: dict[str, list[str]] = {}
if OUTPUT.exists():
    with OUTPUT.open("r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line:
                continue
            try:
                _row = json.loads(_line)
                if _row.get("date") and isinstance(_row.get("titles"), list):
                    existing[_row["date"]] = _row["titles"]
            except (json.JSONDecodeError, TypeError):
                pass
    print(f"Resuming: {len(existing)} dates already in cache")

# Monthly slices: 2022 full year + Q1 2025
SLICES = [
    ("20220101T0000", "20220131T2359"),
    ("20220201T0000", "20220228T2359"),
    ("20220301T0000", "20220331T2359"),
    ("20220401T0000", "20220430T2359"),
    ("20220501T0000", "20220531T2359"),
    ("20220601T0000", "20220630T2359"),
    ("20220701T0000", "20220731T2359"),
    ("20220801T0000", "20220831T2359"),
    ("20220901T0000", "20220930T2359"),
    ("20221001T0000", "20221031T2359"),
    ("20221101T0000", "20221130T2359"),
    ("20221201T0000", "20221231T2359"),
    ("20250101T0000", "20250131T2359"),
    ("20250201T0000", "20250228T2359"),
    ("20250301T0000", "20250331T2359"),
]

date_to_titles: dict[str, list[str]] = dict(existing)

for i, (tf, tt) in enumerate(SLICES, 1):
    month_label = f"{tf[:4]}-{tf[4:6]}"
    # Check if any date in this month is already cached; if fully covered, skip
    month_year = tf[:6]
    cached_in_month = [d for d in existing if d.replace("-", "").startswith(month_year)]
    if len(cached_in_month) >= 25:  # ~25 trading days per month
        print(f"[{i}/{len(SLICES)}] {month_label} already cached ({len(cached_in_month)} dates), skipping")
        continue

    print(f"[{i}/{len(SLICES)}] Fetching {month_label}...", end=" ", flush=True)
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "topics": "economy_fiscal,economy_monetary,geopolitical,financial_markets",
                "time_from": tf,
                "time_to": tt,
                "limit": "1000",
                "apikey": API_KEY,
            },
            timeout=30,
        )
        data = resp.json()
    except Exception as exc:
        print(f"ERROR: {exc}")
        continue

    if "Information" in data or "Note" in data:
        msg = data.get("Information") or data.get("Note", "")
        print(f"API limit: {msg}")
        print("Rate limit hit — wait a minute then re-run (script will resume from here).")
        break

    feed = data.get("feed", [])
    print(f"{len(feed)} articles")

    for article in feed:
        raw_date = article.get("time_published", "")[:8]  # YYYYMMDD
        if len(raw_date) == 8:
            ds = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            title = article.get("title", "").strip()
            if title:
                date_to_titles.setdefault(ds, []).append(title)

    if i < len(SLICES):
        time.sleep(13)  # stay well within 25 req/day free limit

# Write full cache (overwrite so deduped)
with OUTPUT.open("w", encoding="utf-8") as f:
    for ds in sorted(date_to_titles):
        titles = date_to_titles[ds][:20]  # cap per day
        f.write(json.dumps({"date": ds, "titles": titles}) + "\n")

total_articles = sum(len(v) for v in date_to_titles.values())
print(f"\nDone. {len(date_to_titles)} dates / {total_articles} total titles → {OUTPUT}")
print("Now run: python eval_scripts/baseline_ablation.py --baselines B0 B2 B3 B2b --tickers SPY --reset")
