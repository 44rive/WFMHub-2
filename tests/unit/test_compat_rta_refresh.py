from __future__ import annotations

import csv
import http.client
import json
import os
import sqlite3
import threading
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from openpyxl import Workbook, load_workbook

import wfmhub2_compat.actual_contracts as actual_contracts
import wfmhub2_compat.call_contracts as call_contracts
import wfmhub2_compat.rta_refresh as refresh_module
from wfmhub2_compat.rta_refresh import RtaRefreshCoordinator, resolve_source_root
from wfmhub2_compat.server import CompatibilityServer
from wfmhub2_compat.setup import configure_source_root
from wfmhub2_compat.source_contracts import SourceContractError


def _sources(home: Path) -> tuple[Path, Path]:
    root = home / "extracts"
    fte = root / "FTE/FTE Count.xlsx"
    fte.parent.mkdir(parents=True)
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "Agent"
    sheet.append(["Client ID", "Status", "Name", "FTE", "End date if leaver"])
    sheet.append(["00123", "Active", "Ada Agent", 1, None])
    book.save(fte)
    book.close()
    schedule_dir = root / "Verint/Schedules & Activities"
    schedule_dir.mkdir(parents=True)
    return root, schedule_dir


def _schedule(path: Path, assignment: str) -> None:
    with path.open("w", encoding="cp1252", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["Name", "Data Source IDs", "08/01/2026"])
        writer.writerow(["Ada Agent", "00123", assignment])


def _event_sources(root: Path) -> tuple[Path, Path]:
    status = root / "Storm/Agent Status/status.csv"
    status.parent.mkdir(parents=True)
    with status.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "[Serial Number]",
                "[Status]",
                "[Status Start Date and Time]",
                "[Agent]",
                "[Agent ID]",
                "[Status Duration]",
                "[Queue]",
            ]
        )
        writer.writerow(
            ["1", "Available", "08/01/2026 08:00", "Ada Agent", "00123", "00:30:00", "Q1"]
        )
    calls = root / "Storm/Call by Call/calls.csv"
    calls.parent.mkdir(parents=True)
    with calls.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "[Call Date/Time]",
                "[Call End Date/Time]",
                "[Call ID]",
                "[Call Reference Number]",
                "[Agent ID]",
                "[Agent]",
                "[Talk Time]",
                "[Hold Time]",
                "[Total Wrap Time]",
                "[Call Direction]",
                "[Total Queue Wait Time]",
                "[Queue]",
            ]
        )
        writer.writerow(
            [
                "08/01/2026 08:07",
                "08/01/2026 08:10",
                "call-1",
                "ref-1",
                "00123",
                "Ada Agent",
                "00:02:00",
                "00:00:10",
                "00:00:20",
                "I",
                "00:00:15",
                "APBN_BRU_RSA_INTERNAT_All_FR",
            ]
        )
    return status, calls


def test_missing_sources_fail_without_publishing_and_keep_safe_health(tmp_path: Path) -> None:
    coordinator = RtaRefreshCoordinator(tmp_path)
    assert coordinator.source_health()["status"] == "not_ready"

    try:
        coordinator.refresh()
    except Exception as exc:
        assert getattr(exc, "code", None) == "MISSING_FTE_SOURCE"
    else:
        raise AssertionError("missing sources unexpectedly refreshed")

    health = coordinator.source_health()
    assert health["activeGenerationId"] is None
    assert health["latestRefresh"]["status"] == "failed"
    assert health["sourceRoot"]["displayName"] == "extracts"
    assert str(tmp_path) not in json.dumps(health)


