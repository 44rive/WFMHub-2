"""Resolve immutable, previously published event-source Bronze versions.

The selected source root and roster contract are dependencies of every event
adapter.  Reuse never reads rows from a failed refresh generation.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from wfmhub2_compat.refresh_store import QualityIssue, SourceVersion

FileFingerprint = tuple[int, int, str]


class SourceMovedError(RuntimeError):
    """The source changed during the one required fingerprint pass."""


@dataclass(frozen=True)
class ReusedSource:
    version: SourceVersion
    bronze_generation_id: int
    findings: tuple[QualityIssue, ...]


def fingerprint_file(path: Path) -> FileFingerprint:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise SourceMovedError("source changed during fingerprinting")
    return before.st_size, before.st_mtime_ns, digest.hexdigest()


class SourceReuseCatalog:
    """Match event files against successful, same-scope source versions."""

    def __init__(
        self,
        database: Path,
        *,
        catalog_sha256: str,
        model_version: str,
        roster: SourceVersion,
    ) -> None:
        self.database = database
        self.catalog_sha256 = catalog_sha256
        self.model_version = model_version
        self.roster = roster

    def match(
        self,
        path: Path,
        *,
        source_type: str,
        source_key: str,
        adapter_version: str,
        policy_fingerprint: str,
    ) -> tuple[ReusedSource | None, FileFingerprint]:
        before = path.stat()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            candidates = connection.execute(
                """
                SELECT manifest.generation_id, manifest.bronze_generation_id,
                       manifest.file_size, manifest.mtime_ns,
                       manifest.content_sha256, manifest.row_count
                FROM wfm_source_manifest AS manifest
                JOIN wfm_refresh_generation AS generation
                  ON generation.id = manifest.generation_id
                JOIN wfm_source_manifest AS roster
                  ON roster.generation_id = generation.id
                 AND roster.source_type = 'fte_roster' AND roster.state = 'present'
                WHERE generation.status = 'succeeded'
                  AND generation.catalog_sha256 = ?
                  AND generation.model_version = ?
                  AND manifest.source_type = ? AND manifest.source_key = ?
                  AND manifest.state = 'present'
                  AND manifest.adapter_version = ?
                  AND manifest.policy_fingerprint = ?
                  AND manifest.row_count IS NOT NULL
                  AND roster.content_sha256 = ?
                  AND roster.adapter_version = ?
                  AND roster.policy_fingerprint = ?
                ORDER BY manifest.generation_id DESC
                """,
                (
                    self.catalog_sha256,
                    self.model_version,
                    source_type,
                    source_key,
                    adapter_version,
                    policy_fingerprint,
                    self.roster.content_sha256,
                    self.roster.adapter_version,
                    self.roster.policy_fingerprint,
                ),
            ).fetchall()
            active_row = connection.execute(
                "SELECT generation_id FROM wfm_active_generation WHERE singleton = 1"
            ).fetchone()
            active_id = int(active_row[0]) if active_row is not None and active_row[0] else None
            matching_metadata = next(
                (
                    row
                    for row in candidates
                    if row["generation_id"] == active_id
                    if (row["file_size"], row["mtime_ns"]) == (before.st_size, before.st_mtime_ns)
                ),
                None,
            )
            fingerprint = (
                (before.st_size, before.st_mtime_ns, str(matching_metadata["content_sha256"]))
                if matching_metadata is not None
                else fingerprint_file(path)
            )
            matching = matching_metadata or next(
                (row for row in candidates if row["content_sha256"] == fingerprint[2]),
                None,
            )
            if matching is None:
                return None, fingerprint
            owner = matching["bronze_generation_id"]
            if owner is None:
                return None, fingerprint
            findings = tuple(
                QualityIssue(str(row[0]), str(row[1]), str(row[2]), source_key)
                for row in connection.execute(
                    """
                    SELECT issue_code, severity, details FROM wfm_quality_issue
                    WHERE generation_id = ? AND source_key = ? ORDER BY id
                    """,
                    (matching["generation_id"], source_key),
                )
            )
            version = SourceVersion(
                source_type,
                source_key,
                fingerprint[0],
                fingerprint[1],
                fingerprint[2],
                adapter_version,
                policy_fingerprint,
                int(matching["row_count"]),
            )
            return ReusedSource(version, int(owner), findings), fingerprint
