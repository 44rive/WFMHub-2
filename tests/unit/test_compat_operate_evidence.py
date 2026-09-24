"""Synthetic, privacy-bounded coverage for the committed Operate evidence API."""

from __future__ import annotations

import http.client
import json
import sqlite3
import threading
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from wfmhub2_compat.flash_parity import (
    load_flash_profiles,
    parse_flash_query,
    read_flash_parity,
)
from wfmhub2_compat.operate_evidence import (
    OperateQueryError,
    OperateReadError,
    parse_operate_query,
    read_operate_evidence,
)
from wfmhub2_compat.refresh_store import RefreshStore
from wfmhub2_compat.rta_refresh import catalog_fingerprint
from wfmhub2_compat.server import CompatibilityServer
from wfmhub2_compat.setup import configure_source_root
from wfmhub2_compat.storage import initialize_database

DAY = "2026-08-01"
NEXT_DAY = "2026-08-02"


def _insert_interval(
    connection: sqlite3.Connection,
    generation: int,
    *,
    day: str = DAY,
    start: str = "08:00:00",
    service: str = "Demo FR",
    comparison: str = "Demo all",
    queue: str = "Queue A",
    offered: int = 2,
) -> None:
    interval_start = start if "T" in start else f"{day}T{start}"
    interval_end = (datetime.fromisoformat(interval_start) + timedelta(minutes=15)).isoformat(
        timespec="seconds"
    )
    connection.execute(
        """
        INSERT INTO wfm_service_interval (
            generation_id, business_date, interval_start, interval_end, source_system,
            service_scope, comparison_scope, queue, designation, language,
            offered, answered, abandoned, short_abandoned, abandoned_within_target,
            answered_within_target, talk_seconds, hold_seconds, wrap_seconds,
            handled_seconds, call_legs, transferred_legs, source_files_json,
            mapping_sha256, policy_fingerprint
        ) VALUES (?, ?, ?, ?, 'CALL_BY_CALL', ?, ?, ?, 'Inbound', 'FR',
                  ?, 1, 1, 0, 0, 1, 30, 2, 3, 35, 2, 0, '[]', 'map', 'policy')
        """,
        (
            generation,
            day,
            interval_start,
            interval_end,
            service,
            comparison,
            queue,
            offered,
        ),
    )


def _insert_attendance(
    connection: sqlite3.Connection,
    generation: int,
    *,
    day: str,
    agent: str,
    state: str,
    with_gap: bool,
) -> None:
    connection.execute(
        """
        INSERT INTO wfm_agent_roster (
            generation_id, client_id, employment_status, agent_name,
            source_key, source_sheet, source_row
        ) VALUES (?, ?, 'Active', ?, 'synthetic-roster.xlsx', 'Agent', ?)
        """,
        (generation, agent, f"Secret Synthetic Agent {agent}", len(agent) + 1),
    )
    key = f"{day}-{agent}"
    connection.execute(
        """
        INSERT INTO wfm_attendance_agent_day (
            generation_id, agent_day_key, business_date, roster_client_id,
            assignment, assignment_type, scheduled_minutes, planned_work_minutes,
            planned_time_off_minutes, actual_evidence, status_covered_minutes,
            status_coverage_ratio, status_is_primary, raw_late_minutes,
            late_minutes, early_leave_minutes, no_show_minutes, attendance_result,
            evidence_state, status_source_loaded, lilo_source_loaded,
            lilo_row_present, evaluation_as_of, schedule_source_key,
            source_keys_json, policy_fingerprint
        ) VALUES (?, ?, ?, ?, 'Work', 'Work', 480, 480, 0, 'NONE', 0,
                  0, 0, 0, 0, 0, 0, 'Unknown', ?, 0, 0, 0,
                  ?, 'Secret Schedule Path', '[]', 'policy')
        """,
        (generation, key, day, agent, state, f"{day}T17:00:00"),
    )
    if with_gap:
        connection.execute(
            """
            INSERT INTO wfm_attendance_gap (
                generation_id, gap_key, agent_day_key, business_date,
                roster_client_id, gap_type, gap_start, gap_end, gap_minutes,
                evidence_basis, source_keys_json, is_provisional, policy_fingerprint
            ) VALUES (?, ?, ?, ?, ?, 'LATE', ?, ?, 15, 'synthetic', '[]', 0, 'policy')
            """,
            (
                generation,
                f"gap-{key}",
                key,
                day,
                agent,
                f"{day}T08:00:00",
                f"{day}T08:15:00",
            ),
        )


