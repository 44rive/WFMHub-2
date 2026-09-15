import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS source_manifest (
    id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    parser_version TEXT NOT NULL,
    policy_fingerprint TEXT NOT NULL,
    min_business_date TEXT,
    max_business_date TEXT,
    row_count INTEGER,
    active INTEGER NOT NULL DEFAULT 1,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_path, content_sha256, parser_version, policy_fingerprint)
);

CREATE TABLE IF NOT EXISTS refresh_run (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL,
    files_seen INTEGER NOT NULL DEFAULT 0,
    files_changed INTEGER NOT NULL DEFAULT 0,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    service_scope TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    reason TEXT,
    expected_impact REAL,
    actual_impact REAL,
    metadata_json TEXT
);
"""


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
