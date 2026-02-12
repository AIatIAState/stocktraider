import argparse
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parents[1] / "data" / "stocks.db"))
BUSY_TIMEOUT_MS = int(os.getenv("DB_BUSY_TIMEOUT_MS", "30000"))

INDEX_NAME = "idx_bars_timeframe_date_symbol"
INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_bars_timeframe_date_symbol ON bars (timeframe, date, symbol)"


def _sqlite_uri(path: Path, mode: str) -> str:
    resolved = path.resolve()
    posix_path = resolved.as_posix()
    if resolved.is_absolute() and not posix_path.startswith("/"):
        posix_path = "/" + posix_path
    return f"file:{posix_path}?mode={mode}"


def _index_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def ensure_indexes() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    # Fast path: if indexes already exist, avoid opening the DB in write mode.
    ro_conn = sqlite3.connect(_sqlite_uri(DB_PATH, "ro"), uri=True, timeout=BUSY_TIMEOUT_MS / 1000)
    try:
        if _index_exists(ro_conn, INDEX_NAME):
            return
    finally:
        ro_conn.close()

    conn = sqlite3.connect(DB_PATH, timeout=BUSY_TIMEOUT_MS / 1000)
    try:
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        # Best-effort alignment with app settings; this avoids rollback-journal sidecars.
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.Error:
            pass

        # Index supports fast weekly movers queries by date and symbol.
        conn.execute(INDEX_SQL)
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
