import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from connector import get_connection
from admin_jobs import JOBS, JOB_LOCK, find_running_job, prune_jobs, start_update_job

LOGGER = logging.getLogger("uvicorn.error")

SCHEDULER = None
SCHEDULE_TZ: ZoneInfo | None = None
STATE_LOCK = threading.Lock()

DEFAULT_TIMEZONE = "America/Chicago"
SCHEDULER_JOB_ID = "weekly_yfinance_refresh"
STATE_KEY = "scheduler_state"


def _load_state() -> dict:
    try:
        conn = get_connection(readonly=True)
    except Exception:
        LOGGER.exception("Failed to open DB for scheduler state read")
        return {}
    try:
        try:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (STATE_KEY,),
            ).fetchone()
        except sqlite3.Error:
            return {}
        if not row:
            return {}
        try:
            return json.loads(row["value"])
        except Exception:
            LOGGER.exception("Failed to parse scheduler state JSON")
            return {}
    finally:
        conn.close()


def _write_state(state: dict) -> None:
    try:
        conn = get_connection(readonly=False)
    except Exception:
        LOGGER.exception("Failed to open DB for scheduler state write")
        return
    try:
        payload = json.dumps(state, indent=2, sort_keys=True)
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (STATE_KEY, payload),
            )
    except Exception:
        LOGGER.exception("Failed to write scheduler state")
    finally:
        conn.close()


def _desired_enabled() -> bool:
    state = _load_state()
    if "enabled" in state:
        return bool(state.get("enabled"))
    return _env_bool("SCHEDULED_UPDATE_ENABLED", default=False)


def _timezone_name() -> str:
    state = _load_state()
    return (state.get("timezone") or os.getenv("SCHEDULED_UPDATE_TIMEZONE", DEFAULT_TIMEZONE)).strip() or DEFAULT_TIMEZONE


def _scheduler_available() -> bool:
    try:
        import apscheduler  # noqa: F401

        return True
    except Exception:
        return False


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def start_scheduler() -> None:
    global SCHEDULER, SCHEDULE_TZ
    if SCHEDULER:
        return

    if not _desired_enabled():
        LOGGER.info("Scheduled updates disabled (set SCHEDULED_UPDATE_ENABLED=true to enable).")
        return

    tz_name = _timezone_name()
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        LOGGER.exception("Timezone %s not found; falling back to UTC", tz_name)
        tz = ZoneInfo("UTC")

    SCHEDULE_TZ = tz

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except Exception:
        LOGGER.exception("APScheduler is required for scheduled updates but is not available.")
        return

    scheduler = BackgroundScheduler(timezone=tz)
    trigger = CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=tz)
    scheduler.add_job(
        run_scheduled_update,
        trigger=trigger,
        id=SCHEDULER_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=int(os.getenv("SCHEDULED_UPDATE_MISFIRE_GRACE_SECONDS", "43200")),
    )
    scheduler.start()
    SCHEDULER = scheduler

    job = scheduler.get_job(SCHEDULER_JOB_ID)
    LOGGER.info(
        "Scheduled updates enabled: Sundays 03:00 %s (next_run=%s).",
        getattr(tz, "key", tz_name),
        getattr(job, "next_run_time", None),
    )


def stop_scheduler() -> None:
    global SCHEDULER
    if not SCHEDULER:
        return
    try:
        SCHEDULER.shutdown(wait=False)
    except Exception:
        LOGGER.exception("Failed to stop scheduler cleanly.")
    finally:
        SCHEDULER = None


def get_scheduler_status() -> dict:
    state = _load_state()
    tz_name = _timezone_name()
    desired = _desired_enabled()

    next_run = None
    if SCHEDULER:
        job = SCHEDULER.get_job(SCHEDULER_JOB_ID)
        if job and getattr(job, "next_run_time", None):
            next_run = job.next_run_time.isoformat()

    return {
        "available": _scheduler_available(),
        "enabled": desired,
        "running": bool(SCHEDULER),
        "timezone": tz_name,
        "schedule": "Sundays 03:00",
        "next_run_time": next_run,
        "last_started_at": state.get("last_started_at"),
        "last_finished_at": state.get("last_finished_at"),
        "last_status": state.get("last_status"),
        "last_job_id": state.get("last_job_id"),
        "last_error": state.get("last_error"),
    }


def set_scheduler_enabled(enabled: bool) -> dict:
    with STATE_LOCK:
        state = _load_state()
        state["enabled"] = bool(enabled)
        _write_state(state)

    if enabled:
        start_scheduler()
    else:
        stop_scheduler()

    return get_scheduler_status()


def run_scheduled_update() -> None:
    tz = SCHEDULE_TZ
    if tz is None:
        tz_name = _timezone_name()
        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")

    end_date = datetime.now(tz).date()
    start_date = end_date - timedelta(days=6)

    job = None
    def _on_finish(snapshot: dict) -> None:
        with STATE_LOCK:
            state = _load_state()
            state["last_finished_at"] = snapshot.get("finished_at")
            state["last_status"] = snapshot.get("status")
            state["last_error"] = snapshot.get("error")
            _write_state(state)

    with JOB_LOCK:
        prune_jobs()
        running_job = find_running_job()
        if running_job:
            LOGGER.info(
                "Scheduled update skipped (job already running job_id=%s).",
                running_job.get("id"),
            )
            return

        job = start_update_job(
            start_date=start_date,
            end_date=end_date,
            symbols=None,
            limit=None,
            job_meta={"trigger": "scheduler"},
            on_finish=_on_finish,
        )
        JOBS[job["id"]] = job

    with STATE_LOCK:
        state = _load_state()
        state["last_job_id"] = job["id"]
        state["last_started_at"] = job.get("started_at")
        state["last_status"] = job.get("status")
        state["last_error"] = None
        _write_state(state)

    LOGGER.info(
        "Scheduled update started (job_id=%s range=%s..%s).",
        job["id"],
        start_date.isoformat(),
        end_date.isoformat(),
    )
