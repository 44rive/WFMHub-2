from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

REPORT_SCHEMA_VERSION = 1
MAX_REPORT_BYTES = 1024 * 1024
REPORT_PROFILE = "phase0.4-hybrid-compatibility-spike"
EXPECTED_PROBES = {
    "host_sqlite",
    "wasm_worker",
    "duckdb_opfs",
    "pyodide_forecasting",
    "highs_mip",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS compatibility_run (
    id INTEGER PRIMARY KEY,
    recorded_at TEXT NOT NULL,
    overall_status TEXT NOT NULL CHECK(overall_status IN ('pass', 'fail')),
    report_schema_version INTEGER NOT NULL,
    probe_count INTEGER NOT NULL,
    passed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    report_path TEXT NOT NULL
);

-- The compatible host owns these authoritative tables. The older native
-- prototype has a different source_manifest schema, so do not share its names.
CREATE TABLE IF NOT EXISTS wfm_refresh_generation (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('running', 'succeeded', 'failed')),
    base_generation_id INTEGER REFERENCES wfm_refresh_generation(id),
    catalog_sha256 TEXT NOT NULL,
    model_version TEXT NOT NULL,
    failure_reason TEXT
);

CREATE TABLE IF NOT EXISTS wfm_active_generation (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    generation_id INTEGER REFERENCES wfm_refresh_generation(id)
);

INSERT OR IGNORE INTO wfm_active_generation (singleton, generation_id) VALUES (1, NULL);

CREATE TABLE IF NOT EXISTS wfm_source_manifest (
    id INTEGER PRIMARY KEY,
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_type TEXT NOT NULL,
    source_key TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'present' CHECK(state IN ('present', 'removed')),
    file_size INTEGER NOT NULL CHECK(file_size >= 0),
    mtime_ns INTEGER NOT NULL CHECK(mtime_ns >= 0),
    content_sha256 TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    policy_fingerprint TEXT NOT NULL,
    row_count INTEGER CHECK(row_count IS NULL OR row_count >= 0),
    recorded_at TEXT NOT NULL,
    UNIQUE(generation_id, source_type, source_key)
);

CREATE INDEX IF NOT EXISTS ix_wfm_manifest_source
ON wfm_source_manifest(source_type, source_key, generation_id);

CREATE TABLE IF NOT EXISTS wfm_quality_issue (
    id INTEGER PRIMARY KEY,
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_key TEXT,
    issue_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'error')),
    details TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_wfm_quality_generation
ON wfm_quality_issue(generation_id, severity);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.executescript(SCHEMA)
        result = connection.execute("PRAGMA quick_check").fetchone()
        if result != ("ok",):
            raise RuntimeError(f"SQLite quick_check failed: {result!r}")
        connection.commit()


def _probe_counts(report: dict[str, Any]) -> tuple[int, int, int]:
    raw_probes = report.get("probes")
    if not isinstance(raw_probes, list):
        raise ValueError("report.probes must be a list")
    probes = cast(list[object], raw_probes)
    if len(probes) != len(EXPECTED_PROBES):
        raise ValueError(f"report.probes must contain exactly {len(EXPECTED_PROBES)} results")

    passed = 0
    failed = 0
    names: set[str] = set()
    for raw_probe in probes:
        if not isinstance(raw_probe, dict):
            raise ValueError("each probe result must be an object")
        probe = cast(dict[str, object], raw_probe)
        name = probe.get("name")
        if not isinstance(name, str) or name not in EXPECTED_PROBES:
            raise ValueError(f"unknown compatibility probe: {name!r}")
        if name in names:
            raise ValueError(f"duplicate compatibility probe: {name}")
        names.add(name)
        status = probe.get("status")
        if status == "pass":
            passed += 1
        elif status == "fail":
            failed += 1
        else:
            raise ValueError("each probe status must be pass or fail")
    return len(probes), passed, failed


def validate_report(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ValueError("compatibility report must be a JSON object")
    validated = cast(dict[str, Any], report)
    if validated.get("schemaVersion") != REPORT_SCHEMA_VERSION:
        raise ValueError(f"report schemaVersion must be {REPORT_SCHEMA_VERSION}")
    if validated.get("profile") != REPORT_PROFILE:
        raise ValueError(f"report profile must be {REPORT_PROFILE}")
    _, _, failed = _probe_counts(validated)
    expected_status = "pass" if failed == 0 else "fail"
    if validated.get("overallStatus") != expected_status:
        raise ValueError(f"report overallStatus must be {expected_status}")
    return validated


def save_report(home: Path, report: dict[str, Any]) -> Path:
    validated = validate_report(report)
    serialized = (
        json.dumps(
            validated,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if len(serialized.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("compatibility report exceeds the 1 MiB limit")

    report_dir = home / "data" / "compatibility"
    report_dir.mkdir(parents=True, exist_ok=True)
    destination = report_dir / "last-browser-report.json"
    temporary = report_dir / ".last-browser-report.json.tmp"
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    os.replace(temporary, destination)

    total, passed, failed = _probe_counts(validated)
    database = home / "data" / "control.sqlite"
    initialize_database(database)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute(
            """
            INSERT INTO compatibility_run (
                recorded_at,
                overall_status,
                report_schema_version,
                probe_count,
                passed_count,
                failed_count,
                report_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now(),
                "pass" if failed == 0 else "fail",
                REPORT_SCHEMA_VERSION,
                total,
                passed,
                failed,
                str(destination.resolve()),
            ),
        )
        connection.commit()
    return destination
