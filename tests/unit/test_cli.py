import json
from pathlib import Path
from typing import cast

from pytest import MonkeyPatch

from wfmhub2.cli import (
    PORTABLE_HOME_ERROR,
    build_parser,
    error_line,
    parent_pid_from_environment,
    readiness_line,
    reserve_server_socket,
    session_token_from_args,
    settings_from_args,
)
from wfmhub2.core.settings import Settings


def test_cli_propagates_home_extension_host_and_ephemeral_port(tmp_path: Path) -> None:
    home = tmp_path / "portable"
    extension = tmp_path / "ducklake.duckdb_extension"
    args = build_parser().parse_args(
        [
            "--home",
            str(home),
            "--ducklake-extension",
            str(extension),
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--session-token",
            "launch-secret",
        ]
    )
    settings = settings_from_args(args)

    assert settings.home == home.resolve()
    assert settings.ducklake_extension == extension.resolve()
    assert settings.host == "127.0.0.1"
    assert settings.port == 0


def test_ephemeral_socket_and_readiness_line_report_actual_port_without_token(
    tmp_path: Path,
) -> None:
    settings = Settings(home=tmp_path, port=0)
    server_socket = reserve_server_socket(settings)
    try:
        actual_port = int(server_socket.getsockname()[1])
        line = readiness_line(actual_port)
    finally:
        server_socket.close()

    assert actual_port > 0
    assert line.startswith("WFMHUB2_READY ")
    payload = cast(dict[str, object], json.loads(line.removeprefix("WFMHUB2_READY ")))
    assert payload["port"] == actual_port
    assert set(payload) == {"port"}
    assert "token" not in line.lower()
    assert "secret" not in line.lower()


def test_non_loopback_server_host_is_rejected(tmp_path: Path) -> None:
    try:
        Settings(home=tmp_path, host="0.0.0.0")
    except ValueError as exc:
        assert "loopback" in str(exc)
    else:
        raise AssertionError("non-loopback host must not be accepted")


def test_production_session_token_comes_from_child_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    parser = build_parser()
    args = parser.parse_args(["serve"])
    monkeypatch.setenv("WFMHUB2_SESSION_TOKEN", "environment-launch-secret")

    assert session_token_from_args(args, parser) == "environment-launch-secret"


def test_parent_watchdog_pid_is_validated(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("WFMHUB2_PARENT_PID", raising=False)
    assert parent_pid_from_environment() is None

    monkeypatch.setenv("WFMHUB2_PARENT_PID", "43127")
    assert parent_pid_from_environment() == 43127

    for invalid in ("0", "-1", "not-a-pid"):
        monkeypatch.setenv("WFMHUB2_PARENT_PID", invalid)
        try:
            parent_pid_from_environment()
        except RuntimeError as exc:
            assert "positive process ID" in str(exc)
        else:
            raise AssertionError("invalid desktop parent PID must not be accepted")


def test_portable_home_error_is_machine_readable_and_actionable() -> None:
    line = error_line("portable_home_not_writable", PORTABLE_HOME_ERROR)
    payload = cast(dict[str, object], json.loads(line.removeprefix("WFMHUB2_ERROR ")))

    assert payload == {
        "code": "portable_home_not_writable",
        "message": PORTABLE_HOME_ERROR,
    }
    assert "writable" in PORTABLE_HOME_ERROR
