import logging
import threading
import time
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4
import os

from fastapi import HTTPException
from pydantic import BaseModel, Field

from fetch_prices import update_daily_bars

LOGGER = logging.getLogger("uvicorn.error")

JOB_RETENTION_SECONDS = 24 * 60 * 60
# In-memory job tracking (cleared on app restart).
JOB_LOCK = threading.Lock()
JOBS: dict[str, dict] = {}


class AdminUpdateRequest(BaseModel):
    start: str = Field(..., description="YYYY-MM-DD")
    end: str = Field(..., description="YYYY-MM-DD")
    symbols: list[str] | None = None
    limit: int | None = None


def parse_env_bool(name: str, *, default: bool = False) -> bool:
    val = os.getenv(name, "").strip().lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def int_date_to_iso(date_int: int | None) -> str | None:
    if date_int is None:
        return None
    s = str(date_int)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


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


def start_update_job(
    *,
    start_date: date,
    end_date: date,
    symbols: list[str] | None,
    limit: int | None,
    job_meta: dict[str, Any] | None = None,
    on_finish: Callable[[dict], None] | None = None,
) -> dict:
    job_id = uuid4().hex
    started_at = now_iso()
    job = {
        "id": job_id,
        "status": "running",
        "created_at": started_at,
        "started_at": started_at,
        "finished_at": None,
        "summary": None,
        "error": None,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "created_at_ts": time.time(),
    }
    if job_meta:
        job.update(job_meta)

    def _run():
        snapshot = None
        try:
            summary = update_daily_bars(
                start_date=start_date,
                end_date=end_date,
                symbols=symbols,
                limit=limit,
            )
            finished_at = now_iso()
            with JOB_LOCK:
                job["status"] = "completed"
                job["summary"] = summary
                job["finished_at"] = finished_at
                snapshot = job.copy()
        except Exception as exc:
            LOGGER.exception("Admin update job failed")
            finished_at = now_iso()
            with JOB_LOCK:
                job["status"] = "failed"
                job["error"] = str(exc)
                job["finished_at"] = finished_at
                snapshot = job.copy()
        finally:
            if on_finish:
                try:
                    on_finish(snapshot or job.copy())
                except Exception:
                    LOGGER.exception("Admin update job finish callback failed")

    # Run the update in a background thread to avoid blocking the request thread.
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return job
