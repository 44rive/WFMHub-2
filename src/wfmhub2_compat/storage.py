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
    bronze_generation_id INTEGER REFERENCES wfm_refresh_generation(id),
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

-- Generation-keyed Bronze evidence.  These tables preserve source location
-- and validation state; only a successful generation can become active.
CREATE TABLE IF NOT EXISTS wfm_raw_fte_agent (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_key TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    client_id TEXT,
    employment_status TEXT,
    agent_name TEXT,
    team_leader TEXT,
    ops_manager TEXT,
    lob TEXT,
    market TEXT,
    language TEXT,
    location TEXT,
    city TEXT,
    fte REAL,
    end_date TEXT,
    valid INTEGER NOT NULL CHECK(valid IN (0, 1)),
    validation_codes TEXT NOT NULL,
    PRIMARY KEY (generation_id, source_key, source_sheet, source_row)
);

CREATE TABLE IF NOT EXISTS wfm_raw_fte_time_off (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_key TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    source_kind TEXT NOT NULL CHECK(source_kind IN ('PTO', 'AWAY')),
    client_id TEXT,
    agent_name TEXT,
    start_date TEXT,
    end_date TEXT,
    day_coverage TEXT,
    start_time TEXT,
    end_time TEXT,
    absence_type TEXT,
    record_status TEXT,
    comment TEXT,
    valid INTEGER NOT NULL CHECK(valid IN (0, 1)),
    validation_codes TEXT NOT NULL,
    PRIMARY KEY (generation_id, source_key, source_sheet, source_row)
);

CREATE TABLE IF NOT EXISTS wfm_raw_schedule_shift (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_key TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    source_column INTEGER NOT NULL CHECK(source_column > 0),
    business_date TEXT NOT NULL,
    source_agent_id TEXT,
    roster_client_id TEXT,
    agent_name TEXT,
    raw_assignment TEXT NOT NULL,
    assignment TEXT,
    assignment_type TEXT,
    scheduled_start TEXT,
    scheduled_end TEXT,
    schedule_state TEXT NOT NULL CHECK(schedule_state IN ('SHIFT', 'OFF', 'INVALID')),
    is_overnight INTEGER NOT NULL CHECK(is_overnight IN (0, 1)),
    in_roster_scope INTEGER NOT NULL CHECK(in_roster_scope IN (0, 1)),
    scope_match TEXT NOT NULL CHECK(scope_match IN ('id', 'name', 'none')),
    valid INTEGER NOT NULL CHECK(valid IN (0, 1)),
    validation_codes TEXT NOT NULL,
    PRIMARY KEY (generation_id, source_key, source_row, source_column)
);

CREATE TABLE IF NOT EXISTS wfm_raw_lilo (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_key TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    extract_date TEXT NOT NULL,
    source_agent_id TEXT,
    roster_client_id TEXT NOT NULL,
    agent_name TEXT,
    first_login TEXT,
    raw_last_logout TEXT,
    last_logout TEXT,
    overnight_adjusted INTEGER NOT NULL CHECK(overnight_adjusted IN (0, 1)),
    scope_match TEXT NOT NULL CHECK(scope_match IN ('id', 'name')),
    PRIMARY KEY (generation_id, source_key, source_row)
);

CREATE TABLE IF NOT EXISTS wfm_raw_agent_status (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_key TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    serial_number TEXT NOT NULL,
    extract_date TEXT NOT NULL,
    source_agent_id TEXT,
    roster_client_id TEXT NOT NULL,
    agent_name TEXT,
    status TEXT,
    actual_category TEXT NOT NULL CHECK(actual_category IN (
        'Productive', 'Auxiliary', 'Break', 'Lunch', 'Unavailable', 'Logged Off'
    )),
    status_start TEXT NOT NULL,
    status_end TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK(duration_seconds > 0),
    queue TEXT,
    scope_match TEXT NOT NULL CHECK(scope_match IN ('id', 'name')),
    PRIMARY KEY (generation_id, source_key, source_row)
);

