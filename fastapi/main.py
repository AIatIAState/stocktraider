import logging
import sqlite3
import threading
import time
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from Connector import get_connection
from PatternRecognition import get_dtw_patterns
from Forecasting import get_forecast
from update_prices import update_daily_bars

app = FastAPI()
LOGGER = logging.getLogger("uvicorn.error")

MAX_LIMIT = 50000
JOB_RETENTION_SECONDS = 24 * 60 * 60
JOB_LOCK = threading.Lock()
JOBS: dict[str, dict] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(sqlite3.Error)
async def sqlite_error_handler(request: Request, exc: sqlite3.Error):
    LOGGER.exception("SQLite error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Database error: {exc}"})


class AdminUpdateRequest(BaseModel):
    start: str = Field(..., description="YYYY-MM-DD")
    end: str = Field(..., description="YYYY-MM-DD")
    symbols: list[str] | None = None
    limit: int | None = None


def _parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be YYYY-MM-DD (got '{value}')",
        ) from exc


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key != "created_at_ts"}


def _prune_jobs() -> None:
    cutoff = time.time() - JOB_RETENTION_SECONDS
    stale = [job_id for job_id, job in JOBS.items() if job.get("created_at_ts", 0) < cutoff]
    for job_id in stale:
        JOBS.pop(job_id, None)


def _find_running_job() -> dict | None:
    for job in JOBS.values():
        if job.get("status") == "running":
            return job
    return None


def _start_update_job(*, start_date: date, end_date: date, symbols: list[str] | None, limit: int | None) -> dict:
    job_id = uuid4().hex
    now_iso = _now_iso()
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
            finished = _now_iso()
            with JOB_LOCK:
                job["status"] = "completed"
                job["summary"] = summary
                job["finished_at"] = finished
        except Exception as exc:
            LOGGER.exception("Admin update job failed")
            finished = _now_iso()
            with JOB_LOCK:
                job["status"] = "failed"
                job["error"] = str(exc)
                job["finished_at"] = finished

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return job



@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/ready")
def ready():
    conn = get_connection(readonly=True)
    try:
        conn.execute("SELECT 1 FROM symbols LIMIT 1").fetchone()
        conn.execute("SELECT 1 FROM bars LIMIT 1").fetchone()
    finally:
        conn.close()

    return {"status": "ok"}


@app.post("/api/admin/update")
def admin_update(request: AdminUpdateRequest, wait: bool = Query(False)):
    start_date = _parse_iso_date(request.start, "start")
    end_date = _parse_iso_date(request.end, "end")
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end must be >= start")

    if wait:
        summary = update_daily_bars(
            start_date=start_date,
            end_date=end_date,
            symbols=request.symbols,
            limit=request.limit,
        )
        return {"summary": summary}

    with JOB_LOCK:
        _prune_jobs()
        running_job = _find_running_job()
        if running_job:
            raise HTTPException(
                status_code=409,
                detail=f"Update job already running (job_id={running_job['id']})",
            )
        job = _start_update_job(
            start_date=start_date,
            end_date=end_date,
            symbols=request.symbols,
            limit=request.limit,
        )
        JOBS[job["id"]] = job

    return JSONResponse(status_code=202, content=_serialize_job(job))


@app.get("/api/admin/update/jobs")
def admin_update_jobs(status: str | None = Query(None)):
    with JOB_LOCK:
        _prune_jobs()
        jobs = list(JOBS.values())

    if status:
        status_value = status.strip().lower()
        if status_value not in {"running", "completed", "failed"}:
            raise HTTPException(status_code=400, detail="status must be running, completed, or failed")
        jobs = [job for job in jobs if job.get("status") == status_value]

    jobs.sort(key=lambda job: job.get("created_at_ts", 0), reverse=True)
    return {"jobs": [_serialize_job(job) for job in jobs]}


@app.get("/api/admin/update/{job_id}")
def admin_update_status(job_id: str):
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return _serialize_job(job)


@app.get("/api/symbols")
def search_symbols(q: str = Query(..., min_length=1), limit: int = Query(25, ge=1, le=500)):
    query = q.strip().upper()
    conn = get_connection(readonly=True)
    try:
        rows = conn.execute(
            """
            SELECT symbol, exchange, asset_type, country
            FROM symbols
            WHERE symbol LIKE ?
            ORDER BY symbol
            LIMIT ?
            """,
            (f"{query}%", limit),
        ).fetchall()
    finally:
        conn.close()

    return {"results": [dict(row) for row in rows]}


@app.get("/api/bars")
def get_bars(
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query("daily"),
    start: int | None = Query(None, description="YYYYMMDD"),
    end: int | None = Query(None, description="YYYYMMDD"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(500, ge=1, le=MAX_LIMIT),
):
    symbol_value = symbol.strip().upper()
    timeframe_value = timeframe.strip().lower()
    order_value = order.strip().lower()

    if order_value not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="order must be 'asc' or 'desc'")
    order_sql = "ASC" if order_value == "asc" else "DESC"

    where = ["symbol = ?", "timeframe = ?"]
    params: list[object] = [symbol_value, timeframe_value]

    if start is not None:
        where.append("date >= ?")
        params.append(start)
    if end is not None:
        where.append("date <= ?")
        params.append(end)

    sql = f"""
        SELECT symbol, per, date, time, open, high, low, close, volume, openint, timeframe
        FROM bars
        WHERE {' AND '.join(where)}
        ORDER BY date {order_sql}, time {order_sql}
        LIMIT ?
    """
    params.append(limit)

    conn = get_connection(readonly=True)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return {"results": [dict(row) for row in rows]}

@app.get("/api/getPatterns")
def get_patterns(symbol: str = Query(..., min_length=1),
    timeframe: str = Query("daily"),
    trend_length: int | None = Query(None,),
    similarity_score: int | None = Query(None)):

    return get_dtw_patterns(symbol, timeframe, trend_length, similarity_score)

@app.get("/api/getForecasts")
def get_forecasts(symbol: str = Query(..., min_length=1),
                  timeframe: str = Query("daily"),
                  forecast_length: int | None = Query(None, )):
    if forecast_length is None:
        forecast_length = 7
    return get_forecast(symbol, timeframe, forecast_length)
