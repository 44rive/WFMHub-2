from pathlib import Path

from wfmhub2.storage.duckdb import initialize as initialize_duckdb
from wfmhub2.storage.sqlite import initialize as initialize_sqlite


def test_storage_initialization(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "app.sqlite3"
    duckdb_path = tmp_path / "analytics.duckdb"
    initialize_sqlite(sqlite_path)
    initialize_duckdb(duckdb_path)
    assert sqlite_path.exists()
    assert duckdb_path.exists()
