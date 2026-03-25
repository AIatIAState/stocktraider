import datetime
import logging
import os
import sqlite3
from datetime import timedelta

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from connector import DB_PATH, get_connection
from xg_boost_investor import XGBoostInvestor, Features
from pattern_recognition import get_dtw_patterns
from forecasting import get_forecast
from fetch_prices import update_daily_bars
from WeeklyMovers import (
    MOVERS_CACHE_LOCK,
    date_int_to_date,
    date_to_int,
    fetch_weekly_movers,
    fetch_weekly_series,
    get_cached_movers,
    set_cached_movers,
)
from admin_jobs import (
    AdminUpdateRequest,
    JOBS,
    JOB_LOCK,
    find_running_job,
    parse_iso_date,
    prune_jobs,
    serialize_job,
    start_update_job,
    parse_env_bool,
    int_date_to_iso,
)
from scheduled_updates import get_scheduler_status, set_scheduler_enabled, start_scheduler, stop_scheduler
from weekly_dashboard import build_weekly_alerts, build_weekly_insights
from xg_boost_investor.Features import build_full_features, get_feature_explanations
from xg_boost_investor.XGBoostInvestor import retrain_model

DEFAULT_BOOTSTRAP_START = "2020-01-01"

app = FastAPI()
LOGGER = logging.getLogger("uvicorn.error")

MAX_LIMIT = 50000

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def start_background_jobs() -> None:
    start_scheduler()


@app.on_event("shutdown")
def stop_background_jobs() -> None:
    stop_scheduler()


class SchedulerEnabledRequest(BaseModel):
    enabled: bool


@app.get("/api/admin/db-info")
def admin_db_info():
    resolved_path = str(DB_PATH.resolve())
    exists = DB_PATH.exists()
    info: dict[str, object] = {
        "db_path_env": os.getenv("DB_PATH"),
        "db_path": str(DB_PATH),
        "db_path_resolved": resolved_path,
        "exists": exists,
        "size_bytes": None,
        "mtime": None,
        "writable": False,
        "daily_min_date": None,
        "daily_max_date": None,
        "bootstrap_enabled": parse_env_bool("SCHEDULED_UPDATE_BOOTSTRAP_ENABLED", default=False),
        "bootstrap_start": os.getenv("SCHEDULED_UPDATE_BOOTSTRAP_START", DEFAULT_BOOTSTRAP_START),
        "bootstrap_has_data": None,
    }

    if not exists:
        return info

    stat = DB_PATH.stat()
    info["size_bytes"] = stat.st_size
    info["mtime"] = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).isoformat()
    info["writable"] = os.access(DB_PATH, os.W_OK)

    bootstrap_start = str(info["bootstrap_start"] or DEFAULT_BOOTSTRAP_START).strip() or DEFAULT_BOOTSTRAP_START
    try:
        bootstrap_date = datetime.date.fromisoformat(bootstrap_start)
        bootstrap_int = int(bootstrap_date.strftime("%Y%m%d"))
    except ValueError:
        bootstrap_int = None

    conn = get_connection(readonly=True)
    try:
        min_row = conn.execute(
            """
            SELECT date
            FROM bars
            WHERE timeframe = 'daily'
            ORDER BY date ASC
            LIMIT 1
            """
        ).fetchone()
        max_row = conn.execute(
            """
            SELECT date
            FROM bars
            WHERE timeframe = 'daily'
            ORDER BY date DESC
            LIMIT 1
            """
        ).fetchone()
        info["daily_min_date"] = int_date_to_iso(min_row["date"] if min_row else None)
        info["daily_max_date"] = int_date_to_iso(max_row["date"] if max_row else None)

        if bootstrap_int is not None:
            exists_row = conn.execute(
                """
                SELECT 1
                FROM bars
                WHERE timeframe = 'daily'
                  AND date = ?
                LIMIT 1
                """,
                (bootstrap_int,),
            ).fetchone()
            info["bootstrap_has_data"] = bool(exists_row)
    finally:
        conn.close()

    return info


@app.get("/api/admin/scheduler")
def admin_scheduler_status():
    return get_scheduler_status()


@app.post("/api/admin/scheduler/enabled")
def admin_scheduler_enabled(request: SchedulerEnabledRequest):
    return set_scheduler_enabled(request.enabled)


@app.exception_handler(sqlite3.Error)
async def sqlite_error_handler(request: Request, exc: sqlite3.Error):
    LOGGER.exception("SQLite error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Database error: {exc}"})


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
    start_date = parse_iso_date(request.start, "start")
    end_date = parse_iso_date(request.end, "end")
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
        prune_jobs()
        running_job = find_running_job()
        if running_job:
            raise HTTPException(
                status_code=409,
                detail=f"Update job already running (job_id={running_job['id']})",
            )
        job = start_update_job(
            start_date=start_date,
            end_date=end_date,
            symbols=request.symbols,
            limit=request.limit,
        )
        JOBS[job["id"]] = job

    return JSONResponse(status_code=202, content=serialize_job(job))


@app.get("/api/admin/update/jobs")
def admin_update_jobs(status: str | None = Query(None)):
    with JOB_LOCK:
        prune_jobs()
        jobs = list(JOBS.values())

    if status:
        status_value = status.strip().lower()
        if status_value not in {"running", "completed", "failed"}:
            raise HTTPException(status_code=400, detail="status must be running, completed, or failed")
        jobs = [job for job in jobs if job.get("status") == status_value]

    jobs.sort(key=lambda job: job.get("created_at_ts", 0), reverse=True)
    return {"jobs": [serialize_job(job) for job in jobs]}


