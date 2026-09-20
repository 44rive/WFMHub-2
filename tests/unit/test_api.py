from pathlib import Path
from typing import cast

import anyio
import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from starlette.exceptions import HTTPException as StarletteHTTPException

from wfmhub2.api.main import SinglePageApplication, create_app
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
                "Origin": "http://127.0.0.1:5173",
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
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_vite_development_origin_matches_browser_configuration(tmp_path: Path) -> None:
    app = create_app(Settings(home=tmp_path), "per-launch-secret")

    with TestClient(app, base_url="http://localhost") as client:
        response = client.options(
            "/api/stack/probe",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-WFMHub-Token",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_empty_session_token_is_rejected(tmp_path: Path) -> None:
    settings = Settings(home=tmp_path)
    try:
        create_app(settings, "")
    except ValueError as exc:
        assert "session token" in str(exc)
    else:
        raise AssertionError("empty token must not create an application")


def test_compiled_frontend_is_served_same_origin_with_spa_fallback(tmp_path: Path) -> None:
    web_dir = tmp_path / "web"
    assets_dir = web_dir / "assets"
    assets_dir.mkdir(parents=True)
    (web_dir / "index.html").write_text("<main>WFMHub browser shell</main>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('wfmhub')", encoding="utf-8")
    app = create_app(Settings(home=tmp_path), "per-launch-secret", web_dir=web_dir)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        root = client.get("/")
        asset = client.get("/assets/app.js")
        client_route = client.get("/future/rta")
        missing_api = client.get("/api/not-a-route")

    assert root.status_code == 200
    assert "WFMHub browser shell" in root.text
    assert asset.status_code == 200
    assert asset.text == "console.log('wfmhub')"
    assert client_route.status_code == 200
    assert "WFMHub browser shell" in client_route.text
    assert missing_api.status_code == 404

    # Starlette passes OS-normalized mounted paths to StaticFiles. Exercise the
    # Windows representation even when this test suite is running on Linux.
    with pytest.raises(StarletteHTTPException) as exc_info:
        anyio.run(
            SinglePageApplication(directory=web_dir, html=True).get_response,
            r"api\not-a-route",
            {"type": "http", "method": "GET", "path": "/api/not-a-route"},
        )
    assert exc_info.value.status_code == 404


def test_missing_compiled_frontend_fails_before_server_start(tmp_path: Path) -> None:
    try:
        create_app(
            Settings(home=tmp_path),
            "per-launch-secret",
            web_dir=tmp_path / "missing-web",
        )
    except FileNotFoundError as exc:
        assert "index.html" in str(exc)
    else:
        raise AssertionError("portable launch must reject missing compiled web assets")
