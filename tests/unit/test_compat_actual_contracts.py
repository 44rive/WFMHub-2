from __future__ import annotations

import csv
import hashlib
import sqlite3
from pathlib import Path

import pytest

from wfmhub2_compat.actual_contracts import (
    load_status_policy,
    preflight_actual_source,
    publish_actual_plans,
    stage_actual_plans,
)
from wfmhub2_compat.refresh_store import RefreshStore, SourceVersion
from wfmhub2_compat.source_contracts import FteAgentRow, FteSnapshot, SourceContractError

EMPTY_CATALOG = hashlib.sha256(b"").hexdigest()
STATUS_HEADERS = [
    "[Serial Number]",
    "[Status]",
    "[Status Start Date and Time]",
    "[Agent]",
    "[Agent ID]",
    "[Status Duration]",
    "[Queue]",
]
LILO_HEADERS = [
    "[Agent]",
    "[Agent ID]",
    "[First Log-on Time]",
    "[Last Log-off Time]",
]


def _roster() -> FteSnapshot:
    row = FteAgentRow(
        "FTE/FTE Count.xlsx",
        "Agent",
        2,
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
        1.0,
        None,
        True,
        (),
    )
    version = SourceVersion(
        "fte",
        "FTE/FTE Count.xlsx",
        1,
        1,
        hashlib.sha256(b"fte").hexdigest(),
        "test",
        "test",
        1,
    )
    return FteSnapshot("FTE/FTE Count.xlsx", (row,), (), (), version)


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def test_agent_status_streams_long_duration_and_exact_policy(tmp_path: Path) -> None:
    path = tmp_path / "Storm/Agent Status/status.csv"
    _write_csv(
        path,
        STATUS_HEADERS,
        [
            ["", "Available", "07/01/2026 08:00:00", "Ada Agent", "00123", "37:59:56", "Q1"],
            ["2", "Disponible", "07/02/2026 09:00", "Ada Agent", "VERINT-9", "00:30:00", "Q2"],
            ["3", "Available", "07/02/2026 10:00", "Ada Agent", "00123", "00:00:00", "Q2"],
            ["4", "Available", "07/02/2026 10:00", "Outside", "999", "00:30:00", "Q2"],
        ],
    )
    policy = load_status_policy()
    plan = preflight_actual_source(
        path,
        source_key="Storm/Agent Status/status.csv",
        kind="agent_status",
        roster=_roster(),
        status_policy=policy,
    )

    assert (plan.accepted_rows, plan.rejected_rows, plan.scoped_out_rows) == (2, 1, 1)
    assert plan.version.row_count == 2
    assert {finding.issue_code for finding in plan.findings} == {
        "AGENT_STATUS_REJECTED_ROWS",
        "AGENT_STATUS_OUTSIDE_ROSTER_ROWS",
    }

    store = RefreshStore(tmp_path / "control.sqlite")
    generation = store.start_generation(catalog_sha256=EMPTY_CATALOG, model_version="actuals-v1")
    stage_actual_plans(store, generation, (plan,))
    store.activate_generation(
        generation,
        publish=lambda connection, generation_id: publish_actual_plans(
            connection,
            generation_id,
            (plan,),
            roster=_roster(),
            status_policy=policy,
        ),
    )
    with sqlite3.connect(store.path) as connection:
        rows = connection.execute(
            """
            SELECT serial_number, roster_client_id, actual_category,
                   duration_seconds, scope_match, status_end
            FROM wfm_raw_agent_status ORDER BY source_row
            """
        ).fetchall()
    assert len(rows[0][0]) == 64
    assert rows[0][1:5] == ("00123", "Productive", 136796, "id")
    assert rows[0][5] == "2026-07-02T21:59:56"
    assert rows[1][1:5] == ("VERINT-9", "Productive", 1800, "name")


