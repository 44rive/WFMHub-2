from __future__ import annotations

import csv
import hashlib
import importlib
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

import pytest

from wfmhub2_compat.refresh_store import RefreshStore
from wfmhub2_compat.source_contracts import (
    SourceContractError,
    SourceSnapshot,
    make_source_publish,
    parse_fte_workbook,
    parse_start_end_times,
    stage_findings,
    stage_sources,
)

EMPTY_CATALOG = hashlib.sha256(b"").hexdigest()
AGENT_HEADERS = [
    "Client ID",
    "Status",
    "Name",
    "Team leader",
    "Ops Manager",
    "LOB",
    "Market",
    "Language",
    "Location",
    "City",
    "FTE",
    "End date if leaver",
]
PTO_HEADERS = [
    "Client ID",
    "Name",
    "Start date",
    "End date",
    "Day coverage",
    "Start time",
    "End time",
    "PTO type",
    "Approval status",
    "Comment",
]
AWAY_HEADERS = [
    "Client ID",
    "Name",
    "Start date",
    "End date",
    "Away type",
    "Case status",
    "Comment",
]


def write_fte(
    path: Path,
    *,
    agents: Sequence[Sequence[object]],
    pto: Sequence[Sequence[object]] = (),
    away: Sequence[Sequence[object]] = (),
) -> None:
    module = importlib.import_module("openpyxl")
    workbook_factory = cast(Callable[[], Any], cast(Any, module).Workbook)
    workbook = workbook_factory()
    agent_sheet = workbook.active
    agent_sheet.title = "Agent"
    agent_sheet.append(AGENT_HEADERS)
    for row in agents:
        agent_sheet.append(list(row))
    pto_sheet = workbook.create_sheet("PTO")
    pto_sheet.append(PTO_HEADERS)
    for row in pto:
        pto_sheet.append(list(row))
    away_sheet = workbook.create_sheet("Away")
    away_sheet.append(AWAY_HEADERS)
    for row in away:
        away_sheet.append(list(row))
    workbook.save(path)
    workbook.close()


def write_schedule(path: Path, rows: Sequence[Sequence[str]], *dates: str) -> None:
    with path.open("w", encoding="cp1252", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["Name", "Data Source IDs", *dates])
        writer.writerows(rows)


def valid_fte(path: Path) -> None:
    write_fte(
        path,
        agents=(
            (
                "00123",
                "Active",
                "Ada Agent",
                "Lead A",
                "Ops A",
                "Alpha",
                "BE",
                "NL",
                "HQ",
                "City",
                1,
                None,
            ),
            (
                "00200",
                "Leaver",
                "Lee Leaver",
                "Lead B",
                "Ops A",
                "Alpha",
                "BE",
                "FR",
                "HQ",
                "City",
                0.8,
                "2026-08-01",
            ),
        ),
        pto=(
            (
                "00123",
                "Ada Agent",
                "2026-08-03",
                "2026-08-03",
                "Partial day",
                "08:00",
                "10:00",
                "Vacation",
                "Approved",
                "Synthetic",
            ),
        ),
        away=(("00123", "Ada Agent", "2026-08-10", None, "Long sickness", "Active", "Synthetic"),),
    )


def start(store: RefreshStore) -> int:
    return store.start_generation(catalog_sha256=EMPTY_CATALOG, model_version="sources-v1")