CREATE TABLE IF NOT EXISTS wfm_raw_call_leg (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_key TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    call_key TEXT NOT NULL,
    interaction_key TEXT NOT NULL,
    business_date TEXT NOT NULL,
    call_start TEXT NOT NULL,
    call_end TEXT,
    communication_type TEXT,
    call_direction TEXT,
    business_partner_id TEXT,
    lob TEXT,
    service TEXT,
    call_reference_number TEXT,
    call_id TEXT,
    call_progress TEXT,
    queue_wait_seconds INTEGER,
    queue_id TEXT,
    queue TEXT,
    call_treatment TEXT,
    source_agent_id TEXT,
    roster_client_id TEXT,
    agent_name TEXT,
    clearing_party TEXT,
    talk_seconds INTEGER,
    hold_seconds INTEGER,
    wrap_seconds INTEGER,
    completion_code TEXT,
    transferred INTEGER CHECK(transferred IS NULL OR transferred IN (0, 1)),
    shared_call_reference TEXT,
    ringing_seconds INTEGER,
    internal INTEGER CHECK(internal IS NULL OR internal IN (0, 1)),
    direct INTEGER CHECK(direct IS NULL OR direct IN (0, 1)),
    language TEXT,
    post_call_survey_mode TEXT,
    pcs_status TEXT,
    raw_payload_json TEXT NOT NULL,
    service_scope TEXT,
    comparison_scope TEXT,
    designation TEXT,
    mapping_status TEXT NOT NULL CHECK(mapping_status IN ('MAPPED', 'FALLBACK_LOB', 'UNMAPPED')),
    agent_eligible INTEGER NOT NULL CHECK(agent_eligible IN (0, 1)),
    service_eligible INTEGER NOT NULL CHECK(service_eligible IN (0, 1)),
    scope_match TEXT NOT NULL CHECK(scope_match IN ('id', 'name', 'queue')),
    validation_codes TEXT NOT NULL,
    PRIMARY KEY (generation_id, source_key, source_row)
);

-- Generation-keyed Silver facts.  Consumers join these tables to the single
-- active-generation pointer rather than selecting the newest timestamp.
CREATE TABLE IF NOT EXISTS wfm_agent_roster (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    client_id TEXT NOT NULL,
    employment_status TEXT NOT NULL CHECK(employment_status IN ('Active', 'Leaver')),
    agent_name TEXT NOT NULL,
    team_leader TEXT,
    ops_manager TEXT,
    lob TEXT,
    market TEXT,
    language TEXT,
    location TEXT,
    city TEXT,
    fte REAL CHECK(fte IS NULL OR fte >= 0),
    eligible_through TEXT,
    source_key TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    PRIMARY KEY (generation_id, client_id)
);

CREATE TABLE IF NOT EXISTS wfm_time_off (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_kind TEXT NOT NULL CHECK(source_kind IN ('PTO', 'AWAY')),
    client_id TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    day_coverage TEXT NOT NULL CHECK(day_coverage IN ('FULL_DAY', 'PARTIAL_DAY')),
    start_time TEXT,
    end_time TEXT,
    absence_type TEXT NOT NULL,
    record_status TEXT NOT NULL,
    overlay_eligible INTEGER NOT NULL CHECK(overlay_eligible IN (0, 1)),
    comment TEXT,
    source_key TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    PRIMARY KEY (generation_id, source_key, source_sheet, source_row),
    FOREIGN KEY (generation_id, client_id)
        REFERENCES wfm_agent_roster(generation_id, client_id)
);

CREATE TABLE IF NOT EXISTS wfm_schedule_shift (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    business_date TEXT NOT NULL,
    roster_client_id TEXT NOT NULL,
    source_agent_id TEXT,
    agent_name TEXT,
    assignment TEXT NOT NULL,
    assignment_type TEXT NOT NULL,
    scheduled_start TEXT,
    scheduled_end TEXT,
    schedule_state TEXT NOT NULL CHECK(schedule_state IN ('SHIFT', 'OFF')),
    is_overnight INTEGER NOT NULL CHECK(is_overnight IN (0, 1)),
    scope_match TEXT NOT NULL CHECK(scope_match IN ('id', 'name')),
    source_key TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    source_column INTEGER NOT NULL CHECK(source_column > 0),
    PRIMARY KEY (generation_id, source_key, source_row, source_column),
    FOREIGN KEY (generation_id, roster_client_id)
        REFERENCES wfm_agent_roster(generation_id, client_id)
);

