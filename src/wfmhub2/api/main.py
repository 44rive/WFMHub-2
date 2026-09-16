from fastapi import FastAPI

from wfmhub2 import __version__
from wfmhub2.core.settings import Settings
from wfmhub2.ingestion.refresh import RefreshEngine

app = FastAPI(
    title="WFMHub 2 Engine",
    version=__version__,
    description="Local transport API for the WFMHub workforce-intelligence engine.",
)
settings = Settings()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": __version__,
        "architecture": "tauri-python-ducklake",
    }


@app.get("/api/refresh/plan")
def refresh_plan() -> dict[str, int | str]:
    result = RefreshEngine(settings).plan()
    return {
        "status": "planned",
        "files_seen": result.files_seen,
        "files_changed": result.files_changed,
        "files_hashed": result.files_hashed,
    }
