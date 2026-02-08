import argparse
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parents[1] / "data" / "stocks.db"))


def ensure_indexes() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
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
