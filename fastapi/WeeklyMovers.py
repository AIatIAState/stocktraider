
import os
import threading
import time
from datetime import date
from fastapi import HTTPException

MOVERS_CACHE_TTL_SECONDS = 86400  # 24 hours
# In-memory cache to keep weekly movers fast between requests.
# Cache key is (direction, min_volume) to support filtered/unfiltered results independently.
MOVERS_CACHE_LOCK = threading.Lock()
MOVERS_CACHE: dict[str, dict] = {}


def _cache_key(direction: str, min_volume: int | None = None) -> str:
    return f"{direction}:{min_volume or 0}"


def get_cached_movers(direction: str, end_int: int, min_volume: int | None = None) -> dict | None:
    key = _cache_key(direction, min_volume)
    cache = MOVERS_CACHE.get(key)
    if cache is None:
        return None
    now = time.time()
    if cache["end_int"] == end_int and (now - cache["timestamp"]) < MOVERS_CACHE_TTL_SECONDS:
        if cache["movers"] is not None:
            return cache
    return None


def set_cached_movers(direction: str, end_int: int, start: str, end: str, movers: list[dict], min_volume: int | None = None) -> None:
    key = _cache_key(direction, min_volume)
    MOVERS_CACHE[key] = {
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


DEFAULT_MIN_VOLUME = int(os.getenv("WEEKLY_MOVERS_MIN_VOLUME", "2000000"))


def fetch_weekly_movers(conn, start_int: int, end_int: int, direction: str, limit: int, min_volume: int | None = None) -> list[dict]:
    if direction not in ("ASC", "DESC"):
        raise ValueError("direction must be ASC or DESC")

    volume_filter = ""
    volume_params: list[object] = []
    if min_volume is not None and min_volume > 0:
        volume_filter = """
              AND start_rows.symbol IN (
                  SELECT symbol FROM bars
                  WHERE timeframe = 'daily' AND date BETWEEN ? AND ?
                  GROUP BY symbol
                  HAVING AVG(volume) >= ?
              )
        """
        volume_params = [start_int, end_int, min_volume]

    # Use the start/end trading days to compute percent move for the week.
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
        WHERE start_rows.first_close >= 1.0
        {volume_filter}
        ORDER BY pct_change {direction}
        LIMIT ?
    """
    params: list[object] = [start_int, end_int, *volume_params, limit]
    rows = conn.execute(sql, params).fetchall()
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

