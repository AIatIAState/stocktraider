
import os
import sqlite3
from pathlib import Path

from fastapi import HTTPException

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parents[1] / "data" / "stocks.db"))


def _sqlite_uri(path: Path, mode: str) -> str:
    resolved = path.resolve()
    return f"file:{resolved.as_posix()}?mode={mode}"


def get_connection(*, readonly: bool = False) -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Database not found at {DB_PATH}")

    try:
        if readonly:
            conn = sqlite3.connect(_sqlite_uri(DB_PATH, "ro"), uri=True, timeout=30)
        else:
            conn = sqlite3.connect(DB_PATH, timeout=30)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to open database at {DB_PATH}: {exc}") from exc
    conn.row_factory = sqlite3.Row
    return conn