def test_refresh_selects_newest_off_and_preserves_raw_evidence(tmp_path: Path) -> None:
    _, schedule_dir = _sources(tmp_path)
    old = schedule_dir / "StartEndTimes-old.txt"
    new = schedule_dir / "StartEndTimes-new.txt"
    _schedule(old, ".ORG | Work 08/01/2026 8:00 AM-08/01/2026 4:00 PM")
    _schedule(new, "Off")
    os.utime(old, ns=(1_000_000_000, 1_000_000_000))
    os.utime(new, ns=(2_000_000_000, 2_000_000_000))
    coordinator = RtaRefreshCoordinator(tmp_path)

    result = coordinator.refresh()

    assert result["status"] == "succeeded"
    health = coordinator.source_health()
    assert health["ready"] is True
    assert health["sources"]["roster"]["agentCount"] == 1
    assert health["sources"]["schedule"]["fileCount"] == 2
    assert health["sources"]["schedule"]["shiftCount"] == 1
    generation = health["activeGenerationId"]
    with sqlite3.connect(coordinator.store.path) as connection:
        canonical = connection.execute(
            "SELECT schedule_state, source_key FROM wfm_schedule_shift WHERE generation_id = ?",
            (generation,),
        ).fetchall()
        raw_count = connection.execute(
            "SELECT count(*) FROM wfm_raw_schedule_shift WHERE generation_id = ?",
            (generation,),
        ).fetchone()
    assert canonical == [("OFF", "Verint/Schedules & Activities/StartEndTimes-new.txt")]
    assert raw_count == (2,)

    _schedule(new, "not an interval")
    try:
        coordinator.refresh()
    except Exception as exc:
        assert getattr(exc, "code", None) == "BLOCKING_SOURCE_QUALITY"
    else:
        raise AssertionError("malformed schedule unexpectedly refreshed")
    assert coordinator.store.active_generation_id() == generation
    assert coordinator.source_health()["latestRefresh"]["status"] == "failed"


def test_setup_pointer_uses_existing_folder_without_copying(tmp_path: Path) -> None:
    home = tmp_path / "portable"
    source = tmp_path / "existing WFM Database"
    source.mkdir()

    pointer = configure_source_root(home, source)

    assert pointer == home / "data/source-root.txt"
    assert resolve_source_root(home).path == source.resolve()
    assert sorted(source.iterdir()) == []
    assert str(source) not in json.dumps(RtaRefreshCoordinator(home).source_health())


def test_source_change_marks_previous_generation_stale(tmp_path: Path) -> None:
    source, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    coordinator = RtaRefreshCoordinator(tmp_path)
    coordinator.refresh()
    assert coordinator.source_health()["ready"] is True

    alternate = tmp_path / "other WFM Database"
    alternate.mkdir()
    configure_source_root(tmp_path, alternate)

    health = coordinator.source_health()
    assert health["status"] == "source_changed"
    assert health["ready"] is False
    assert health["activeGenerationId"] is not None
    assert health["sources"]["roster"]["ready"] is False
    assert str(source) not in json.dumps(health)
    assert str(alternate) not in json.dumps(health)


