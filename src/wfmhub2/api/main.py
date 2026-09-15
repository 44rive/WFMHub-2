from fastapi import FastAPI

from wfmhub2 import __version__
from wfmhub2.core.settings import Settings
from wfmhub2.ingestion.refresh import RefreshEngine

app = FastAPI(title="WFMHub 2", version=__version__)
settings = Settings()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/api/refresh")
def refresh() -> dict[str, int]:
    result = RefreshEngine(settings).run()
    return {
        "files_seen": result.files_seen,
        "files_changed": result.files_changed,
        "rows_loaded": result.rows_loaded,
    }
