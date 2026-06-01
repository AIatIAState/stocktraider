import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException


def _sqlite_uri(path: Path, mode: str) -> str:
    resolved = path.resolve()
    return f"file:{resolved.as_posix()}?mode={mode}"


def test_sqlite_uri_readonly():
    uri = _sqlite_uri(Path("/tmp/test.db"), "ro")
    assert uri.endswith("?mode=ro")
    assert "test.db" in uri


def test_sqlite_uri_readwrite():
    uri = _sqlite_uri(Path("/tmp/test.db"), "rw")
    assert uri.endswith("?mode=rw")


def test_get_connection_missing_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nonexistent.db"))
    # Re-import so DB_PATH picks up the env var
    import importlib
    import sys
    sys.modules.pop("connector", None)
    import connector
    importlib.reload(connector)

    with pytest.raises(HTTPException) as exc_info:
        connector.get_connection()
    assert exc_info.value.status_code == 500


def test_get_connection_success(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    sqlite3.connect(str(db_file)).close()

    monkeypatch.setenv("DB_PATH", str(db_file))
    import importlib
    import sys
    sys.modules.pop("connector", None)
    import connector
    importlib.reload(connector)

    conn = connector.get_connection()
    assert conn is not None
    conn.close()