def test_refresh_publishes_optional_storm_source_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    status = source / "Storm/Agent Status/status.csv"
    status.parent.mkdir(parents=True)
    with status.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "[Serial Number]",
                "[Status]",
                "[Status Start Date and Time]",
                "[Agent]",
                "[Agent ID]",
                "[Status Duration]",
                "[Queue]",
            ]
        )
        writer.writerow(
            ["1", "Available", "08/01/2026 08:00", "Ada Agent", "00123", "00:30:00", "Q1"]
        )
    lilo = source / "Storm/LILO/LILO_2026-08-01.csv"
    lilo.parent.mkdir(parents=True)
    with lilo.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["[Agent]", "[Agent ID]", "[First Log-on Time]", "[Last Log-off Time]"])
        writer.writerow(["Ada Agent", "00123", "08/01/2026 08:00", "08/01/2026 16:00"])
    calls = source / "Storm/Call by Call/calls.csv"
    calls.parent.mkdir(parents=True)
    with calls.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "[Call Date/Time]",
                "[Call End Date/Time]",
                "[Call ID]",
                "[Call Reference Number]",
                "[Agent ID]",
                "[Agent]",
                "[Talk Time]",
                "[Hold Time]",
                "[Total Wrap Time]",
                "[Call Direction]",
                "[Total Queue Wait Time]",
                "[Queue]",
            ]
        )
        writer.writerow(
            [
                "08/01/2026 08:07",
                "08/01/2026 08:10",
                "call-1",
                "ref-1",
                "00123",
                "Ada Agent",
                "00:02:00",
                "00:00:10",
                "00:00:20",
                "I",
                "00:00:15",
                "APBN_BRU_RSA_INTERNAT_All_FR",
            ]
        )

    status_parser = Mock(
        wraps=actual_contracts._iter_status  # pyright: ignore[reportPrivateUsage]
    )
    lilo_parser = Mock(wraps=actual_contracts._iter_lilo)  # pyright: ignore[reportPrivateUsage]
    call_parser = Mock(wraps=call_contracts._iter_calls)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(actual_contracts, "_iter_status", status_parser)
    monkeypatch.setattr(actual_contracts, "_iter_lilo", lilo_parser)
    monkeypatch.setattr(call_contracts, "_iter_calls", call_parser)
    coordinator = RtaRefreshCoordinator(tmp_path)
    result = coordinator.refresh()

    assert (status_parser.call_count, lilo_parser.call_count, call_parser.call_count) == (1, 1, 1)
    health = result["sourceHealth"]

    assert health["ready"] is True
    assert health["sources"]["agentStatus"] == {
        "ready": True,
        "rowCount": 1,
        "fileCount": 1,
        "minDate": "2026-08-01",
        "maxDate": "2026-08-01",
    }
    assert health["sources"]["lilo"] == {
        "ready": True,
        "rowCount": 1,
        "fileCount": 1,
        "minDate": "2026-08-01",
        "maxDate": "2026-08-01",
    }
    assert health["sources"]["callByCall"] == {
        "ready": True,
        "rawLegCount": 1,
        "canonicalLegCount": 1,
        "serviceIntervalCount": 1,
        "fileCount": 1,
        "minDate": "2026-08-01",
        "maxDate": "2026-08-01",
    }
    assert health["sources"]["attendance"] == {
        "ready": True,
        "agentDayCount": 1,
        "gapFragmentCount": 0,
        "statusPrimaryCount": 0,
        "unknownCount": 0,
        "minDate": "2026-08-01",
        "maxDate": "2026-08-01",
    }
    assert health["activeGeneration"]["counts"]["sourceFiles"] == 5
    assert str(source) not in json.dumps(health)


def test_second_unchanged_refresh_reuses_active_generation_without_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    coordinator = RtaRefreshCoordinator(tmp_path)
    first = coordinator.refresh()

    def unexpected_parse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unchanged refresh parsed the roster")

    monkeypatch.setattr(refresh_module, "_discover_roster", unexpected_parse)
    second = coordinator.refresh()

    assert second["status"] == "succeeded"
    assert second["unchanged"] is True
    assert second["generationId"] == first["generationId"]
    with sqlite3.connect(coordinator.store.path) as connection:
        assert connection.execute("SELECT count(*) FROM wfm_refresh_generation").fetchone() == (1,)


def test_new_schedule_reuses_event_bronze_without_reopening_or_copying_csvs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    _event_sources(root)
    coordinator = RtaRefreshCoordinator(tmp_path)
    first = coordinator.refresh()["generationId"]
    _schedule(schedule_dir / "StartEndTimes-second.txt", "Off")

    def unexpected_parse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unchanged event source was parsed")

    monkeypatch.setattr(actual_contracts, "_iter_status", unexpected_parse)
    monkeypatch.setattr(call_contracts, "_iter_calls", unexpected_parse)
    second_result = coordinator.refresh()
    second = second_result["generationId"]

    assert second != first
    assert second_result["sourceHealth"]["sources"]["agentStatus"]["rowCount"] == 1
    assert second_result["sourceHealth"]["sources"]["callByCall"]["rawLegCount"] == 1
    with sqlite3.connect(coordinator.store.path) as connection:
        owners = connection.execute(
            """
            SELECT source_type, bronze_generation_id FROM wfm_source_manifest
            WHERE generation_id = ? AND source_type IN ('agent_status', 'call_by_call')
            ORDER BY source_type
            """,
            (second,),
        ).fetchall()
        assert owners == [("agent_status", first), ("call_by_call", first)]
        assert connection.execute(
            "SELECT count(*) FROM wfm_raw_agent_status WHERE generation_id = ?", (second,)
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM wfm_raw_call_leg WHERE generation_id = ?", (second,)
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM wfm_call_leg WHERE generation_id = ?", (second,)
        ).fetchone() == (1,)


