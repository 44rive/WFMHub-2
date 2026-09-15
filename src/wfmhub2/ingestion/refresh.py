from dataclasses import dataclass
from pathlib import Path

from wfmhub2.core.settings import Settings


@dataclass(frozen=True)
class RefreshResult:
    files_seen: int
    files_changed: int
    rows_loaded: int


class RefreshEngine:
    """Incremental refresh orchestrator.

    The first implementation deliberately establishes the contract before vendor
    adapters are added: unchanged files are skipped and downstream models receive
    affected date ranges rather than a request to rebuild all history.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def discover(self) -> list[Path]:
        if not self.settings.inbox_dir.exists():
            return []
        return sorted(path for path in self.settings.inbox_dir.rglob("*") if path.is_file())

    def run(self) -> RefreshResult:
        files = self.discover()
        # Vendor adapters + manifest comparison land next. Keeping the public
        # orchestration contract stable lets each adapter be implemented independently.
        return RefreshResult(files_seen=len(files), files_changed=0, rows_loaded=0)
