import argparse
import json
import os
import socket
import threading
import time
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from wfmhub2.api.main import create_app
from wfmhub2.core.settings import Settings
from wfmhub2.doctor import DoctorReport, run_doctor
from wfmhub2.storage.lakehouse import initialize as initialize_lakehouse
from wfmhub2.storage.sqlite import initialize as initialize_sqlite

ERROR_PREFIX = "WFMHUB2_ERROR "
PORTABLE_HOME_ERROR = (
    "The portable WFMHub folder is not writable. Move WFMHub to a writable "
    "folder or grant write access."
)


def init_storage(settings: Settings, *, require_offline: bool = False) -> None:
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    settings.ducklake_data_path.mkdir(parents=True, exist_ok=True)
    initialize_sqlite(settings.control_db_path)
    initialize_lakehouse(settings, require_offline=require_offline)


def settings_from_args(args: argparse.Namespace) -> Settings:
    values: dict[str, object] = {}
    if args.home is not None:
        values["home"] = Path(args.home).expanduser().resolve()
    if args.ducklake_extension is not None:
        values["ducklake_extension"] = Path(args.ducklake_extension).expanduser().resolve()
    if getattr(args, "host", None) is not None:
        values["host"] = args.host
    if getattr(args, "port", None) is not None:
        values["port"] = args.port
    return Settings.model_validate(values)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wfmhub2")
    parser.add_argument(
        "--home",
        default=None,
        help="Portable WFMHub home directory. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--ducklake-extension",
        default=None,
        help="Path to a locally bundled DuckLake extension for offline runtime.",
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Initialize the local control DB and DuckLake")

    serve = sub.add_parser("serve", help="Start the local WFM engine API")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", default=None, type=int)
    serve.add_argument(
        "--session-token",
        default=None,
        help=(
            "Development override for WFMHUB2_SESSION_TOKEN. Production launchers "
            "should inject the token through the child-process environment."
        ),
    )

    doctor = sub.add_parser("doctor", help="Qualify the portable backend stack")
    doctor.add_argument("--json", action="store_true", dest="json_output")
    doctor.add_argument(
        "--require-offline",
        action="store_true",
        help="Require explicit local DuckLake LOAD; never use the extension repository.",
    )
    doctor.add_argument(
        "--full",
        action="store_true",
        help="Also execute Polars, forecasting, XGBoost, and OR-Tools operations.",
    )
    return parser


def readiness_payload(actual_port: int) -> dict[str, object]:
    # Keep the Tauri handshake deliberately minimal. The parser rejects unknown
    # fields so secrets or operational details cannot accidentally enter it.
    return {"port": actual_port}


def readiness_line(actual_port: int) -> str:
    payload = json.dumps(
        readiness_payload(actual_port),
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"WFMHUB2_READY {payload}"


def error_line(code: str, message: str) -> str:
    payload = json.dumps(
        {"code": code, "message": message},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{ERROR_PREFIX}{payload}"


def reserve_server_socket(settings: Settings) -> socket.socket:
    family = socket.AF_INET6 if ":" in settings.host else socket.AF_INET
    server_socket = socket.socket(family, socket.SOCK_STREAM)
    try:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((settings.host, settings.port))
        server_socket.listen(2048)
        server_socket.set_inheritable(True)
        return server_socket
    except Exception:
        server_socket.close()
        raise


class ReadinessServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, ready_line: str) -> None:
        super().__init__(config)
        self._ready_line = ready_line

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets=sockets)
        if self.started:
            print(self._ready_line, flush=True)


def _print_human_report(report: DoctorReport) -> None:
    print(f"WFMHub 2 doctor: {report.status} ({report.mode})")
    for check in report.checks:
        suffix = ""
        if check.error is not None:
            suffix = f" — {check.error.type}: {check.error.message}"
        print(f"  {check.name}: {check.status}{suffix}")


def _serve(
    settings: Settings,
    session_token: str,
    *,
    parent_pid: int | None = None,
) -> None:
    init_storage(settings)
    app = create_app(settings, session_token)
    server_socket = reserve_server_socket(settings)
    actual_port = int(server_socket.getsockname()[1])
    config = uvicorn.Config(
        app=app,
        host=settings.host,
        port=actual_port,
        reload=False,
        access_log=False,
    )
    server = ReadinessServer(config, readiness_line(actual_port))
    start_parent_watchdog(server, parent_pid)
    server.run(sockets=[server_socket])


def session_token_from_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    session_token = args.session_token or os.environ.get("WFMHUB2_SESSION_TOKEN")
    if not session_token:
        parser.error("serve requires WFMHUB2_SESSION_TOKEN or --session-token")
    return session_token


def parent_pid_from_environment() -> int | None:
    raw_parent_pid = os.environ.get("WFMHUB2_PARENT_PID")
    if raw_parent_pid is None:
        return None
    try:
        parent_pid = int(raw_parent_pid)
    except ValueError as exc:
        raise RuntimeError("WFMHUB2_PARENT_PID must be a positive process ID") from exc
    if parent_pid <= 1:
        raise RuntimeError("WFMHUB2_PARENT_PID must be a positive process ID")
    return parent_pid


def _process_exists(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def start_parent_watchdog(server: uvicorn.Server, parent_pid: int | None) -> None:
    if parent_pid is None:
        return

    def watch_parent() -> None:
        while _process_exists(parent_pid):
            time.sleep(0.1)
        server.should_exit = True

    threading.Thread(
        target=watch_parent,
        name="wfmhub2-parent-watchdog",
        daemon=True,
    ).start()


def _main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = settings_from_args(args)

    if args.command == "init":
        init_storage(settings)
        print(f"Initialized WFMHub 2 at {settings.home}")
        return

    if args.command == "doctor":
        report = run_doctor(
            settings,
            require_offline=args.require_offline,
            full=args.full,
        )
        if args.json_output:
            print(json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")))
        else:
            _print_human_report(report)
        if report.status != "ok":
            raise SystemExit(1)
        return

    _serve(
        settings,
        session_token_from_args(args, parser),
        parent_pid=parent_pid_from_environment(),
    )


def main(argv: Sequence[str] | None = None) -> None:
    try:
        _main(argv)
    except PermissionError:
        print(error_line("portable_home_not_writable", PORTABLE_HOME_ERROR), flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