@app.get("/api/admin/update/{job_id}")
def admin_update_status(job_id: str):
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return serialize_job(job)


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


@app.get("/api/weekly-movers")
def weekly_movers(
    direction: str | None = Query(None, description="top or bottom"),
    limit: int = Query(3, ge=1, le=25),
):
    conn = get_connection(readonly=True)
    try:
        row = conn.execute(
            "SELECT MAX(date) AS max_date FROM bars WHERE timeframe = 'daily'"
        ).fetchone()
        if not row or row["max_date"] is None:
            raise HTTPException(status_code=404, detail="No daily bars available")

        end_int = row["max_date"]
        end_date = date_int_to_date(end_int)

        if direction:
            direction_value = direction.strip().lower()
            if direction_value not in ("top", "bottom"):
                raise HTTPException(status_code=400, detail="direction must be top or bottom")
            with MOVERS_CACHE_LOCK:
                cached = get_cached_movers(direction_value, end_int)
            if cached:
                return {
                    "start": cached["start"],
                    "end": cached["end"],
                    "direction": direction_value,
                    "movers": cached["movers"],
                }

            range_start = end_date - timedelta(days=6)
            range_start_int = date_to_int(range_start)
            row = conn.execute(
                """
                SELECT MIN(date) AS min_date
                FROM bars
                WHERE timeframe = 'daily'
                  AND date BETWEEN ? AND ?
                """,
                (range_start_int, end_int),
            ).fetchone()
            start_int = row["min_date"] or range_start_int
            start_date = date_int_to_date(start_int)

            sql_direction = "DESC" if direction_value == "top" else "ASC"
            movers = fetch_weekly_movers(conn, start_int, end_int, sql_direction, limit)
            symbols = [mover["symbol"] for mover in movers]
            series_map = fetch_weekly_series(conn, symbols, start_int, end_int)
            for mover in movers:
                mover["series"] = series_map.get(mover["symbol"], [])
            with MOVERS_CACHE_LOCK:
                set_cached_movers(
                    direction_value,
                    end_int,
                    start_date.isoformat(),
                    end_date.isoformat(),
                    movers,
                )
            return {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "direction": direction_value,
                "movers": movers,
            }

        with MOVERS_CACHE_LOCK:
            cached_top = get_cached_movers("top", end_int)
            cached_bottom = get_cached_movers("bottom", end_int)
        if cached_top and cached_bottom:
            return {
                "start": cached_top["start"],
                "end": cached_top["end"],
                "top": cached_top["movers"],
                "bottom": cached_bottom["movers"],
            }

        range_start = end_date - timedelta(days=6)
        range_start_int = date_to_int(range_start)
        row = conn.execute(
            """
            SELECT MIN(date) AS min_date
            FROM bars
            WHERE timeframe = 'daily'
              AND date BETWEEN ? AND ?
            """,
            (range_start_int, end_int),
        ).fetchone()
        start_int = row["min_date"] or range_start_int
        start_date = date_int_to_date(start_int)

        top = fetch_weekly_movers(conn, start_int, end_int, "DESC", limit)
        bottom = fetch_weekly_movers(conn, start_int, end_int, "ASC", limit)
        top_series = fetch_weekly_series(conn, [m["symbol"] for m in top], start_int, end_int)
        bottom_series = fetch_weekly_series(conn, [m["symbol"] for m in bottom], start_int, end_int)
        for mover in top:
            mover["series"] = top_series.get(mover["symbol"], [])
        for mover in bottom:
            mover["series"] = bottom_series.get(mover["symbol"], [])
        with MOVERS_CACHE_LOCK:
            set_cached_movers("top", end_int, start_date.isoformat(), end_date.isoformat(), top)
            set_cached_movers("bottom", end_int, start_date.isoformat(), end_date.isoformat(), bottom)

        return {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "top": top,
            "bottom": bottom,
        }
    finally:
        conn.close()


@app.get("/api/weekly-insights")
def weekly_insights(end_date: str | None = None):
    return build_weekly_insights(end_date=end_date)


@app.post("/api/admin/weekly-insights/refresh")
def weekly_insights_refresh(end_date: str | None = None):
    return build_weekly_insights(force_refresh=True, end_date=end_date)


@app.get("/api/weekly-alerts")
def weekly_alerts(end_date: str | None = None):
    return build_weekly_alerts(end_date=end_date)


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

@app.get("/api/getCurrentTickerConditions")
def get_market_conditions(symbol: str = Query(..., min_length=1)):
    today = datetime.date.today()
    market_conditions, _ = build_full_features([symbol.replace(".US", "")], today, today)
    feature_explanations = get_feature_explanations()
    xgboost = XGBoostInvestor.XGBoostInvestor()
    xgboost.load('xg_boost_investor/model_save/model/xgboost_investor')
    market_conditions_df = pd.DataFrame(market_conditions)
    market_conditions_df = market_conditions_df.reset_index(drop=True)
    X_test, _, _, _ = xgboost.prepare_predictions(market_conditions_df, pd.DataFrame([{'ret_1d': 0}]))
    prediction = xgboost.predict(X_test)
    return {"market_conditions": market_conditions.iloc[-1].to_dict(), "feature_explanations": feature_explanations,
            "prediction": float(prediction[0])}