CREATE TABLE IF NOT EXISTS wfm_call_leg (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    source_key TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row > 0),
    call_key TEXT NOT NULL,
    interaction_key TEXT NOT NULL,
    business_date TEXT NOT NULL,
    call_start TEXT NOT NULL,
    call_end TEXT,
    communication_type TEXT,
    call_direction TEXT,
    business_partner_id TEXT,
    lob TEXT,
    service TEXT,
    call_reference_number TEXT,
    call_id TEXT,
    call_progress TEXT,
    queue_wait_seconds INTEGER,
    queue_id TEXT,
    queue TEXT,
    call_treatment TEXT,
    source_agent_id TEXT,
    roster_client_id TEXT,
    agent_name TEXT,
    clearing_party TEXT,
    talk_seconds INTEGER,
    hold_seconds INTEGER,
    wrap_seconds INTEGER,
    completion_code TEXT,
    transferred INTEGER CHECK(transferred IS NULL OR transferred IN (0, 1)),
    shared_call_reference TEXT,
    ringing_seconds INTEGER,
    internal INTEGER CHECK(internal IS NULL OR internal IN (0, 1)),
    direct INTEGER CHECK(direct IS NULL OR direct IN (0, 1)),
    language TEXT,
    post_call_survey_mode TEXT,
    pcs_status TEXT,
    raw_payload_json TEXT NOT NULL,
    service_scope TEXT,
    comparison_scope TEXT,
    designation TEXT,
    mapping_status TEXT NOT NULL CHECK(mapping_status IN ('MAPPED', 'FALLBACK_LOB', 'UNMAPPED')),
    agent_eligible INTEGER NOT NULL CHECK(agent_eligible IN (0, 1)),
    service_eligible INTEGER NOT NULL CHECK(service_eligible IN (0, 1)),
    scope_match TEXT NOT NULL CHECK(scope_match IN ('id', 'name', 'queue')),
    validation_codes TEXT NOT NULL,
    PRIMARY KEY (generation_id, call_key)
);

CREATE TABLE IF NOT EXISTS wfm_service_interval (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    business_date TEXT NOT NULL,
    interval_start TEXT NOT NULL,
    interval_end TEXT NOT NULL,
    source_system TEXT NOT NULL CHECK(source_system = 'CALL_BY_CALL'),
    service_scope TEXT NOT NULL,
    comparison_scope TEXT NOT NULL,
    queue TEXT NOT NULL,
    designation TEXT NOT NULL,
    language TEXT NOT NULL,
    offered INTEGER NOT NULL CHECK(offered >= 0),
    answered INTEGER NOT NULL CHECK(answered >= 0),
    abandoned INTEGER NOT NULL CHECK(abandoned >= 0),
    short_abandoned INTEGER NOT NULL CHECK(short_abandoned >= 0),
    abandoned_within_target INTEGER NOT NULL CHECK(abandoned_within_target >= 0),
    answered_within_target INTEGER NOT NULL CHECK(answered_within_target >= 0),
    talk_seconds INTEGER NOT NULL,
    hold_seconds INTEGER NOT NULL,
    wrap_seconds INTEGER NOT NULL,
    handled_seconds INTEGER NOT NULL,
    call_legs INTEGER NOT NULL CHECK(call_legs >= 0),
    transferred_legs INTEGER NOT NULL CHECK(transferred_legs >= 0),
    source_files_json TEXT NOT NULL,
    mapping_sha256 TEXT NOT NULL,
    policy_fingerprint TEXT NOT NULL,
    PRIMARY KEY (
        generation_id, interval_start, source_system, service_scope,
        comparison_scope, queue, designation, language
    )
);

CREATE TABLE IF NOT EXISTS wfm_attendance_agent_day (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    agent_day_key TEXT NOT NULL,
    business_date TEXT NOT NULL,
    roster_client_id TEXT NOT NULL,
    assignment TEXT NOT NULL,
    assignment_type TEXT NOT NULL,
    scheduled_start TEXT,
    scheduled_end TEXT,
    scheduled_minutes INTEGER NOT NULL CHECK(scheduled_minutes >= 0),
    planned_work_minutes INTEGER NOT NULL CHECK(planned_work_minutes >= 0),
    planned_time_off_minutes INTEGER NOT NULL CHECK(planned_time_off_minutes >= 0),
    actual_first_seen TEXT,
    actual_last_seen TEXT,
    actual_evidence TEXT NOT NULL CHECK(actual_evidence IN (
        'NONE', 'LILO', 'AGENT_STATUS', 'LILO+AGENT_STATUS'
    )),
    status_covered_minutes INTEGER NOT NULL CHECK(status_covered_minutes >= 0),
    status_coverage_ratio REAL NOT NULL CHECK(status_coverage_ratio >= 0),
    status_is_primary INTEGER NOT NULL CHECK(status_is_primary IN (0, 1)),
    raw_late_minutes INTEGER NOT NULL CHECK(raw_late_minutes >= 0),
    late_minutes INTEGER NOT NULL CHECK(late_minutes >= 0),
    early_leave_minutes INTEGER NOT NULL CHECK(early_leave_minutes >= 0),
    no_show_minutes INTEGER NOT NULL CHECK(no_show_minutes >= 0),
    attendance_result TEXT NOT NULL,
    evidence_state TEXT NOT NULL CHECK(evidence_state IN (
        'NOT_REQUIRED', 'NOT_STARTED', 'PROVISIONAL', 'COMPLETE', 'UNKNOWN'
    )),
    status_source_loaded INTEGER NOT NULL CHECK(status_source_loaded IN (0, 1)),
    lilo_source_loaded INTEGER NOT NULL CHECK(lilo_source_loaded IN (0, 1)),
    lilo_row_present INTEGER NOT NULL CHECK(lilo_row_present IN (0, 1)),
    evaluation_as_of TEXT NOT NULL,
    schedule_source_key TEXT NOT NULL,
    source_keys_json TEXT NOT NULL,
    policy_fingerprint TEXT NOT NULL,
    PRIMARY KEY (generation_id, agent_day_key),
    FOREIGN KEY (generation_id, roster_client_id)
        REFERENCES wfm_agent_roster(generation_id, client_id)
);

