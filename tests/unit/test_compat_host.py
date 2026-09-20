from __future__ import annotations

import http.client
import json
import sqlite3
import threading
from pathlib import Path

import pytest

from wfmhub2_compat.server import CompatibilityServer, browser_url
from wfmhub2_compat.storage import save_report, validate_report


def sample_report() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "profile": "phase0.4-hybrid-compatibility-spike",
        "overallStatus": "pass",
        "probes": [
            {"name": name, "status": "pass", "durationMs": 2}
            for name in (
                "host_sqlite",
                "wasm_worker",
                "duckdb_opfs",
                "pyodide_forecasting",
                "highs_mip",
            )
        ],
    }


def test_report_is_atomically_persisted_and_audited_in_sqlite(tmp_path: Path) -> None:
    destination = save_report(tmp_path, sample_report())

    assert destination == tmp_path / "data/compatibility/last-browser-report.json"
    assert json.loads(destination.read_text(encoding="utf-8"))["overallStatus"] == "pass"
    with sqlite3.connect(tmp_path / "data/control.sqlite") as connection:
        row = connection.execute(
            "SELECT overall_status, probe_count, passed_count, failed_count FROM compatibility_run"
        ).fetchone()
    assert row == ("pass", 5, 5, 0)


def test_report_rejects_inconsistent_overall_status() -> None:
    report = sample_report()
    report["overallStatus"] = "fail"

    with pytest.raises(ValueError, match="overallStatus must be pass"):
        validate_report(report)


def test_report_rejects_duplicate_or_missing_probe() -> None:
    report = sample_report()
    probes = report["probes"]
    assert isinstance(probes, list)
    probes[-1] = probes[0]

    with pytest.raises(ValueError, match="duplicate compatibility probe"):
        validate_report(report)


def test_token_is_kept_in_browser_fragment() -> None:
    url = browser_url(43127, "secret value")

    assert url == "http://127.0.0.1:43127/#wfmhub_token=secret+value"
    assert "secret" not in url.split("#", maxsplit=1)[0]


def test_loopback_server_requires_token_and_accepts_browser_report(tmp_path: Path) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>compatibility</h1>", encoding="utf-8")
    server = CompatibilityServer(tmp_path, web, "launch-secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", "/api/compat/health")
        assert connection.getresponse().status == 401
        connection.close()

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "GET",
            "/api/compat/health",
            headers={"X-WFMHub-Token": "launch-secret"},
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["thirdPartyHostNativeFiles"] == 0
        connection.close()

        encoded = json.dumps(sample_report()).encode("utf-8")
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "POST",
            "/api/compat/report",
            body=encoded,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(encoded)),
                "X-WFMHub-Token": "launch-secret",
            },
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["relativePath"] == (
            "data/compatibility/last-browser-report.json"
        )
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_loopback_server_restarts_on_stable_origin_but_rejects_live_collision(
    tmp_path: Path,
) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>compatibility</h1>", encoding="utf-8")
    first = CompatibilityServer(tmp_path, web, "first-secret")
    port = int(first.server_address[1])
    with pytest.raises(OSError):
        CompatibilityServer(tmp_path, web, "collision", port)

    thread = threading.Thread(target=first.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request("GET", "/")
    assert connection.getresponse().status == 200
    connection.close()
    first.shutdown()
    first.server_close()
    thread.join(timeout=5)

    restarted = CompatibilityServer(tmp_path, web, "second-secret", port)
    restarted.server_close()


def test_hybrid_launchers_do_not_require_blocked_native_stack() -> None:
    root = Path(__file__).resolve().parents[2]
    launcher = (root / "packaging/windows/WFMHub-Hybrid.cmd").read_text(encoding="utf-8")
    doctor = (root / "packaging/windows/DOCTOR-Hybrid.cmd").read_text(encoding="utf-8")

    assert "wfmhub2_compat" in launcher
    assert "wfmhub2_compat.doctor" in doctor
    for blocked_component in ("ducklake", "uvicorn", "fastapi", "pydantic"):
        assert blocked_component not in launcher.lower()
        assert blocked_component not in doctor.lower()
