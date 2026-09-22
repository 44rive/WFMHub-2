from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from wfmhub2_compat.attendance_model import build_attendance_model, load_attendance_policy
from wfmhub2_compat.refresh_store import RefreshStore, SourceVersion
from wfmhub2_compat.source_contracts import SourceContractError

EMPTY_CATALOG = hashlib.sha256(b"").hexdigest()


def _publish_fixture(connection: sqlite3.Connection, generation_id: int) -> None:
    agents = ("A", "B", "C", "D", "E", "F", "G")
    connection.executemany(
        """
        INSERT INTO wfm_agent_roster (
            generation_id, client_id, employment_status, agent_name, fte,
            source_key, source_sheet, source_row
        ) VALUES (?, ?, 'Active', ?, 1, 'FTE/FTE Count.xlsx', 'Agent', ?)
        """,
        [(generation_id, agent, f"Agent {agent}", index) for index, agent in enumerate(agents, 2)],
    )
    connection.executemany(
        """
        INSERT INTO wfm_schedule_shift (
            generation_id, business_date, roster_client_id, source_agent_id,
            agent_name, assignment, assignment_type, scheduled_start,
            scheduled_end, schedule_state, is_overnight, scope_match,
            source_key, source_row, source_column
        ) VALUES (?, '2026-08-01', ?, ?, ?, 'Work', 'Work',
                  '2026-08-01T08:00:00', '2026-08-01T16:00:00',
                  'SHIFT', 0, 'id', 'schedule.txt', ?, 3)
        """,
        [
            (generation_id, agent, agent, f"Agent {agent}", index)
            for index, agent in enumerate(agents[:5], 2)
        ],
    )
    connection.execute(
        """
        INSERT INTO wfm_schedule_shift (
            generation_id, business_date, roster_client_id, source_agent_id,
            agent_name, assignment, assignment_type, scheduled_start,
            scheduled_end, schedule_state, is_overnight, scope_match,
            source_key, source_row, source_column
        ) VALUES (?, '2026-08-01', 'F', 'F', 'Agent F', 'Work', 'Work',
                  '2026-08-01T22:00:00', '2026-08-02T06:00:00',
                  'SHIFT', 1, 'id', 'schedule.txt', 7, 3)
        """,
        (generation_id,),
    )
    connection.execute(
        """
        INSERT INTO wfm_schedule_shift (
            generation_id, business_date, roster_client_id, source_agent_id,
            agent_name, assignment, assignment_type, scheduled_start,
            scheduled_end, schedule_state, is_overnight, scope_match,
            source_key, source_row, source_column
        ) VALUES (?, '2026-08-01', 'G', 'G', 'Agent G', 'Work', 'Work',
                  '2026-08-01T08:00:00', '2026-08-01T16:00:00',
                  'SHIFT', 0, 'id', 'schedule.txt', 8, 3)
        """,
        (generation_id,),
    )
    status_rows = [
        ("1", "Logged Off", "Logged Off", "2026-08-01T08:00:00", "2026-08-01T08:10:00"),
        ("2", "Available", "Productive", "2026-08-01T08:10:00", "2026-08-01T12:00:00"),
        ("3", "Logged Off", "Logged Off", "2026-08-01T12:00:00", "2026-08-01T12:10:00"),
        ("4", "Available", "Productive", "2026-08-01T12:10:00", "2026-08-01T16:00:00"),
    ]
    connection.executemany(
        """
        INSERT INTO wfm_raw_agent_status (
            generation_id, source_key, source_row, serial_number, extract_date,
            source_agent_id, roster_client_id, agent_name, status,
            actual_category, status_start, status_end, duration_seconds, queue,
            scope_match
        ) VALUES (?, 'Storm/Agent Status/status.csv', ?, ?, '2026-08-01',
                  'A', 'A', 'Agent A', ?, ?, ?, ?, 600, 'Q1', 'id')
        """,
        [
            (generation_id, index, serial, status, category, start, end)
            for index, (serial, status, category, start, end) in enumerate(status_rows, 2)
        ],
    )
    connection.execute(
        """
        INSERT INTO wfm_raw_agent_status (
            generation_id, source_key, source_row, serial_number, extract_date,
            source_agent_id, roster_client_id, agent_name, status,
            actual_category, status_start, status_end, duration_seconds, queue,
            scope_match
        ) VALUES (?, 'Storm/Agent Status/status.csv', 8, '8', '2026-08-01',
                  'B', 'B', 'Agent B', 'Available', 'Productive',
                  '2026-08-01T10:00:00', '2026-08-01T11:00:00', 3600, 'Q1', 'id')
        """,
        (generation_id,),
    )
    connection.execute(
        """
        INSERT INTO wfm_raw_agent_status (
            generation_id, source_key, source_row, serial_number, extract_date,
            source_agent_id, roster_client_id, agent_name, status,
            actual_category, status_start, status_end, duration_seconds, queue,
            scope_match
        ) VALUES (?, 'Storm/Agent Status/status.csv', 9, '9', '2026-08-01',
                  'G', 'G', 'Agent G', 'Available', 'Productive',
                  '2026-08-01T08:30:00', '2026-08-01T14:54:00', 23040, 'Q1', 'id')
        """,
        (generation_id,),
    )
    connection.execute(
        """
        INSERT INTO wfm_time_off (
            generation_id, source_kind, client_id, start_date, end_date,
            day_coverage, absence_type, record_status, overlay_eligible,
            source_key, source_sheet, source_row
        ) VALUES (?, 'AWAY', 'F', '2026-08-01', '2026-08-01', 'FULL_DAY',
                  'Long sickness', 'ACTIVE', 1, 'FTE/FTE Count.xlsx', 'AWAY', 2)
        """,
        (generation_id,),
    )
    lilo_rows = [
        (2, "A", "2026-08-01T07:55:00", "2026-08-01T13:00:00"),
        (3, "B", "2026-08-01T08:05:00", "2026-08-01T15:50:00"),
        (4, "C", None, None),
        (5, "E", "2026-08-01T10:00:00", "2026-08-01T16:00:00"),
        (6, "G", "2026-08-01T08:00:00", "2026-08-01T16:00:00"),
    ]
    connection.executemany(
        """
        INSERT INTO wfm_raw_lilo (
            generation_id, source_key, source_row, extract_date, source_agent_id,
            roster_client_id, agent_name, first_login, raw_last_logout,
            last_logout, overnight_adjusted, scope_match
        ) VALUES (?, 'Storm/LILO/lilo.csv', ?, '2026-08-01', ?, ?, ?, ?, ?, ?, 0, 'id')
        """,
        [
            (
                generation_id,
                source_row,
                agent,
                agent,
                f"Agent {agent}",
                first,
                last,
                last,
            )
            for source_row, agent, first, last in lilo_rows
        ],
    )
    connection.execute(
        """
        INSERT INTO wfm_time_off (
            generation_id, source_kind, client_id, start_date, end_date,
            day_coverage, start_time, end_time, absence_type, record_status,
            overlay_eligible, source_key, source_sheet, source_row
        ) VALUES (?, 'PTO', 'E', '2026-08-01', '2026-08-01', 'PARTIAL_DAY',
                  '08:00:00', '10:00:00', 'Vacation', 'APPROVED', 1,
                  'FTE/FTE Count.xlsx', 'PTO', 2)
        """,
        (generation_id,),
    )
    build_attendance_model(
        connection,
        generation_id,
        policy=load_attendance_policy(),
        as_of=datetime(2026, 8, 2, 12),
    )


