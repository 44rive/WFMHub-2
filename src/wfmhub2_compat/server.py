from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import webbrowser
from collections.abc import Sequence
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from secrets import compare_digest
from typing import Any, cast
from urllib.parse import urlencode, urlsplit

from wfmhub2_compat import __version__
from wfmhub2_compat.operate_evidence import (
    OperateQueryError,
    OperateReadError,
    parse_operate_query,
    read_operate_evidence,
)
from wfmhub2_compat.rta_refresh import (
    RefreshBusyError,
    RefreshFailedError,
    RtaRefreshCoordinator,
    validate_refresh_body,
)
from wfmhub2_compat.storage import MAX_REPORT_BYTES, initialize_database, save_report

SESSION_TOKEN_FRAGMENT_KEY = "wfmhub_token"
COMPATIBILITY_PORT = 8420
MAX_REFRESH_BODY_BYTES = 256
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; "
        "worker-src 'self' blob:; connect-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; font-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}

mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("application/zip", ".whl")


class CompatibilityServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = sys.platform != "win32"

    def server_bind(self) -> None:
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, home: Path, web_root: Path, session_token: str, port: int = 0) -> None:
        self.home = home
        self.web_root = web_root
        self.session_token = session_token
        self.rta = RtaRefreshCoordinator(home)
        super().__init__(("127.0.0.1", port), CompatibilityHandler)


class CompatibilityHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        server = cast(CompatibilityServer, args[2])
        super().__init__(*args, directory=str(server.web_root), **kwargs)

    @property
    def compatibility_server(self) -> CompatibilityServer:
        return cast(CompatibilityServer, self.server)

    def log_message(self, format: str, *args: object) -> None:
        del format, args
        return

    def end_headers(self) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def _valid_host(self) -> bool:
        raw_host = self.headers.get("Host", "")
        hostname = raw_host.rsplit(":", maxsplit=1)[0].strip("[]").lower()
        return hostname in {"127.0.0.1", "localhost"}

    def _authorized(self) -> bool:
        supplied = self.headers.get("X-WFMHub-Token")
        return supplied is not None and compare_digest(
            supplied, self.compatibility_server.session_token
        )

    def _json_response(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _reject_invalid_host(self) -> bool:
        if self._valid_host():
            return False
        self._json_response(HTTPStatus.BAD_REQUEST, {"error": "invalid loopback host"})
        return True

    def _require_api_auth(self) -> bool:
        if self._authorized():
            return True
        self._json_response(HTTPStatus.UNAUTHORIZED, {"error": "invalid session token"})
        return False

    def do_GET(self) -> None:
        if self._reject_invalid_host():
            return
        path = urlsplit(self.path).path
        if path == "/api/rta/operate-evidence":
            self._get_operate_evidence()
            return
        if path == "/api/rta/source-health":
            if not self._require_api_auth():
                return
            self._json_response(HTTPStatus.OK, self.compatibility_server.rta.source_health())
            return
        if path == "/api/compat/health":
            if not self._require_api_auth():
                return
            self._json_response(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "version": __version__,
                    "architecture": "stdlib-sqlite-browser-wasm-spike",
                    "thirdPartyHostNativeFiles": 0,
                },
            )
            return
        if path.startswith("/api/"):
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self._reject_invalid_host():
            return
        path = urlsplit(self.path).path
        if path == "/api/rta/operate-evidence":
            self._get_operate_evidence()
            return
        if path == "/api/rta/source-health":
            if not self._require_api_auth():
                return
            self._json_response(HTTPStatus.OK, self.compatibility_server.rta.source_health())
            return
        if path == "/api/compat/health":
            if not self._require_api_auth():
                return
            self._json_response(HTTPStatus.OK, {"status": "ok"})
            return
        if path.startswith("/api/"):
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
            return
        super().do_HEAD()

    def _get_operate_evidence(self) -> None:
        if not self._require_api_auth():
            return
        try:
            business_date, scope = parse_operate_query(urlsplit(self.path).query)
            result = read_operate_evidence(
                self.compatibility_server.rta.store.path,
                self.compatibility_server.home,
                business_date,
                scope,
            )
        except OperateQueryError:
            self._json_response(
                HTTPStatus.BAD_REQUEST, {"error": "invalid operate evidence selection"}
            )
            return
        except (OperateReadError, sqlite3.DatabaseError, OSError):
            self._json_response(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "committed operate evidence is unavailable"},
            )
            return
        self._json_response(HTTPStatus.OK, result)

    def do_POST(self) -> None:
        if self._reject_invalid_host():
            return
        path = urlsplit(self.path).path
        if path == "/api/rta/refresh":
            self._post_rta_refresh()
            return
        if path != "/api/compat/report":
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
            return
        if not self._require_api_auth():
            return
        if self.headers.get_content_type() != "application/json":
            self._json_response(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 1 <= length <= MAX_REPORT_BYTES:
            self._json_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "invalid size"})
            return
        try:
            report = json.loads(self.rfile.read(length))
            destination = save_report(self.compatibility_server.home, report)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._json_response(
            HTTPStatus.OK,
            {
                "status": "saved",
                "relativePath": destination.relative_to(self.compatibility_server.home).as_posix(),
            },
        )

    def _post_rta_refresh(self) -> None:
        if not self._require_api_auth():
            return
        if self.headers.get_content_type() != "application/json":
            self._json_response(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 1 <= length <= MAX_REFRESH_BODY_BYTES:
            self._json_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "invalid size"})
            return
        try:
            validate_refresh_body(json.loads(self.rfile.read(length)))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "refresh requires JSON {}"})
            return
        try:
            result = self.compatibility_server.rta.refresh()
        except RefreshBusyError:
            self._json_response(
                HTTPStatus.CONFLICT,
                {"code": "REFRESH_BUSY", "message": "A source refresh is already running."},
            )
            return
        except RefreshFailedError as exc:
            self._json_response(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {
                    "status": "failed",
                    "code": exc.code,
                    "message": exc.message,
                    "generationId": exc.generation_id,
                    "sourceHealth": self.compatibility_server.rta.source_health(),
                },
            )
            return
        self._json_response(HTTPStatus.OK, result)

    def send_head(self):  # type: ignore[no-untyped-def]
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        translated = Path(self.translate_path(path))
        if not translated.exists() and Path(path).suffix == "":
            self.path = "/index.html"
        return super().send_head()


