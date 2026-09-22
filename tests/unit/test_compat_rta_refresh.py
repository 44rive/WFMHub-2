from __future__ import annotations

import csv
import http.client
import json
import os
import sqlite3
import threading
from pathlib import Path

from openpyxl import Workbook

from wfmhub2_compat.rta_refresh import RtaRefreshCoordinator, resolve_source_root
from wfmhub2_compat.server import CompatibilityServer
from wfmhub2_compat.setup import configure_source_root


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


def test_refresh_publishes_optional_storm_source_health(tmp_path: Path) -> None:
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

    coordinator = RtaRefreshCoordinator(tmp_path)
    result = coordinator.refresh()
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
