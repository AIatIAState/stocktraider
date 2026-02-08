import argparse
import datetime as dt
import logging
import time
from typing import Iterable

import pandas as pd
import yfinance as yf

from Connector import get_connection

LOGGER = logging.getLogger("uvicorn.error")

DEFAULT_TIMEFRAME = "daily"
DEFAULT_PER = "D"
DEFAULT_TIME = 0
DEFAULT_OPENINT = 0.0
DEFAULT_CHUNK_SIZE = 50
DEFAULT_THROTTLE_SECONDS = 0.0


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}. Use YYYY-MM-DD.") from exc


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _to_yfinance_symbol(symbol: str) -> str:
    symbol_value = symbol.strip().upper()
    if symbol_value.endswith(".US"):
        return symbol_value[:-3]
    return symbol_value


def _load_symbols(conn, symbols: list[str] | None, limit: int | None) -> list[dict]:
    if symbols:
        cleaned = [value.strip().upper() for value in symbols if value.strip()]
        placeholders = ",".join("?" for _ in cleaned)
        rows = conn.execute(
            f"""
            SELECT symbol, exchange, asset_type, country
            FROM symbols
            WHERE symbol IN ({placeholders})
            ORDER BY symbol
            """,
            cleaned,
        ).fetchall()
    else:
        sql = """
            SELECT symbol, exchange, asset_type, country
            FROM symbols
            ORDER BY symbol
        """
        if limit:
            rows = conn.execute(f"{sql} LIMIT ?", (limit,)).fetchall()
        else:
            rows = conn.execute(sql).fetchall()

    return [dict(row) for row in rows]


def _split_download(data: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    if data is None or data.empty:
        return {}
    if isinstance(data.columns, pd.MultiIndex):
        level0 = data.columns.get_level_values(0)
        if any(ticker in level0 for ticker in tickers):
            return {ticker: data[ticker] for ticker in tickers if ticker in level0}
        level1 = data.columns.get_level_values(1)
        return {
            ticker: data.xs(ticker, level=1, axis=1)
            for ticker in tickers
            if ticker in level1
        }
    if len(tickers) == 1:
        return {tickers[0]: data}
    return {}


def _safe_float(value) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def update_daily_bars(
    *,
    start_date: dt.date,
    end_date: dt.date,
    symbols: list[str] | None = None,
    limit: int | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
) -> dict:
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    conn = get_connection(readonly=False)
    try:
        symbol_rows = _load_symbols(conn, symbols, limit)
        if not symbol_rows:
            return {
                "symbols": 0,
                "yf_symbols": 0,
                "rows_fetched": 0,
                "rows_inserted": 0,
            }

        yf_to_meta: dict[str, list[dict]] = {}
        for row in symbol_rows:
            yf_symbol = _to_yfinance_symbol(row["symbol"])
            yf_to_meta.setdefault(yf_symbol, []).append(row)

        start_str = start_date.isoformat()
        end_exclusive = end_date + dt.timedelta(days=1)
        end_str = end_exclusive.isoformat()

        total_rows = 0
        total_inserted = 0

        for chunk in _chunked(list(yf_to_meta.keys()), chunk_size):
            LOGGER.info("Fetching %s symbols from yfinance", len(chunk))
            data = yf.download(
                tickers=" ".join(chunk),
                start=start_str,
                end=end_str,
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
            )
            frames = _split_download(data, chunk)
            batch_rows: list[tuple] = []

            for yf_symbol, frame in frames.items():
                if frame.empty:
                    continue
                for idx, row in frame.iterrows():
                    date_value = int(idx.date().strftime("%Y%m%d"))
                    open_value = _safe_float(row.get("Open"))
                    high_value = _safe_float(row.get("High"))
                    low_value = _safe_float(row.get("Low"))
                    close_value = _safe_float(row.get("Close"))
                    volume_value = _safe_float(row.get("Volume"))

                    if all(value is None for value in (open_value, high_value, low_value, close_value)):
                        continue

                    for meta in yf_to_meta.get(yf_symbol, []):
                        batch_rows.append(
                            (
                                meta["symbol"],
                                DEFAULT_PER,
                                date_value,
                                DEFAULT_TIME,
                                open_value,
                                high_value,
                                low_value,
                                close_value,
                                volume_value,
                                DEFAULT_OPENINT,
                                DEFAULT_TIMEFRAME,
                                meta.get("exchange"),
                                meta.get("asset_type"),
                                meta.get("country"),
                            )
                        )

            if not batch_rows:
                if throttle_seconds:
                    time.sleep(throttle_seconds)
                continue

            total_rows += len(batch_rows)
            changes_before = conn.total_changes
            # Commit per chunk to keep write locks short.
            with conn:
                conn.executemany(
                    """
                    INSERT INTO bars (
                        symbol, per, date, time, open, high, low, close, volume, openint,
                        timeframe, exchange, asset_type, country
                    )
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM bars WHERE symbol = ? AND date = ? AND time = ? AND timeframe = ?
                    )
                    """,
                    [
                        (*row, row[0], row[2], row[3], row[10])
                        for row in batch_rows
                    ],
                )
            total_inserted += conn.total_changes - changes_before

            if throttle_seconds:
                time.sleep(throttle_seconds)

        return {
            "symbols": len(symbol_rows),
            "yf_symbols": len(yf_to_meta),
            "rows_fetched": total_rows,
            "rows_inserted": total_inserted,
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Update daily bars using yfinance.")
    parser.add_argument("--start", type=_parse_date, help="Start date (YYYY-MM-DD).")
    parser.add_argument("--end", type=_parse_date, help="End date (YYYY-MM-DD).")
    parser.add_argument("--symbols", nargs="*", help="Specific symbols to update (DB symbols).")
    parser.add_argument("--limit", type=int, help="Limit number of symbols for testing.")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--throttle", type=float, default=DEFAULT_THROTTLE_SECONDS)

    args = parser.parse_args()

    end_date = args.end or dt.date.today()
    start_date = args.start or (end_date - dt.timedelta(days=6))

    summary = update_daily_bars(
        start_date=start_date,
        end_date=end_date,
        symbols=args.symbols,
        limit=args.limit,
        chunk_size=args.chunk_size,
        throttle_seconds=args.throttle,
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