def browser_url(port: int, token: str) -> str:
    fragment = urlencode({SESSION_TOKEN_FRAGMENT_KEY: token})
    return f"http://127.0.0.1:{port}/#{fragment}"


def launch_browser(url: str) -> None:
    if sys.platform != "win32":
        if not webbrowser.open(url, new=2):
            raise RuntimeError("the default browser could not be started")
        return

    candidates = [
        shutil.which("msedge.exe"),
        *(
            str(Path(root) / "Microsoft/Edge/Application/msedge.exe")
            for name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")
            if (root := os.environ.get(name))
        ),
    ]
    for raw_candidate in candidates:
        if raw_candidate and Path(raw_candidate).is_file():
            subprocess.Popen(
                [raw_candidate, f"--app={url}", "--no-first-run"],
                close_fds=True,
            )
            return
    raise FileNotFoundError("Microsoft Edge (msedge.exe) was not found")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wfmhub2-compat")
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--web-dir", type=Path, default=None)
    parser.add_argument("--no-browser", action="store_true")
    return parser


def run(
    home: Path,
    web_root: Path,
    *,
    open_browser: bool,
    session_token: str | None = None,
) -> None:
    home = home.expanduser().resolve()
    web_root = web_root.expanduser().resolve()
    if not (web_root / "index.html").is_file():
        raise FileNotFoundError(f"compiled browser assets are missing: {web_root / 'index.html'}")
    initialize_database(home / "data" / "control.sqlite")
    token = session_token or secrets.token_urlsafe(32)
    server = CompatibilityServer(home, web_root, token, COMPATIBILITY_PORT)
    port = int(server.server_address[1])
    url = browser_url(port, token)
    print(f"WFMHUB2_COMPAT_READY {json.dumps({'port': port}, separators=(',', ':'))}", flush=True)
    print("\nWFMHub 2 hybrid compatibility spike is ready.", flush=True)
    print(f"Address: http://127.0.0.1:{port}/", flush=True)
    print("Scope: this computer only", flush=True)
    print("Run every browser probe, then press Ctrl+C here to stop.\n", flush=True)
    try:
        if open_browser:
            launch_browser(url)
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nWFMHub 2 compatibility spike stopped.", flush=True)
    finally:
        server.server_close()


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    home = args.home
    web_root = args.web_dir or home / "_system" / "web"
    try:
        run(
            home,
            web_root,
            open_browser=not args.no_browser,
            session_token=(
                os.environ.get("WFMHUB2_COMPAT_SESSION_TOKEN") if args.no_browser else None
            ),
        )
    except Exception as exc:
        print(f"WFMHUB2_COMPAT_ERROR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
