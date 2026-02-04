

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from Connector import get_connection
from PatternRecognition import get_dtw_patterns
from Forecasting import get_forecast

app = FastAPI()

MAX_LIMIT = 50000

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/symbols")
def search_symbols(q: str = Query(..., min_length=1), limit: int = Query(25, ge=1, le=500)):
    query = q.strip().upper()
    conn = get_connection()
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

    conn = get_connection()
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