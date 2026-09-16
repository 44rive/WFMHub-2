from pathlib import Path

from wfmhub2.core.settings import Settings
from wfmhub2.storage.sqlite import connect, initialize


def test_control_database_initializes(tmp_path: Path) -> None:
    db = tmp_path / "control.sqlite"
    initialize(db)

    with connect(db) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

    assert {"source_manifest", "refresh_run", "decision_log", "scenario"} <= tables


def test_greenfield_paths(tmp_path: Path) -> None:
    settings = Settings(home=tmp_path)
    assert settings.control_db_path == tmp_path / "data" / "control.sqlite"
    assert settings.ducklake_catalog_path == tmp_path / "data" / "lake" / "catalog.ducklake"
    assert settings.ducklake_data_path == tmp_path / "data" / "lake" / "files"