def test_attendance_status_primary_lilo_fallback_and_unknown_are_explicit(
    tmp_path: Path,
) -> None:
    store = RefreshStore(tmp_path / "control.sqlite")
    generation = store.start_generation(catalog_sha256=EMPTY_CATALOG, model_version="attendance-v1")
    store.stage_source(
        generation,
        SourceVersion(
            "agent_status",
            "Storm/Agent Status/status.csv",
            1,
            1,
            "a" * 64,
            "synthetic-status-v1",
            "synthetic-policy-v1",
            6,
        ),
    )
    store.stage_source(
        generation,
        SourceVersion(
            "lilo",
            "Storm/LILO/lilo.csv",
            1,
            1,
            "b" * 64,
            "synthetic-lilo-v1",
            "synthetic-policy-v1",
            5,
        ),
    )
    store.activate_generation(generation, publish=_publish_fixture)

    with sqlite3.connect(store.path) as connection:
        connection.row_factory = sqlite3.Row
        rows = {
            str(row["roster_client_id"]): row
            for row in connection.execute(
                """
                SELECT roster_client_id, actual_first_seen, actual_last_seen,
                       actual_evidence, status_is_primary, status_coverage_ratio,
                       planned_work_minutes, planned_time_off_minutes,
                       late_minutes, early_leave_minutes, no_show_minutes,
                       attendance_result, evidence_state
                FROM wfm_attendance_agent_day WHERE generation_id = ?
                """,
                (generation,),
            )
        }
        gaps = connection.execute(
            """
            SELECT roster_client_id, gap_type, gap_start, gap_end, gap_minutes
            FROM wfm_attendance_gap WHERE generation_id = ?
            ORDER BY roster_client_id, gap_start, gap_type
            """,
            (generation,),
        ).fetchall()

    assert rows["A"]["status_is_primary"] == 1
    assert rows["A"]["actual_first_seen"] == "2026-08-01T08:10:00"
    assert rows["A"]["actual_last_seen"] == "2026-08-01T16:00:00"
    assert rows["A"]["attendance_result"] == "Late"
    assert rows["A"]["late_minutes"] == 10
    assert rows["A"]["early_leave_minutes"] == 0
    assert rows["B"]["status_is_primary"] == 0
    assert rows["B"]["actual_evidence"] == "LILO+AGENT_STATUS"
    assert rows["B"]["actual_first_seen"] == "2026-08-01T08:05:00"
    assert rows["B"]["attendance_result"] == "Early leave"
    assert rows["B"]["late_minutes"] == 0
    assert rows["B"]["early_leave_minutes"] == 10
    assert rows["C"]["attendance_result"] == "No show"
    assert rows["C"]["no_show_minutes"] == 480
    assert rows["D"]["attendance_result"] == "Missing actual evidence"
    assert rows["D"]["evidence_state"] == "UNKNOWN"
    assert rows["D"]["no_show_minutes"] == 0
    assert rows["E"]["attendance_result"] == "Present - partial time off"
    assert rows["E"]["planned_work_minutes"] == 360
    assert rows["E"]["planned_time_off_minutes"] == 120
    assert rows["F"]["attendance_result"] == "Planned absence"
    assert rows["F"]["planned_work_minutes"] == 0
    assert rows["F"]["planned_time_off_minutes"] == 480
    assert abs(float(rows["G"]["status_coverage_ratio"]) - 0.8) < 1e-9
    assert rows["G"]["status_is_primary"] == 1
    assert rows["G"]["actual_first_seen"] == "2026-08-01T08:30:00"
    assert rows["G"]["actual_last_seen"] == "2026-08-01T14:54:00"
    assert rows["G"]["attendance_result"] == "Late + early leave"
    assert {(row[0], row[1], row[4]) for row in gaps} == {
        ("A", "LATE", 10),
        ("A", "LOGGED_OFF", 10),
        ("B", "EARLY_LEAVE", 10),
        ("C", "NO_SHOW", 480),
        ("G", "LATE", 30),
        ("G", "EARLY_LEAVE", 66),
    }
    assert (
        "A",
        "LOGGED_OFF",
        "2026-08-01T12:00:00",
        "2026-08-01T12:10:00",
        10,
    ) in [tuple(row) for row in gaps]


def test_attendance_policy_rejects_invalid_thresholds(tmp_path: Path) -> None:
    policy = tmp_path / "attendance.toml"
    policy.write_text(
        "[attendance]\nlate_tolerance_minutes = -1\n"
        "status_gap_tolerance_minutes = 5\nminimum_status_coverage = 0.8\n",
        encoding="utf-8",
    )

    with pytest.raises(SourceContractError, match="values are invalid"):
        load_attendance_policy(policy)
