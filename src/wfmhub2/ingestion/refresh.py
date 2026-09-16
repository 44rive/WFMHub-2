from dataclasses import dataclass
from pathlib import Path

from wfmhub2.core.settings import Settings
from wfmhub2.ingestion.fingerprint import fingerprint_file
from wfmhub2.storage.sqlite import connect


@dataclass(frozen=True)
class RefreshPlan:
    files_seen: int
    files_changed: int
    files_hashed: int
    changed_paths: tuple[Path, ...]


class RefreshEngine:
    """Plan incremental ingestion without rebuilding unchanged history.

    Vendor adapters own normalization/loading. This orchestrator owns the stable
    source-manifest contract and dependency planning boundary.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def discover(self) -> list[Path]:
        if not self.settings.inbox_dir.exists():
            return []
        return sorted(path for path in self.settings.inbox_dir.rglob("*") if path.is_file())

    def plan(self) -> RefreshPlan:
        files = self.discover()
        changed: list[Path] = []
        hashed = 0

        if not self.settings.control_db_path.exists():
            return RefreshPlan(len(files), len(files), 0, tuple(files))

        with connect(self.settings.control_db_path) as conn:
            for path in files:
                stat = path.stat()
                row = conn.execute(
                    """
                    SELECT file_size, mtime_ns
                    FROM source_manifest
                    WHERE source_path = ? AND active = 1
                    ORDER BY loaded_at DESC, id DESC
                    LIMIT 1
                    """,
                    (str(path),),
                ).fetchone()

                if row and row["file_size"] == stat.st_size and row["mtime_ns"] == stat.st_mtime_ns:
                    continue

                # Content hashing is intentionally deferred until cheap metadata says
                # the source may have changed.
                fingerprint_file(path)
                hashed += 1
                changed.append(path)

        return RefreshPlan(len(files), len(changed), hashed, tuple(changed))
