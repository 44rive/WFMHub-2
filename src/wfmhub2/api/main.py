from pathlib import Path
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from wfmhub2 import __version__
from wfmhub2.core.settings import Settings
from wfmhub2.doctor import run_doctor
from wfmhub2.ingestion.refresh import RefreshEngine


class SinglePageApplication(StaticFiles):
    """Serve compiled assets with an index fallback for client-side routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        if path.startswith("api/"):
            raise StarletteHTTPException(status_code=status.HTTP_404_NOT_FOUND)
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return await super().get_response("index.html", scope)
        return response


def create_app(
    settings: Settings,
    session_token: str,
    *,
    web_dir: Path | None = None,
) -> FastAPI:
    """Create one engine API bound to one explicit portable-home launch."""
    if not session_token:
        raise ValueError("a non-empty per-launch session token is required")

    app = FastAPI(
        title="WFMHub 2 Engine",
        version=__version__,
        description="Local transport API for the WFMHub workforce-intelligence engine.",
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-WFMHub-Token"],
    )
    allowed_hosts = {"127.0.0.1", "localhost", "[::1]", "::1", settings.host}
    if ":" in settings.host:
        allowed_hosts.add(f"[{settings.host}]")
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=sorted(allowed_hosts),
    )

    def require_session_token(
        supplied_token: Annotated[str | None, Header(alias="X-WFMHub-Token")] = None,
    ) -> None:
        if supplied_token is None or not compare_digest(supplied_token, session_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid engine session token",
            )

    protected = Depends(require_session_token)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "architecture": "browser-python-ducklake",
        }

    @app.get("/api/stack/probe", dependencies=[protected])
    def stack_probe() -> JSONResponse:
        # API probes model packaged behavior: they never install an extension or
        # touch the network. The explicit doctor command is the development gate.
        report = run_doctor(settings, require_offline=True)
        status_code = 200 if report.status == "ok" else 503
        return JSONResponse(report.to_dict(), status_code=status_code)

    @app.get("/api/refresh/plan", dependencies=[protected])
    def refresh_plan() -> dict[str, int | str]:
        result = RefreshEngine(settings).plan()
        return {
            "status": "planned",
            "files_seen": result.files_seen,
            "files_changed": result.files_changed,
            "files_hashed": result.files_hashed,
        }

    if web_dir is not None:
        resolved_web_dir = web_dir.resolve()
        if not (resolved_web_dir / "index.html").is_file():
            raise FileNotFoundError(
                f"Compiled WFMHub web assets are missing: {resolved_web_dir / 'index.html'}"
            )
        app.state.web_dir = resolved_web_dir
        app.mount(
            "/",
            SinglePageApplication(directory=resolved_web_dir, html=True),
            name="web",
        )

    return app