def test_known_call_version_reactivates_after_a_to_b_to_a(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    _, calls = _event_sources(root)
    original = calls.read_bytes()
    coordinator = RtaRefreshCoordinator(tmp_path)
    first = coordinator.refresh()["generationId"]

    calls.write_bytes(original.replace(b"call-1", b"call-2").replace(b"ref-1", b"ref-2"))
    changed_time = calls.stat().st_mtime_ns + 1_000_000_000
    os.utime(calls, ns=(changed_time, changed_time))
    second = coordinator.refresh()["generationId"]
    assert second != first

    calls.write_bytes(original)
    restored_time = calls.stat().st_mtime_ns + 1_000_000_000
    os.utime(calls, ns=(restored_time, restored_time))

    def unexpected_parse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("known call source version was parsed")

    monkeypatch.setattr(call_contracts, "_iter_calls", unexpected_parse)
    third = coordinator.refresh()["generationId"]
    assert third not in {first, second}
    with sqlite3.connect(coordinator.store.path) as connection:
        owner = connection.execute(
            """
            SELECT bronze_generation_id FROM wfm_source_manifest
            WHERE generation_id = ? AND source_type = 'call_by_call'
            """,
            (third,),
        ).fetchone()
        assert owner == (first,)
        assert connection.execute(
            "SELECT call_id FROM wfm_call_leg WHERE generation_id = ?", (third,)
        ).fetchone() == ("call-1",)


def test_roster_change_reparses_agent_scoped_event_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    _event_sources(root)
    coordinator = RtaRefreshCoordinator(tmp_path)
    coordinator.refresh()
    roster = root / "FTE/FTE Count.xlsx"
    book = load_workbook(roster)
    sheet = book["Agent"]
    sheet.append(["00456", "Active", "Ben Agent", 1, None])
    book.save(roster)
    book.close()

    status_parser = Mock(wraps=actual_contracts._iter_status)  # pyright: ignore[reportPrivateUsage]
    call_parser = Mock(wraps=call_contracts._iter_calls)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(actual_contracts, "_iter_status", status_parser)
    monkeypatch.setattr(call_contracts, "_iter_calls", call_parser)
    second = coordinator.refresh()["generationId"]

    assert status_parser.call_count == 1
    assert call_parser.call_count == 1
    with sqlite3.connect(coordinator.store.path) as connection:
        assert connection.execute(
            """
            SELECT count(*) FROM wfm_source_manifest
            WHERE generation_id = ? AND source_type IN ('agent_status', 'call_by_call')
              AND bronze_generation_id = generation_id
            """,
            (second,),
        ).fetchone() == (2,)


def test_removed_call_source_disappears_from_new_cut_and_rollback_restores_it(
    tmp_path: Path,
) -> None:
    root, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    _, calls = _event_sources(root)
    coordinator = RtaRefreshCoordinator(tmp_path)
    first = coordinator.refresh()["generationId"]

    calls.unlink()
    second = coordinator.refresh()["generationId"]
    health = coordinator.source_health()
    assert health["sources"]["callByCall"]["fileCount"] == 0
    assert health["sources"]["callByCall"]["canonicalLegCount"] == 0
    with sqlite3.connect(coordinator.store.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM wfm_call_leg WHERE generation_id = ?", (second,)
        ).fetchone() == (0,)
    assert coordinator.store.restore_previous_generation(expected_active_id=second) == first
    assert coordinator.source_health()["sources"]["callByCall"]["canonicalLegCount"] == 1


def test_call_policy_change_invalidates_known_bronze_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    _event_sources(root)
    coordinator = RtaRefreshCoordinator(tmp_path)
    coordinator.refresh()
    current_policy = refresh_module.load_call_policy()
    monkeypatch.setattr(
        refresh_module,
        "load_call_policy",
        lambda: replace(current_policy, fingerprint="f" * 64),
    )
    call_parser = Mock(wraps=call_contracts._iter_calls)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(call_contracts, "_iter_calls", call_parser)

    second = coordinator.refresh()["generationId"]

    assert call_parser.call_count == 1
    with sqlite3.connect(coordinator.store.path) as connection:
        assert connection.execute(
            """
            SELECT bronze_generation_id FROM wfm_source_manifest
            WHERE generation_id = ? AND source_type = 'call_by_call'
            """,
            (second,),
        ).fetchone() == (second,)


def test_missing_old_bronze_rows_force_source_reparse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    _event_sources(root)
    coordinator = RtaRefreshCoordinator(tmp_path)
    first = coordinator.refresh()["generationId"]
    with sqlite3.connect(coordinator.store.path) as connection:
        connection.execute("DELETE FROM wfm_raw_call_leg WHERE generation_id = ?", (first,))
    _schedule(schedule_dir / "StartEndTimes-second.txt", "Off")
    call_parser = Mock(wraps=call_contracts._iter_calls)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(call_contracts, "_iter_calls", call_parser)

    second = coordinator.refresh()["generationId"]

    assert call_parser.call_count == 1
    with sqlite3.connect(coordinator.store.path) as connection:
        assert connection.execute(
            """
            SELECT bronze_generation_id FROM wfm_source_manifest
            WHERE generation_id = ? AND source_type = 'call_by_call'
            """,
            (second,),
        ).fetchone() == (second,)
        assert connection.execute(
            "SELECT count(*) FROM wfm_call_leg WHERE generation_id = ?", (second,)
        ).fetchone() == (1,)


def test_changed_source_forces_a_new_generation(tmp_path: Path) -> None:
    _, schedule_dir = _sources(tmp_path)
    schedule = schedule_dir / "StartEndTimes.txt"
    _schedule(schedule, "Off")
    coordinator = RtaRefreshCoordinator(tmp_path)
    first = coordinator.refresh()

    _schedule(schedule, ".ORG | Work 08/01/2026 8:00 AM-08/01/2026 4:00 PM")
    second = coordinator.refresh()

    assert second["unchanged"] is False
    assert second["generationId"] != first["generationId"]


def test_unexpected_attendance_failure_is_actionable_and_preserves_active_cut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _, schedule_dir = _sources(tmp_path)
    schedule = schedule_dir / "StartEndTimes.txt"
    _schedule(schedule, "Off")
    coordinator = RtaRefreshCoordinator(tmp_path)
    active = coordinator.refresh()["generationId"]
    _schedule(schedule, ".ORG | Work 08/01/2026 8:00 AM-08/01/2026 4:00 PM")

    def fail_attendance(*_args: object, **_kwargs: object) -> None:
        raise sqlite3.IntegrityError("synthetic attendance failure")

    monkeypatch.setattr(refresh_module, "build_attendance_model", fail_attendance)
    with pytest.raises(refresh_module.RefreshFailedError) as captured:
        coordinator.refresh()

    assert captured.value.code == "REFRESH_FAILED_ATTENDANCE_INTEGRITYERROR"
    assert "during attendance" in captured.value.message
    assert "data/diagnostics/refresh-failure.txt" in captured.value.message
    assert coordinator.store.active_generation_id() == active
    diagnostic = tmp_path / "data/diagnostics/refresh-failure.txt"
    assert diagnostic.is_file()
    diagnostic_text = diagnostic.read_text(encoding="utf-8")
    assert "stage=attendance" in diagnostic_text
    assert "exception_type=IntegrityError" in diagnostic_text
    assert "synthetic attendance failure" in diagnostic_text
    assert "IntegrityError" in capsys.readouterr().err


def test_source_movement_gets_a_specific_retry_error_and_preserves_active_cut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    coordinator = RtaRefreshCoordinator(tmp_path)
    active = coordinator.refresh()["generationId"]
    status = source / "Storm/Agent Status/status.csv"
    status.parent.mkdir(parents=True)
    status.write_text("moving export", encoding="utf-8")

    def moving_source(*_args: object, **_kwargs: object) -> None:
        raise SourceContractError("source changed while it was being parsed")

    monkeypatch.setattr(refresh_module, "preflight_actual_source", moving_source)
    with pytest.raises(refresh_module.RefreshFailedError) as captured:
        coordinator.refresh()

    assert captured.value.code == "SOURCE_CHANGED_DURING_REFRESH"
    assert "Wait for the export or copy to finish" in captured.value.message
    assert coordinator.store.active_generation_id() == active
    diagnostic = tmp_path / "data/diagnostics/refresh-failure.txt"
    assert "SourceContractError" in diagnostic.read_text(encoding="utf-8")


def test_refresh_progress_is_readable_while_refresh_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, schedule_dir = _sources(tmp_path)
    _schedule(schedule_dir / "StartEndTimes.txt", "Off")
    coordinator = RtaRefreshCoordinator(tmp_path)
    original = refresh_module._discover_roster  # pyright: ignore[reportPrivateUsage]
    observed: list[dict[str, object] | None] = []

    def inspect_progress(source_root: Path, progress: object = None):  # type: ignore[no-untyped-def]
        observed.append(coordinator.source_health()["refreshProgress"])
        return original(source_root, progress)  # type: ignore[arg-type]

    monkeypatch.setattr(refresh_module, "_discover_roster", inspect_progress)
    coordinator.refresh()

    assert observed and observed[0] is not None
    assert observed[0]["stage"] == "inventory"
    assert observed[0]["status"] == "running"
    assert coordinator.source_health()["refreshProgress"] is None


def test_rta_http_requires_token_and_never_accepts_upload_payload(tmp_path: Path) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>WFMHub</h1>", encoding="utf-8")
    server = CompatibilityServer(tmp_path, web, "launch-secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", "/api/rta/source-health")
        assert connection.getresponse().status == 401
        connection.close()

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "GET", "/api/rta/source-health", headers={"X-WFMHub-Token": "launch-secret"}
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["status"] == "not_ready"
        connection.close()

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "POST",
            "/api/rta/refresh",
            body=b'{"path":"C:/outside"}',
            headers={"X-WFMHub-Token": "launch-secret", "Content-Type": "application/json"},
        )
        assert connection.getresponse().status == 400
        connection.close()

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "POST",
            "/api/rta/refresh",
            body=b"{}",
            headers={"X-WFMHub-Token": "launch-secret", "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        assert response.status == 422
        assert json.loads(response.read())["code"] == "MISSING_FTE_SOURCE"
        connection.close()

        _, schedule_dir = _sources(tmp_path)
        with (schedule_dir / "StartEndTimes.txt").open(
            "w", encoding="cp1252", newline=""
        ) as stream:
            writer = csv.writer(stream, delimiter="\t")
            writer.writerow(["Name", "Data Source IDs", "08/01/2026", "Total"])
            writer.writerow(["Ada Agent", "00123", "Off", "private assignment"])
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "POST",
            "/api/rta/refresh",
            body=b"{}",
            headers={"X-WFMHub-Token": "launch-secret", "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        result = json.loads(response.read())
        assert response.status == 422
        assert result["code"] == "INVALID_PUBLISHED_SCHEDULE"
        assert "header column 4 is not a business date" in result["message"]
        assert "Ada Agent" not in result["message"]
        assert "private assignment" not in result["message"]
        assert str(tmp_path) not in result["message"]
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
