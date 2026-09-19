from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from wfmhub2.api.main import create_app
from wfmhub2.core.settings import Settings
from wfmhub2.doctor import DoctorReport, ProbeCheck


def _successful_report(settings: Settings) -> DoctorReport:
    return DoctorReport(
        status="ok",
        mode="offline",
        settings={"home": str(settings.home)},
        checks=(ProbeCheck(name="ducklake", status="pass"),),
    )


def test_app_uses_explicit_settings_and_protects_stack_probe(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings = Settings(home=tmp_path)

    def fake_run_doctor(
        received_settings: Settings,
        *,
        require_offline: bool,
    ) -> DoctorReport:
        assert require_offline is True
        return _successful_report(received_settings)

    monkeypatch.setattr(
        "wfmhub2.api.main.run_doctor",
        fake_run_doctor,
    )
    app = create_app(settings, "per-launch-secret")

    assert app.state.settings is settings
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/stack/probe").status_code == 401
        assert (
            client.get(
                "/api/stack/probe",
                headers={"X-WFMHub-Token": "wrong"},
            ).status_code
            == 401
        )
        response = client.get(
            "/api/stack/probe",
            headers={"X-WFMHub-Token": "per-launch-secret"},
        )

    assert response.status_code == 200
    body = cast(dict[str, object], response.json())
    assert body["status"] == "ok"
    assert body["mode"] == "offline"


def test_host_and_cors_are_restricted(tmp_path: Path) -> None:
    app = create_app(Settings(home=tmp_path), "per-launch-secret")

    with TestClient(app, base_url="http://evil.example") as untrusted:
        assert untrusted.get("/api/health").status_code == 400

    with TestClient(app, base_url="http://localhost") as client:
        allowed = client.options(
            "/api/stack/probe",
            headers={
                "Origin": "tauri://localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-WFMHub-Token",
            },
        )
        denied = client.options(
            "/api/stack/probe",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "tauri://localhost"
    assert "access-control-allow-origin" not in denied.headers


def test_empty_session_token_is_rejected(tmp_path: Path) -> None:
    settings = Settings(home=tmp_path)
    try:
        create_app(settings, "")
    except ValueError as exc:
        assert "session token" in str(exc)
    else:
        raise AssertionError("empty token must not create an application")
