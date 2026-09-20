import argparse
import ctypes
import json
import os
import secrets
import socket
import threading
import time
import webbrowser
from collections.abc import Callable, Sequence
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlencode

import uvicorn

from wfmhub2.api.main import create_app
from wfmhub2.core.settings import Settings
from wfmhub2.doctor import DoctorReport, run_doctor
from wfmhub2.storage.lakehouse import initialize as initialize_lakehouse
from wfmhub2.storage.sqlite import initialize as initialize_sqlite

ERROR_PREFIX = "WFMHUB2_ERROR "
PORTABLE_WEB_RELATIVE_PATH = Path("_system") / "web"
SESSION_TOKEN_FRAGMENT_KEY = "wfmhub_token"
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
        "--web-dir",
        default=None,
        help=(
            "Compiled React directory. Packaged homes automatically use "
            "<home>/_system/web when it exists."
        ),
    )
    serve.add_argument(
        "--session-token",
        default=None,
        help=(
            "Development override for WFMHUB2_SESSION_TOKEN. Production launchers "
            "should inject the token through the child-process environment."
        ),
    )

    portable = sub.add_parser(
        "portable",
        help="Start the local engine and open the compiled interface in the default browser",
    )
    portable.add_argument(
        "--web-dir",
        default=None,
        help="Compiled React directory. Defaults to <home>/_system/web.",
    )
    portable.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the portable server without opening a browser (for automated smoke tests).",
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
    def __init__(
        self,
        config: uvicorn.Config,
        ready_line: str,
        on_started: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(config)
        self._ready_line = ready_line
        self._on_started = on_started

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets=sockets)
        if self.started:
            print(self._ready_line, flush=True)
            if self._on_started is not None:
                self._on_started()


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
    web_dir: Path | None = None,
) -> None:
    _run_server(settings, session_token, parent_pid=parent_pid, web_dir=web_dir)


def portable_web_dir(settings: Settings, raw_web_dir: str | None) -> Path:
    if raw_web_dir is None:
        return (settings.home / PORTABLE_WEB_RELATIVE_PATH).resolve()
    return Path(raw_web_dir).expanduser().resolve()


def serve_web_dir(settings: Settings, raw_web_dir: str | None) -> Path | None:
    candidate = portable_web_dir(settings, raw_web_dir)
    if raw_web_dir is not None or (candidate / "index.html").is_file():
        return candidate
    return None


def portable_browser_url(actual_port: int, session_token: str) -> str:
    fragment = urlencode({SESSION_TOKEN_FRAGMENT_KEY: session_token})
    return f"http://127.0.0.1:{actual_port}/#{fragment}"


def _open_browser(url: str) -> None:
    try:
        opened = webbrowser.open(url, new=2)
    except webbrowser.Error:
        opened = False
    if not opened:
        print(
            "The default browser did not open. Keep this window open and retry WFMHub.", flush=True
        )


def _run_server(
    settings: Settings,
    session_token: str,
    *,
    parent_pid: int | None = None,
    web_dir: Path | None = None,
    require_offline: bool = False,
    on_ready: Callable[[int], None] | None = None,
) -> None:
    init_storage(settings, require_offline=require_offline)
    app = create_app(settings, session_token, web_dir=web_dir)
    server_socket = reserve_server_socket(settings)
    actual_port = int(server_socket.getsockname()[1])
    config = uvicorn.Config(
        app=app,
        host=settings.host,
        port=actual_port,
        reload=False,
        access_log=False,
    )
    started_callback = None if on_ready is None else lambda: on_ready(actual_port)
    server = ReadinessServer(
        config,
        readiness_line(actual_port),
        on_started=started_callback,
    )
    start_parent_watchdog(server, parent_pid)
    server.run(sockets=[server_socket])


def _portable(
    settings: Settings,
    web_dir: Path,
    *,
    launch_browser: bool,
    session_token: str | None = None,
) -> None:
    # token_urlsafe(32) draws 32 random bytes: a fresh 256-bit credential for
    # this one localhost process. The fragment is not sent in the HTTP request.
    session_token = session_token or secrets.token_urlsafe(32)

    def ready(actual_port: int) -> None:
        display_url = f"http://127.0.0.1:{actual_port}/"
        print("\nWFMHub 2 is ready.", flush=True)
        print(f"Address: {display_url}", flush=True)
        print("Scope: this computer only", flush=True)
        print("Keep this window open; press Ctrl+C to stop WFMHub.\n", flush=True)
        if launch_browser:
            _open_browser(portable_browser_url(actual_port, session_token))

    portable_settings = settings.model_copy(update={"host": "127.0.0.1", "port": 0})
    _run_server(
        portable_settings,
        session_token,
        web_dir=web_dir,
        require_offline=True,
        on_ready=ready,
    )


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
    if parent_pid <= 1 or parent_pid > 0xFFFFFFFF:
        raise RuntimeError("WFMHUB2_PARENT_PID must be a positive process ID")
    return parent_pid


def process_exists(process_id: int) -> bool:
    if os.name == "nt":
        # The POSIX `kill(pid, 0)` liveness idiom is invalid on Windows and can
        # be destructive there. Query a process handle without signalling it.
        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # pyright: ignore[reportAttributeAccessIssue]
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit_code_process = kernel32.GetExitCodeProcess
        get_exit_code_process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code_process.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        handle = open_process(process_query_limited_information, False, process_id)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if not get_exit_code_process(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            close_handle(handle)

    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def start_parent_watchdog(server: uvicorn.Server, parent_pid: int | None) -> None:
    if parent_pid is None:
        return

    def watch_parent() -> None:
        while process_exists(parent_pid):
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

    if args.command == "portable":
        _portable(
            settings,
            portable_web_dir(settings, args.web_dir),
            launch_browser=not args.no_browser,
            # Automated exact-ZIP smoke needs a known credential. Normal
            # browser launches always ignore inherited token variables and
            # generate a fresh credential inside this process.
            session_token=(os.environ.get("WFMHUB2_SESSION_TOKEN") if args.no_browser else None),
        )
        return

    _serve(
        settings,
        session_token_from_args(args, parser),
        parent_pid=parent_pid_from_environment(),
        web_dir=serve_web_dir(settings, args.web_dir),
    )


def main(argv: Sequence[str] | None = None) -> None:
    try:
        _main(argv)
    except KeyboardInterrupt:
        print("\nWFMHub 2 stopped.", flush=True)
    except PermissionError:
        print(error_line("portable_home_not_writable", PORTABLE_HOME_ERROR), flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
