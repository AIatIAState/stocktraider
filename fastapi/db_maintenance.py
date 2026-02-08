import argparse
from http.client import HTTPException
import os
import sqlite3
from pathlib import Path
import threading
import time
from datetime import date, datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field
from update_prices import update_daily_bars
import logging

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parents[1] / "data" / "stocks.db"))
LOGGER = logging.getLogger(__name__)

JOB_RETENTION_SECONDS = 24 * 60 * 60
JOB_LOCK = threading.Lock()
JOBS: dict[str, dict] = {}

class AdminUpdateRequest(BaseModel):
    start: str = Field(..., description="YYYY-MM-DD")
    end: str = Field(..., description="YYYY-MM-DD")
    symbols: list[str] | None = None
    limit: int | None = None


def parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be YYYY-MM-DD (got '{value}')",
        ) from exc


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key != "created_at_ts"}


def prune_jobs() -> None:
    cutoff = time.time() - JOB_RETENTION_SECONDS
    stale = [job_id for job_id, job in JOBS.items() if job.get("created_at_ts", 0) < cutoff]
    for job_id in stale:
        JOBS.pop(job_id, None)


def find_running_job() -> dict | None:
    for job in JOBS.values():
        if job.get("status") == "running":
            return job
    return None


def start_update_job(*, start_date: date, end_date: date, symbols: list[str] | None, limit: int | None) -> dict:
    job_id = uuid4().hex
    now_iso = now_iso()
    job = {
        "id": job_id,
        "status": "running",
        "created_at": now_iso,
        "started_at": now_iso,
        "finished_at": None,
        "summary": None,
        "error": None,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "created_at_ts": time.time(),
    }

    def _run():
        try:
            summary = update_daily_bars(
                start_date=start_date,
                end_date=end_date,
                symbols=symbols,
                limit=limit,
            )
            finished = now_iso()
            with JOB_LOCK:
                job["status"] = "completed"
                job["summary"] = summary
                job["finished_at"] = finished
        except Exception as exc:
            LOGGER.exception("Admin update job failed")
            finished = now_iso()
            with JOB_LOCK:
                job["status"] = "failed"
                job["error"] = str(exc)
                job["finished_at"] = finished

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return job


def ensure_indexes() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        # Create indexes for the bars table to optimize queries by timeframe, date, and symbol
        # This makes loading 1min --> 2 seconds
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bars_timeframe_date_symbol ON bars (timeframe, date, symbol)"
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite maintenance tasks.")
    parser.add_argument("--ensure-indexes", action="store_true", help="Ensure required indexes exist.")
    args = parser.parse_args()

    if args.ensure_indexes:
        ensure_indexes()
        print("Indexes ensured.")
        return 0

    print("No action requested. Use --ensure-indexes.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
