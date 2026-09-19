from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class FileFingerprint:
    path: Path
    size: int
    mtime_ns: int
    sha256: str


def fingerprint_file(path: Path, chunk_size: int = 1024 * 1024) -> FileFingerprint:
    stat = path.stat()
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return FileFingerprint(
        path=path,
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=digest.hexdigest(),
    )