def _published_store(home: Path) -> tuple[RefreshStore, int]:
    extracts = home / "extracts"
    extracts.mkdir(parents=True)
    store = RefreshStore(home / "data/control.sqlite")
    generation = store.start_generation(
        catalog_sha256=catalog_fingerprint(extracts), model_version="synthetic"
    )

    def publish(connection: sqlite3.Connection, current: int) -> None:
        _insert_interval(connection, current)
        _insert_interval(connection, current, queue="Queue B", offered=3)
        _insert_interval(
            connection, current, service="Demo NL", comparison="Demo all", queue="Queue C"
        )
        _insert_interval(connection, current, day=NEXT_DAY, queue="Tomorrow Queue")
        _insert_attendance(
            connection, current, day=DAY, agent="synthetic-A", state="UNKNOWN", with_gap=True
        )
        _insert_attendance(
            connection, current, day=DAY, agent="synthetic-B", state="COMPLETE", with_gap=False
        )
        _insert_attendance(
            connection,
            current,
            day=NEXT_DAY,
            agent="synthetic-C",
            state="UNKNOWN",
            with_gap=False,
        )

    store.activate_generation(generation, publish=publish)
    return store, generation


def test_query_contract_rejects_ambiguous_or_invalid_selections() -> None:
    assert parse_operate_query("date=2026-08-01") == (date(2026, 8, 1), None)
    assert parse_operate_query("date=2026-08-01&serviceScope=Demo+FR&comparisonScope=Demo+all") == (
        date(2026, 8, 1),
        ("Demo FR", "Demo all"),
    )
    for query in (
        "",
        "date=2026-02-29",
        "date=2026-8-1",
        "date=2026-08-01&date=2026-08-02",
        "date=2026-08-01&serviceScope=Demo+FR",
        "date=2026-08-01&serviceScope=&comparisonScope=Demo+all",
        "date=2026-08-01&serviceScope=Demo%0AFR&comparisonScope=Demo+all",
        "date=2026-08-01&unexpected=x",
        "date=2026-08-01&serviceScope=x&comparisonScope=y&unexpected=z",
        "date=2026-08-01&serviceScope=x&comparisonScope=y&date=2026-08-02",
    ):
        with pytest.raises(OperateQueryError):
            parse_operate_query(query)