def test_lilo_preserves_dated_no_show_and_adjusts_overnight(tmp_path: Path) -> None:
    path = tmp_path / "Storm/LILO/LILO_2026-07-01.csv"
    _write_csv(
        path,
        [*LILO_HEADERS, "Date"],
        [
            ["Ada Agent", "00123", "", "", "2026-07-01"],
            [
                "Ada Agent",
                "VERINT-9",
                "07/01/2026 10:00 PM",
                "07/01/2026 06:00 AM",
                "",
            ],
            ["Ada Agent", "", "", "", "2026-07-01"],
        ],
    )
    plan = preflight_actual_source(
        path,
        source_key="Storm/LILO/LILO_2026-07-01.csv",
        kind="lilo",
        roster=_roster(),
    )
    assert (plan.accepted_rows, plan.rejected_rows, plan.scoped_out_rows) == (2, 0, 1)

    store = RefreshStore(tmp_path / "control.sqlite")
    generation = store.start_generation(catalog_sha256=EMPTY_CATALOG, model_version="actuals-v1")
    stage_actual_plans(store, generation, (plan,))
    store.activate_generation(
        generation,
        publish=lambda connection, generation_id: publish_actual_plans(
            connection,
            generation_id,
            (plan,),
            roster=_roster(),
            status_policy=None,
        ),
    )
    with sqlite3.connect(store.path) as connection:
        rows = connection.execute(
            """
            SELECT roster_client_id, first_login, raw_last_logout, last_logout,
                   overnight_adjusted, scope_match
            FROM wfm_raw_lilo ORDER BY source_row
            """
        ).fetchall()
    assert rows[0] == ("00123", None, None, None, 0, "id")
    assert rows[1] == (
        "VERINT-9",
        "2026-07-01T22:00:00",
        "2026-07-01T06:00:00",
        "2026-07-02T06:00:00",
        1,
        "name",
    )


def test_lilo_range_filename_does_not_invent_blank_row_date(tmp_path: Path) -> None:
    path = tmp_path / "LILO_2026-07-01_2026-07-31.csv"
    _write_csv(path, LILO_HEADERS, [["Ada Agent", "00123", "", ""]])

    plan = preflight_actual_source(
        path,
        source_key="Storm/LILO/range.csv",
        kind="lilo",
        roster=_roster(),
    )

    assert (plan.accepted_rows, plan.rejected_rows) == (0, 1)
    assert plan.date_from is None


def test_missing_exact_header_blocks_file(tmp_path: Path) -> None:
    path = tmp_path / "status.csv"
    _write_csv(path, [header.replace("[Queue]", "Queue") for header in STATUS_HEADERS], [])

    with pytest.raises(SourceContractError, match=r"missing columns: \[Queue\]"):
        preflight_actual_source(
            path,
            source_key="Storm/Agent Status/status.csv",
            kind="agent_status",
            roster=_roster(),
            status_policy=load_status_policy(),
        )


def test_changed_source_rolls_back_generation_publication(tmp_path: Path) -> None:
    path = tmp_path / "LILO_2026-07-01.csv"
    _write_csv(
        path,
        LILO_HEADERS,
        [["Ada Agent", "00123", "07/01/2026 08:00", "07/01/2026 16:00"]],
    )
    plan = preflight_actual_source(
        path,
        source_key="Storm/LILO/LILO_2026-07-01.csv",
        kind="lilo",
        roster=_roster(),
    )
    store = RefreshStore(tmp_path / "control.sqlite")
    generation = store.start_generation(catalog_sha256=EMPTY_CATALOG, model_version="actuals-v1")
    stage_actual_plans(store, generation, (plan,))
    path.write_text(path.read_text(encoding="utf-8-sig") + "\n", encoding="utf-8")

    with pytest.raises(SourceContractError, match="changed before publication"):
        store.activate_generation(
            generation,
            publish=lambda connection, generation_id: publish_actual_plans(
                connection,
                generation_id,
                (plan,),
                roster=_roster(),
                status_policy=None,
            ),
        )

    assert store.active_generation_id() is None
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT count(*) FROM wfm_raw_lilo").fetchone() == (0,)


def test_lilo_publication_crosses_bounded_batch_boundary(tmp_path: Path) -> None:
    path = tmp_path / "LILO_2026-07-01.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(LILO_HEADERS)
        for _ in range(5001):
            writer.writerow(["Ada Agent", "00123", "07/01/2026 08:00", "07/01/2026 16:00"])
    plan = preflight_actual_source(
        path,
        source_key="Storm/LILO/LILO_2026-07-01.csv",
        kind="lilo",
        roster=_roster(),
    )
    store = RefreshStore(tmp_path / "control.sqlite")
    generation = store.start_generation(catalog_sha256=EMPTY_CATALOG, model_version="actuals-v1")
    stage_actual_plans(store, generation, (plan,))
    store.activate_generation(
        generation,
        publish=lambda connection, generation_id: publish_actual_plans(
            connection,
            generation_id,
            (plan,),
            roster=_roster(),
            status_policy=None,
        ),
    )

    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT count(*) FROM wfm_raw_lilo").fetchone() == (5001,)
