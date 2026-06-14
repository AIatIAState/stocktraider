"""Ablation runner: clear geo cache → sanity check (SPY) → full sweep.

Usage:
    python eval_scripts/run_ablation.py

Prereqs:
    - OPENAI_API_KEY set (for B2/B3 geo extraction)
    - results/headlines_cache.jsonl populated by prefetch_headlines.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"
GEO_CACHE = RESULTS_DIR / "geo_features_cache.jsonl"
ABLATION_CSV = RESULTS_DIR / "ablation_results.csv"
LOG_FILE = RESULTS_DIR / "ablation.log"

ABLATION_MOD = "eval_scripts.baseline_ablation"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


class Tee:
    """Write to both stdout and a log file simultaneously."""

    def __init__(self, log_path: Path) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = log_path.open("a", encoding="utf-8")

    def write(self, line: str) -> None:
        print(line)
        self._log.write(line + "\n")
        self._log.flush()

    def close(self) -> None:
        self._log.close()


def run_subprocess(tee: Tee, args: list[str]) -> int:
    """Run args as subprocess, streaming output to tee. Returns exit code."""
    tee.write(f"[{_ts()}] CMD: {' '.join(args)}")
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=REPO_ROOT,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        tee.write(line.rstrip())
    proc.wait()
    return proc.returncode


def sanity_check_csv(tee: Tee) -> bool:
    """Return True if any geo baseline (B2/B3/B2b) differs from B0 in DA."""
    if not ABLATION_CSV.exists() or ABLATION_CSV.stat().st_size == 0:
        tee.write(f"[{_ts()}] SANITY FAIL — ablation_results.csv is missing or empty.")
        return False
    df = pd.read_csv(ABLATION_CSV)
    if "DA" not in df.columns or "baseline" not in df.columns:
        tee.write(f"[{_ts()}] SANITY FAIL — expected columns 'baseline' and 'DA' not found.")
        return False
    b0 = df[df["baseline"] == "B0"]["DA"].dropna()
    geo = df[df["baseline"].isin(["B2", "B3", "B2b"])]["DA"].dropna()
    if b0.empty or geo.empty:
        tee.write(f"[{_ts()}] SANITY FAIL — B0 or geo baselines missing from CSV.")
        return False
    if b0.mean() == geo.mean():
        tee.write(
            f"[{_ts()}] SANITY FAIL — mean DA identical between B0 ({b0.mean():.4f}) "
            f"and geo baselines ({geo.mean():.4f}). Possible extraction error."
        )
        return False
    tee.write(
        f"[{_ts()}] SANITY PASS — B0 mean DA={b0.mean():.4f}, "
        f"geo baselines mean DA={geo.mean():.4f} (differ as expected)."
    )
    return True


def print_summary(tee: Tee) -> None:
    """Print mean DA and MAE per baseline × period."""
    if not ABLATION_CSV.exists() or ABLATION_CSV.stat().st_size == 0:
        tee.write(f"[{_ts()}] No results to summarise.")
        return
    df = pd.read_csv(ABLATION_CSV)
    if not {"baseline", "period", "DA", "MAE"}.issubset(df.columns):
        tee.write(f"[{_ts()}] CSV missing expected columns for summary.")
        return

    summary = (
        df.groupby(["baseline", "period"])[["DA", "MAE"]]
        .mean()
        .round(4)
        .reset_index()
        .sort_values(["period", "baseline"])
    )
    lines = [
        "",
        "=" * 56,
        "RESULTS SUMMARY",
        "=" * 56,
        f"{'baseline':<10} {'period':<14} {'mean_DA':>8} {'mean_MAE':>10}",
        "-" * 46,
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"{row['baseline']:<10} {row['period']:<14} {row['DA']:>8.4f} {row['MAE']:>10.6f}"
        )
    lines.append("=" * 56)
    for line in lines:
        tee.write(line)


def main() -> None:
    tee = Tee(LOG_FILE)
    tee.write(f"[{_ts()}] === run_ablation.py started ===")

    # 1. Clear stale geo cache
    if GEO_CACHE.exists():
        GEO_CACHE.unlink()
        tee.write(f"[{_ts()}] Cleared geo cache: {GEO_CACHE}")
    else:
        tee.write(f"[{_ts()}] No geo cache to clear (first run).")

    python = sys.executable

    # 2. Sanity check: SPY only, B0 B2 B3 B2b, --reset
    tee.write(f"[{_ts()}] --- Sanity check (SPY × B0/B2/B3/B2b) ---")
    rc = run_subprocess(
        tee,
        [
            python, "-m", ABLATION_MOD,
            "--baselines", "B0", "B2", "B3", "B2b",
            "--tickers", "SPY",
            "--reset",
        ],
    )
    if rc != 0:
        tee.write(f"[{_ts()}] Sanity check subprocess exited with code {rc}. Aborting.")
        tee.close()
        sys.exit(rc)

    if not sanity_check_csv(tee):
        tee.write(
            textwrap.dedent(f"""
            [{_ts()}] Diagnostic: geo baselines returned identical DA to B0.
            Possible causes:
              1. OPENAI_API_KEY not set — B2/B3 geo extraction falls back to zeros.
              2. headlines_cache.jsonl is empty or missing from results/.
              3. Geo feature extraction raised errors (check log above).
            Aborting full sweep to avoid wasting API quota.
            """).strip()
        )
        tee.close()
        sys.exit(1)

    # 3. Full sweep: all tickers, all baselines (resume — no --reset)
    tee.write(f"[{_ts()}] --- Full sweep (all tickers × B0/B1/B2/B3/B2b) ---")
    rc = run_subprocess(
        tee,
        [
            python, "-m", ABLATION_MOD,
            "--baselines", "B0", "B1", "B2", "B3", "B2b",
        ],
    )
    if rc != 0:
        tee.write(f"[{_ts()}] Full sweep exited with code {rc}.")
        print_summary(tee)
        tee.close()
        sys.exit(rc)

    # 4. Summary
    print_summary(tee)
    tee.write(f"[{_ts()}] === run_ablation.py complete. Log: {LOG_FILE} ===")
    tee.close()


if __name__ == "__main__":
    main()