def test_flash_parity_uses_exact_legacy_queue_lists_across_service_scopes(tmp_path: Path) -> None:
    catalog_sha, profiles = load_flash_profiles()
    assert catalog_sha == "b4e7fe5a93350c57a72d7bb4e9dbd900220f9695c804b8aa85f83cf60d72e0e7"
    assert {profile.profile_id for profile in profiles} == {
        "ford_oem_fr",
        "ford_nl",
        "rsa_be",
        "rsa_nl",
    }
    assert parse_flash_query(f"date={DAY}&profile=rsa_be") == (date(2026, 8, 1), "rsa_be")
    for query in ("date=2026-02-29", f"date={DAY}&profile=", f"date={DAY}&profile=x&profile=y"):
        with pytest.raises(OperateQueryError):
            parse_flash_query(query)

    store, generation = _published_store(tmp_path)
    with closing(sqlite3.connect(store.path)) as connection:
        _insert_interval(
            connection,
            generation,
            service="RSA BE FR",
            comparison="RSA BE",
            queue="APBN_BRU_RSA_INSURAN_All_FR",
            offered=3,
        )
        _insert_interval(
            connection,
            generation,
            service="RSA BE VL",
            comparison="RSA BE",
            queue="APBN_BRU_RSA_INSURAN_All_VL",
            offered=4,
        )
        _insert_interval(
            connection,
            generation,
            service="RSA BE FR",
            comparison="RSA BE",
            queue="Some Other Mapped Queue",
            offered=100,
        )
        _insert_interval(
            connection,
            generation,
            service="RSA BE FR",
            comparison="RSA BE",
            queue="APBN_BRU_RSA_INTERNAT_All_FR",
            start="09:00:00",
            offered=5,
        )
        connection.commit()
    result = read_flash_parity(store.path, tmp_path, date(2026, 8, 1), "rsa_be")
    assert result["status"] == "ready"
    assert result["selectedProfile"] == {"id": "rsa_be", "label": "RSA Belgium"}
    assert result["totals"]["offered"] == 12
    assert result["totals"]["answered"] == 3
    assert len(result["serviceHours"]) == 2
    assert result["serviceHours"][0]["hourStart"] == f"{DAY}T08:00:00"
    assert result["serviceHours"][0]["offered"] == 7
    assert result["serviceHours"][1]["hourStart"] == f"{DAY}T09:00:00"
    assert result["serviceHours"][1]["offered"] == 5
    assert "serviceLevel" not in json.dumps(result)
    assert "Some Other Mapped Queue" not in json.dumps(result)
    assert "Secret" not in json.dumps(result)
    empty = read_flash_parity(store.path, tmp_path, date(2026, 8, 1), "ford_nl")
    assert empty["totals"] is None
    failed = store.start_generation(
        catalog_sha256=catalog_fingerprint(tmp_path / "extracts"), model_version="synthetic"
    )
    store.fail_generation(failed, reason="synthetic failure")
    retained = read_flash_parity(store.path, tmp_path, date(2026, 8, 1), "rsa_be")
    assert retained["generationId"] == generation
    assert retained["totals"]["offered"] == 12
    with pytest.raises(OperateQueryError):
        read_flash_parity(store.path, tmp_path, date(2025, 8, 1), "rsa_be")


def test_flash_parity_suppresses_changed_source_root(tmp_path: Path) -> None:
    store, _ = _published_store(tmp_path)
    (tmp_path / "extracts").rmdir()
    result = read_flash_parity(store.path, tmp_path, date(2026, 8, 1))
    assert result["reason"] == "SOURCE_ROOT_UNAVAILABLE"


def test_no_cut_and_missing_source_root_return_bounded_not_ready(tmp_path: Path) -> None:
    store = RefreshStore(tmp_path / "data/control.sqlite")
    result = read_operate_evidence(store.path, tmp_path, date(2026, 8, 1))
    assert result == {
        "status": "not_ready",
        "reason": "NO_ACTIVE_GENERATION",
        "businessDate": DAY,
        "generationId": None,
        "serviceScopes": [],
        "selectedScope": None,
        "serviceIntervals": [],
        "attendance": {"scope": "date-wide", "evidenceStates": [], "gapTypes": []},
    }
    store, _ = _published_store(tmp_path)
    (tmp_path / "extracts").rmdir()
    assert read_operate_evidence(store.path, tmp_path, date(2026, 8, 1))["reason"] == (
        "SOURCE_ROOT_UNAVAILABLE"
    )