CREATE TABLE IF NOT EXISTS wfm_attendance_gap (
    generation_id INTEGER NOT NULL REFERENCES wfm_refresh_generation(id),
    gap_key TEXT NOT NULL,
    agent_day_key TEXT NOT NULL,
    business_date TEXT NOT NULL,
    roster_client_id TEXT NOT NULL,
    gap_type TEXT NOT NULL CHECK(gap_type IN (
        'LATE', 'LOGGED_OFF', 'UNAVAILABLE', 'EARLY_LEAVE', 'NO_SHOW'
    )),
    gap_start TEXT NOT NULL,
    gap_end TEXT NOT NULL,
    gap_minutes INTEGER NOT NULL CHECK(gap_minutes > 0),
    evidence_basis TEXT NOT NULL,
    source_keys_json TEXT NOT NULL,
    is_provisional INTEGER NOT NULL CHECK(is_provisional IN (0, 1)),
    policy_fingerprint TEXT NOT NULL,
    PRIMARY KEY (generation_id, gap_key),
    FOREIGN KEY (generation_id, agent_day_key)
        REFERENCES wfm_attendance_agent_day(generation_id, agent_day_key)
);

CREATE INDEX IF NOT EXISTS ix_wfm_roster_active_lookup
ON wfm_agent_roster(generation_id, client_id, eligible_through);

CREATE INDEX IF NOT EXISTS ix_wfm_schedule_active_date
ON wfm_schedule_shift(generation_id, business_date, roster_client_id);

CREATE INDEX IF NOT EXISTS ix_wfm_time_off_active_date
ON wfm_time_off(generation_id, start_date, end_date, client_id);

CREATE INDEX IF NOT EXISTS ix_wfm_time_off_agent_range
ON wfm_time_off(generation_id, client_id, start_date, end_date);

CREATE INDEX IF NOT EXISTS ix_wfm_lilo_active_date
ON wfm_raw_lilo(generation_id, extract_date, roster_client_id);

CREATE INDEX IF NOT EXISTS ix_wfm_lilo_agent_date
ON wfm_raw_lilo(generation_id, roster_client_id, extract_date);

CREATE INDEX IF NOT EXISTS ix_wfm_status_active_interval
ON wfm_raw_agent_status(generation_id, extract_date, roster_client_id, status_start);

CREATE INDEX IF NOT EXISTS ix_wfm_status_agent_interval
ON wfm_raw_agent_status(generation_id, roster_client_id, status_start, status_end);

CREATE INDEX IF NOT EXISTS ix_wfm_raw_call_key
ON wfm_raw_call_leg(generation_id, call_key);

CREATE INDEX IF NOT EXISTS ix_wfm_call_service_date
ON wfm_call_leg(generation_id, business_date, service_scope, queue);

CREATE INDEX IF NOT EXISTS ix_wfm_service_interval_scope
ON wfm_service_interval(generation_id, interval_start, service_scope);

CREATE INDEX IF NOT EXISTS ix_wfm_service_interval_date_scope
ON wfm_service_interval(generation_id, business_date, service_scope, comparison_scope,
                        interval_start, interval_end);

CREATE INDEX IF NOT EXISTS ix_wfm_attendance_date
ON wfm_attendance_agent_day(generation_id, business_date, evidence_state);

CREATE INDEX IF NOT EXISTS ix_wfm_attendance_gap_date
ON wfm_attendance_gap(generation_id, business_date, gap_type);
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
        manifest_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(wfm_source_manifest)")
        }
        if "bronze_generation_id" not in manifest_columns:
            connection.execute(
                "ALTER TABLE wfm_source_manifest ADD COLUMN bronze_generation_id INTEGER "
                "REFERENCES wfm_refresh_generation(id)"
            )
        connection.execute(
            """
            UPDATE wfm_source_manifest
            SET bronze_generation_id = generation_id
            WHERE state = 'present' AND bronze_generation_id IS NULL
            """
        )
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
