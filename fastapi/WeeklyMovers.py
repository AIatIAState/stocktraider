
import threading
import time
from datetime import date
from fastapi import HTTPException

MOVERS_CACHE_TTL_SECONDS = 10 * 60
MOVERS_CACHE_LOCK = threading.Lock()
MOVERS_CACHE: dict[str, dict] = {
    "top": {"timestamp": 0.0, "end_int": None, "start": None, "end": None, "movers": None},
    "bottom": {"timestamp": 0.0, "end_int": None, "start": None, "end": None, "movers": None},
}


def get_cached_movers(direction: str, end_int: int) -> dict | None:
    cache = MOVERS_CACHE[direction]
    now = time.time()
    if cache["end_int"] == end_int and (now - cache["timestamp"]) < MOVERS_CACHE_TTL_SECONDS:
        if cache["movers"] is not None:
            return cache
    return None


def set_cached_movers(direction: str, end_int: int, start: str, end: str, movers: list[dict]) -> None:
    MOVERS_CACHE[direction] = {
        "timestamp": time.time(),
        "end_int": end_int,
        "start": start,
        "end": end,
        "movers": movers,
    }


def date_int_to_date(value: int) -> date:
    value_str = str(value)
    if len(value_str) != 8:
        raise HTTPException(status_code=500, detail="Invalid date value in database")
    try:
        return date(int(value_str[:4]), int(value_str[4:6]), int(value_str[6:]))
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Invalid date value in database") from exc


def date_to_int(value: date) -> int:
    return int(value.strftime("%Y%m%d"))


def fetch_weekly_movers(conn, start_int: int, end_int: int, direction: str, limit: int) -> list[dict]:
    if direction not in ("ASC", "DESC"):
        raise ValueError("direction must be ASC or DESC")
    sql = f"""
        WITH start_rows AS (
            SELECT symbol, close AS first_close
            FROM bars
            WHERE timeframe = 'daily'
              AND date = ?
              AND close IS NOT NULL
        ),
        end_rows AS (
            SELECT symbol, close AS last_close
            FROM bars
            WHERE timeframe = 'daily'
              AND date = ?
              AND close IS NOT NULL
        )
        SELECT
            start_rows.symbol AS symbol,
            start_rows.first_close AS first_close,
            end_rows.last_close AS last_close,
            ((end_rows.last_close - start_rows.first_close) / start_rows.first_close) * 100.0 AS pct_change
        FROM start_rows
        JOIN end_rows ON end_rows.symbol = start_rows.symbol
        WHERE start_rows.first_close > 0
        ORDER BY pct_change {direction}
        LIMIT ?
    """
    rows = conn.execute(sql, (start_int, end_int, limit)).fetchall()
    return [dict(row) for row in rows]


def fetch_weekly_series(conn, symbols: list[str], start_int: int, end_int: int) -> dict[str, list[float]]:
    if not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    sql = f"""
        SELECT symbol, date, close
        FROM bars
        WHERE timeframe = 'daily'
          AND date BETWEEN ? AND ?
          AND symbol IN ({placeholders})
          AND close IS NOT NULL
        ORDER BY date ASC
    """
    rows = conn.execute(sql, (start_int, end_int, *symbols)).fetchall()
    series: dict[str, list[float]] = {symbol: [] for symbol in symbols}
    for row in rows:
        series[row["symbol"]].append(row["close"])
    return series