def test_active_cut_aggregates_service_and_attendance_without_leaking_rows(
    tmp_path: Path,
) -> None:
    store, generation = _published_store(tmp_path)
    result = read_operate_evidence(store.path, tmp_path, date(2026, 8, 1))
    assert result["status"] == "ready"
    assert result["generationId"] == generation
    assert result["serviceScopes"] == [
        {"serviceScope": "Demo FR", "comparisonScope": "Demo all"},
        {"serviceScope": "Demo NL", "comparisonScope": "Demo all"},
    ]
    assert result["selectedScope"] == result["serviceScopes"][0]
    assert result["serviceIntervals"] == [
        {
            "intervalStart": f"{DAY}T08:00:00",
            "intervalEnd": f"{DAY}T08:15:00",
            "offered": 5,
            "answered": 2,
            "abandoned": 2,
            "shortAbandoned": 0,
            "abandonedWithinTarget": 0,
            "answeredWithinTarget": 2,
            "talkSeconds": 60,
            "holdSeconds": 4,
            "wrapSeconds": 6,
            "handledSeconds": 70,
            "callLegs": 4,
            "transferredLegs": 0,
        }
    ]
    assert result["attendance"] == {
        "scope": "date-wide",
        "evidenceStates": [
            {"state": "COMPLETE", "agentDays": 1},
            {"state": "UNKNOWN", "agentDays": 1},
        ],
        "gapTypes": [{"type": "LATE", "fragments": 1, "minutes": 15}],
    }
    serialized = json.dumps(result)
    for secret in ("Secret", "synthetic-A", "synthetic-B", str(tmp_path), "Queue A"):
        assert secret not in serialized
    nl = read_operate_evidence(store.path, tmp_path, date(2026, 8, 1), ("Demo NL", "Demo all"))
    assert nl["serviceIntervals"][0]["offered"] == 2
    assert nl["attendance"] == result["attendance"]
    tomorrow = read_operate_evidence(store.path, tmp_path, date(2026, 8, 2))
    assert tomorrow["attendance"]["evidenceStates"] == [{"state": "UNKNOWN", "agentDays": 1}]


def test_read_uses_successful_cut_during_failed_and_running_refresh(tmp_path: Path) -> None:
    store, active = _published_store(tmp_path)
    running = store.start_generation(
        catalog_sha256=catalog_fingerprint(tmp_path / "extracts"), model_version="synthetic"
    )
    with closing(sqlite3.connect(store.path)) as writer:
        writer.execute("BEGIN IMMEDIATE")
        _insert_interval(writer, running, offered=999)
        current = read_operate_evidence(store.path, tmp_path, date(2026, 8, 1))
        assert current["generationId"] == active
        assert current["serviceIntervals"][0]["offered"] == 5
        writer.rollback()
    store.fail_generation(running, reason="synthetic failure")
    after = read_operate_evidence(store.path, tmp_path, date(2026, 8, 1))
    assert after["generationId"] == active


def test_changed_source_pointer_suppresses_previous_cut(tmp_path: Path) -> None:
    store, _ = _published_store(tmp_path)
    alternate = tmp_path / "new source root"
    alternate.mkdir()
    configure_source_root(tmp_path, alternate)
    result = read_operate_evidence(store.path, tmp_path, date(2026, 8, 1))
    assert result["status"] == "not_ready"
    assert result["reason"] == "SOURCE_ROOT_CHANGED"
    assert result["serviceIntervals"] == []
    assert str(alternate) not in json.dumps(result)