def test_source_contract_module_import_does_not_import_openpyxl() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    script = (
        "import wfmhub2_compat.source_contracts; "
        "raise SystemExit(1 if 'openpyxl' in sys.modules else 0)"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            f"import sys; sys.path.insert(0, {str(source_root)!r}); {script}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_fte_parser_preserves_text_id_effective_status_and_time_off(tmp_path: Path) -> None:
    path = tmp_path / "FTE Count.xlsx"
    valid_fte(path)

    snapshot = parse_fte_workbook(path, source_key="FTE/FTE Count.xlsx")

    assert [row.client_id for row in snapshot.agents] == ["00123", "00200"]
    assert snapshot.agents[0].employment_status == "Active"
    assert snapshot.agents[1].employment_status == "Leaver"
    assert snapshot.agents[1].eligible_on(snapshot.agents[1].end_date)  # type: ignore[arg-type]
    assert not snapshot.agents[1].eligible_on(snapshot.agents[1].end_date.replace(day=2))  # type: ignore[union-attr]
    assert [(row.source_kind, row.record_status) for row in snapshot.time_off] == [
        ("PTO", "APPROVED"),
        ("AWAY", "ACTIVE"),
    ]
    assert snapshot.time_off[0].start_time is not None
    assert snapshot.time_off[1].end_date is None
    assert not [finding for finding in snapshot.findings if finding.severity == "error"]


def test_fte_parser_reports_duplicates_unknown_status_and_invalid_register(tmp_path: Path) -> None:
    path = tmp_path / "FTE Count.xlsx"
    write_fte(
        path,
        agents=(
            ("007", "Leaver", "First Person", None, None, None, None, None, None, None, 1, None),
            ("007", "Mystery", "Second Person", None, None, None, None, None, None, None, 1, None),
        ),
        pto=(
            (
                "999",
                "Outside Person",
                "2026-08-03",
                "2026-08-04",
                "Partial day",
                "10:00",
                "09:00",
                "Vacation",
                "Approved",
                None,
            ),
        ),
    )

    snapshot = parse_fte_workbook(path, source_key="synthetic/fte.xlsx")

    codes = {finding.code for finding in snapshot.findings}
    assert {
        "DUPLICATE_CLIENT_ID",
        "LEAVER_END_DATE_REQUIRED",
        "UNKNOWN_EMPLOYMENT_STATUS",
        "TIME_OFF_CLIENT_NOT_IN_ROSTER",
        "PARTIAL_PTO_MULTIPLE_DATES",
        "INVALID_PARTIAL_PTO_TIME",
    } <= codes
    assert all(not row.valid for row in snapshot.agents)
    assert not snapshot.time_off[0].valid


def test_wide_schedule_preserves_business_dates_scope_off_and_explicit_overnight(
    tmp_path: Path,
) -> None:
    fte_path = tmp_path / "FTE Count.xlsx"
    schedule_path = tmp_path / "StartEndTimes.txt"
    valid_fte(fte_path)
    write_schedule(
        schedule_path,
        (
            (
                "Ada Agent",
                "00123",
                ".ORG | Front-office 08/01/2026 10:00 PM-08/02/2026 6:00 AM",
                "Off",
            ),
            (
                "Lee Leaver",
                "00200",
                ".ORG | Front-office 08/01/2026 8:00 AM-08/01/2026 4:00 PM",
                ".ORG | Front-office 08/02/2026 8:00 AM-08/02/2026 4:00 PM",
            ),
        ),
        "08/01/2026",
        "08/02/2026",
    )
    roster = parse_fte_workbook(fte_path, source_key="synthetic/fte.xlsx")

    schedule = parse_start_end_times(
        schedule_path,
        source_key="synthetic/StartEndTimes.txt",
        roster=roster,
    )

    assert [row.business_date.isoformat() for row in schedule.shifts] == [
        "2026-08-01",
        "2026-08-02",
        "2026-08-01",
        "2026-08-02",
    ]
    assert schedule.shifts[0].is_overnight
    assert schedule.shifts[0].source_row == 2
    assert schedule.shifts[0].source_column == 3
    assert schedule.shifts[1].schedule_state == "OFF"
    assert schedule.shifts[2].roster_client_id == "00200"
    assert not schedule.shifts[3].in_roster_scope
    assert schedule.scoped_out == 1
    assert {finding.code for finding in schedule.findings} == {"SCHEDULE_OUTSIDE_EFFECTIVE_ROSTER"}


def test_schedule_name_crosswalk_preserves_conflicting_explicit_source_id(
    tmp_path: Path,
) -> None:
    fte_path = tmp_path / "FTE Count.xlsx"
    schedule_path = tmp_path / "StartEndTimes.txt"
    valid_fte(fte_path)
    write_schedule(
        schedule_path,
        (
            (
                "Ada Agent",
                "VERINT-999",
                ".ORG | Front-office 08/01/2026 8:00 AM-08/01/2026 4:00 PM",
            ),
        ),
        "08/01/2026",
    )
    roster = parse_fte_workbook(fte_path, source_key="synthetic/fte.xlsx")

    schedule = parse_start_end_times(
        schedule_path,
        source_key="synthetic/StartEndTimes.txt",
        roster=roster,
    )

    row = schedule.shifts[0]
    assert row.source_agent_id == "VERINT-999"
    assert row.roster_client_id == "00123"
    assert row.scope_match == "name"
    assert row.in_roster_scope
    assert [finding.code for finding in schedule.findings] == ["SCHEDULE_ID_NAME_FALLBACK"]


def test_schedule_rejects_implicit_overnight_and_wrong_header_date(tmp_path: Path) -> None:
    fte_path = tmp_path / "FTE Count.xlsx"
    schedule_path = tmp_path / "StartEndTimes.txt"
    valid_fte(fte_path)
    write_schedule(
        schedule_path,
        (
            (
                "Ada Agent",
                "00123",
                ".ORG | Front-office 08/01/2026 10:00 PM-08/01/2026 6:00 AM",
                ".ORG | Front-office 08/03/2026 8:00 AM-08/03/2026 4:00 PM",
            ),
        ),
        "08/01/2026",
        "08/02/2026",
    )
    roster = parse_fte_workbook(fte_path, source_key="synthetic/fte.xlsx")

    schedule = parse_start_end_times(
        schedule_path,
        source_key="synthetic/StartEndTimes.txt",
        roster=roster,
    )

    assert [row.schedule_state for row in schedule.shifts] == ["INVALID", "INVALID"]
    assert {finding.code for finding in schedule.findings if finding.severity == "error"} == {
        "SHIFT_END_NOT_AFTER_START",
        "SHIFT_START_DATE_MISMATCH",
    }


def test_schedule_requires_unambiguous_wide_business_date_columns(tmp_path: Path) -> None:
    fte_path = tmp_path / "FTE Count.xlsx"
    schedule_path = tmp_path / "StartEndTimes.txt"
    valid_fte(fte_path)
    roster = parse_fte_workbook(fte_path, source_key="synthetic/fte.xlsx")
    schedule_path.write_text(
        "Name\tData Source IDs\tScheduling Period\tShift Assignment\n",
        encoding="cp1252",
    )
    with pytest.raises(SourceContractError, match="business date"):
        parse_start_end_times(schedule_path, source_key="synthetic/schedule.txt", roster=roster)


def test_activation_atomically_publishes_generation_keyed_raw_and_canonical_facts(
    tmp_path: Path,
) -> None:
    fte_path = tmp_path / "FTE Count.xlsx"
    schedule_path = tmp_path / "StartEndTimes.txt"
    valid_fte(fte_path)
    write_schedule(
        schedule_path,
        (
            (
                "Ada Agent",
                "00123",
                ".ORG | Front-office 08/01/2026 8:00 AM-08/01/2026 4:00 PM",
            ),
        ),
        "08/01/2026",
    )
    roster = parse_fte_workbook(fte_path, source_key="FTE/FTE Count.xlsx")
    schedule = parse_start_end_times(
        schedule_path,
        source_key="Verint/StartEndTimes.txt",
        roster=roster,
    )
    snapshot = SourceSnapshot(roster, (schedule,))
    store = RefreshStore(tmp_path / "control.sqlite")
    generation = start(store)
    stage_sources(store, generation, snapshot)
    stage_findings(store, generation, snapshot)
    store.activate_generation(generation, publish=make_source_publish(snapshot))

    with sqlite3.connect(store.path) as connection:
        roster_rows = connection.execute(
            "SELECT client_id, employment_status, eligible_through, source_row "
            "FROM wfm_agent_roster WHERE generation_id = ? ORDER BY client_id",
            (generation,),
        ).fetchall()
        time_off_rows = connection.execute(
            "SELECT source_kind, client_id, record_status, overlay_eligible "
            "FROM wfm_time_off "
            "WHERE generation_id = ? ORDER BY source_kind DESC",
            (generation,),
        ).fetchall()
        schedule_rows = connection.execute(
            "SELECT business_date, roster_client_id, source_row, source_column "
            "FROM wfm_schedule_shift WHERE generation_id = ?",
            (generation,),
        ).fetchall()
        raw_counts = connection.execute(
            "SELECT "
            "(SELECT count(*) FROM wfm_raw_fte_agent WHERE generation_id = ?), "
            "(SELECT count(*) FROM wfm_raw_fte_time_off WHERE generation_id = ?), "
            "(SELECT count(*) FROM wfm_raw_schedule_shift WHERE generation_id = ?)",
            (generation, generation, generation),
        ).fetchone()
    assert roster_rows == [
        ("00123", "Active", None, 2),
        ("00200", "Leaver", "2026-08-01", 3),
    ]
    assert time_off_rows == [
        ("PTO", "00123", "APPROVED", 1),
        ("AWAY", "00123", "ACTIVE", 1),
    ]
    assert schedule_rows == [("2026-08-01", "00123", 2, 3)]
    assert raw_counts == (2, 2, 1)
    assert store.active_generation_id() == generation


def test_activation_requires_exact_staged_source_evidence(tmp_path: Path) -> None:
    fte_path = tmp_path / "FTE Count.xlsx"
    schedule_path = tmp_path / "StartEndTimes.txt"
    valid_fte(fte_path)
    write_schedule(schedule_path, (("Ada Agent", "00123", "Off"),), "08/01/2026")
    roster = parse_fte_workbook(fte_path, source_key="synthetic/fte.xlsx")
    schedule = parse_start_end_times(
        schedule_path,
        source_key="synthetic/schedule.txt",
        roster=roster,
    )
    snapshot = SourceSnapshot(roster, (schedule,))
    store = RefreshStore(tmp_path / "control.sqlite")
    generation = start(store)

    with pytest.raises(ValueError, match="matching source evidence"):
        store.activate_generation(generation, publish=make_source_publish(snapshot))

    assert store.active_generation_id() is None


def test_time_off_marks_only_governed_statuses_overlay_eligible(tmp_path: Path) -> None:
    fte_path = tmp_path / "FTE Count.xlsx"
    write_fte(
        fte_path,
        agents=(
            (
                "00123",
                "Active",
                "Ada Agent",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                1,
                None,
            ),
        ),
        pto=(
            (
                "00123",
                "Ada Agent",
                "2026-08-03",
                "2026-08-03",
                "Full day",
                None,
                None,
                "Vacation",
                "Pending",
                None,
            ),
            (
                "00123",
                "Ada Agent",
                "2026-08-04",
                "2026-08-04",
                "Full day",
                None,
                None,
                "Vacation",
                "Cancelled",
                None,
            ),
        ),
        away=(
            (
                "00123",
                "Ada Agent",
                "2026-08-05",
                "2026-08-05",
                "Long sickness",
                "Closed",
                None,
            ),
            (
                "00123",
                "Ada Agent",
                "2026-08-06",
                "2026-08-06",
                "Long sickness",
                "Cancelled",
                None,
            ),
        ),
    )

    snapshot = parse_fte_workbook(fte_path, source_key="synthetic/fte.xlsx")

    assert [row.overlay_eligible for row in snapshot.time_off] == [False, False, True, False]


def test_blocking_parse_finding_leaves_previous_generation_active(tmp_path: Path) -> None:
    fte_path = tmp_path / "FTE Count.xlsx"
    valid_schedule_path = tmp_path / "StartEndTimes-good.txt"
    invalid_schedule_path = tmp_path / "StartEndTimes-bad.txt"
    valid_fte(fte_path)
    roster = parse_fte_workbook(fte_path, source_key="synthetic/fte.xlsx")
    write_schedule(
        valid_schedule_path,
        (("Ada Agent", "00123", "Off"),),
        "08/01/2026",
    )
    good = parse_start_end_times(
        valid_schedule_path,
        source_key="synthetic/good.txt",
        roster=roster,
    )
    store = RefreshStore(tmp_path / "control.sqlite")
    first = start(store)
    good_snapshot = SourceSnapshot(roster, (good,))
    stage_sources(store, first, good_snapshot)
    store.activate_generation(first, publish=make_source_publish(good_snapshot))

    write_schedule(
        invalid_schedule_path,
        (("Ada Agent", "00123", "bad interval"),),
        "08/02/2026",
    )
    bad = parse_start_end_times(
        invalid_schedule_path,
        source_key="synthetic/bad.txt",
        roster=roster,
    )
    second = start(store)
    broken_snapshot = SourceSnapshot(roster, (bad,))
    stage_sources(store, second, broken_snapshot)
    stage_findings(store, second, broken_snapshot)

    with pytest.raises(ValueError, match="blocking quality"):
        store.activate_generation(second, publish=make_source_publish(broken_snapshot))

    with sqlite3.connect(store.path) as connection:
        second_rows = connection.execute(
            "SELECT count(*) FROM wfm_raw_schedule_shift WHERE generation_id = ?", (second,)
        ).fetchone()
        first_rows = connection.execute(
            "SELECT business_date, schedule_state FROM wfm_schedule_shift WHERE generation_id = ?",
            (first,),
        ).fetchall()
    assert second_rows == (0,)
    assert first_rows == [("2026-08-01", "OFF")]
    assert store.active_generation_id() == first


def test_parsed_snapshot_version_hashes_exact_source_bytes(tmp_path: Path) -> None:
    path = tmp_path / "FTE Count.xlsx"
    valid_fte(path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()

    snapshot = parse_fte_workbook(path, source_key="FTE/FTE Count.xlsx")

    assert snapshot.version.source_key == "FTE/FTE Count.xlsx"
    assert snapshot.version.content_sha256 == expected
    assert snapshot.version.file_size == path.stat().st_size
    assert snapshot.version.row_count == snapshot.row_count