def test_extended_business_day_is_not_truncated_and_oversized_cut_fails_closed(
    tmp_path: Path,
) -> None:
    extracts = tmp_path / "extracts"
    extracts.mkdir()
    store = RefreshStore(tmp_path / "data/control.sqlite")
    generation = store.start_generation(
        catalog_sha256=catalog_fingerprint(extracts), model_version="synthetic"
    )
    day = "2026-10-25"

    def publish(connection: sqlite3.Connection, current: int) -> None:
        for index in range(100):
            start = datetime(2026, 10, 25) + timedelta(minutes=index * 15)
            _insert_interval(
                connection,
                current,
                day=day,
                start=start.isoformat(timespec="seconds"),
                queue="DST Queue",
            )

    store.activate_generation(generation, publish=publish)
    result = read_operate_evidence(store.path, tmp_path, date(2026, 10, 25))
    assert len(result["serviceIntervals"]) == 100

    later = store.start_generation(
        catalog_sha256=catalog_fingerprint(extracts), model_version="synthetic"
    )

    def publish_oversized(connection: sqlite3.Connection, current: int) -> None:
        publish(connection, current)
        for index in range(100, 105):
            start = datetime(2026, 10, 25) + timedelta(minutes=index * 15)
            _insert_interval(
                connection,
                current,
                day=day,
                start=start.isoformat(timespec="seconds"),
                queue="DST Queue",
            )

    store.activate_generation(later, publish=publish_oversized)
    with pytest.raises(OperateReadError, match="exceeds one business day"):
        read_operate_evidence(store.path, tmp_path, date(2026, 10, 25))


def test_startup_adds_date_scope_index_to_existing_database(tmp_path: Path) -> None:
    database = tmp_path / "data/control.sqlite"
    RefreshStore(database)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("DROP INDEX ix_wfm_service_interval_date_scope")
        connection.commit()
    initialize_database(database)
    with closing(sqlite3.connect(database)) as connection:
        names = {row[1] for row in connection.execute("PRAGMA index_list(wfm_service_interval)")}
    assert "ix_wfm_service_interval_date_scope" in names


def _request(
    port: int, path: str, *, token: str | None = "secret", method: str = "GET"
) -> tuple[int, dict[str, Any]]:
    headers = {"X-WFMHub-Token": token} if token is not None else {}
    with closing(http.client.HTTPConnection("127.0.0.1", port, timeout=5)) as connection:
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        body = response.read()
        return response.status, json.loads(body) if body else {}


def test_api_requires_token_and_returns_only_bounded_evidence(tmp_path: Path) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<p>synthetic</p>", encoding="utf-8")
    server = CompatibilityServer(tmp_path, web, "secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    try:
        assert _request(port, f"/api/rta/operate-evidence?date={DAY}", token=None)[0] == 401
        assert _request(port, f"/api/rta/operate-evidence?date={DAY}", token="wrong")[0] == 401
        assert _request(port, f"/api/rta/flash-parity?date={DAY}", token=None)[0] == 401
        status, payload = _request(port, f"/api/rta/operate-evidence?date={DAY}")
        assert status == 200
        assert payload["reason"] == "NO_ACTIVE_GENERATION"
        _published_store(tmp_path)
        status, payload = _request(port, f"/api/rta/operate-evidence?date={DAY}")
        assert status == 200
        assert payload["serviceIntervals"][0]["offered"] == 5
        assert "agent_name" not in json.dumps(payload)
        selected = (
            f"/api/rta/operate-evidence?date={DAY}&serviceScope=Demo+NL&comparisonScope=Demo+all"
        )
        assert _request(port, selected)[1]["serviceIntervals"][0]["offered"] == 2
        assert (
            _request(port, f"/api/rta/operate-evidence?date={DAY}&serviceScope=Demo+FR")[0] == 400
        )
        assert (
            _request(
                port,
                f"/api/rta/operate-evidence?date={DAY}&serviceScope=Unknown&comparisonScope=Demo+all",
            )[0]
            == 400
        )
        assert _request(port, f"/api/rta/operate-evidence?date={DAY}", method="HEAD") == (200, {})
        flash_status, flash = _request(port, f"/api/rta/flash-parity?date={DAY}&profile=rsa_be")
        assert flash_status == 200
        assert flash["totals"] is None
        assert "flash_queues" not in json.dumps(flash)
        assert _request(port, f"/api/rta/flash-parity?date={DAY}&profile=invalid")[0] == 400
        assert _request(port, f"/api/rta/flash-parity?date={DAY}", method="HEAD") == (200, {})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
