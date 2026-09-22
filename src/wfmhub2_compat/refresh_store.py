"""Generation-scoped SQLite refresh control for the stdlib portable profile.

Rows staged for a generation are not visible as current WFM state until the
single active-generation pointer is changed in the same transaction as the
canonical facts' publication. Future fact tables must be generation-keyed or
written through ``activate_generation(publish=...)``; unversioned writes made
before activation would violate the rollback contract.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Generator, Iterable
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

from wfmhub2_compat.storage import initialize_database, utc_now

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class SourceVersion:
    """One changed, read-only source version observed during a refresh."""

    source_type: str
    source_key: str
    file_size: int
    mtime_ns: int
    content_sha256: str
    adapter_version: str
    policy_fingerprint: str
    row_count: int | None = None


@dataclass(frozen=True)
class QualityIssue:
    """One generation-scoped data-quality observation."""

    issue_code: str
    severity: str
    details: str
    source_key: str | None = None


@contextmanager
def _write_transaction(path: Path) -> Generator[sqlite3.Connection]:
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _running(connection: sqlite3.Connection, generation_id: int) -> sqlite3.Row:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT id, status, base_generation_id FROM wfm_refresh_generation WHERE id = ?",
        (generation_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown refresh generation {generation_id}")
    if row["status"] != "running":
        raise ValueError(f"refresh generation {generation_id} is not running")
    return row


def _required_text(value: str, name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{name} must not be empty")


def _sha256(value: str, name: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def _inserted_id(cursor: sqlite3.Cursor) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return an inserted row ID")
    return cursor.lastrowid


class RefreshStore:
    """Small transactional authority, independent of HTTP and native packages."""

    def __init__(self, path: Path) -> None:
        self.path = path
        initialize_database(path)

    def active_generation_id(self) -> int | None:
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                "SELECT generation_id FROM wfm_active_generation WHERE singleton = 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("active-generation control row is missing")
        return row[0]

    def active_source(self, *, source_type: str, source_key: str) -> SourceVersion | None:
        """Resolve the most recent changed version through the active lineage."""
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                """
                WITH RECURSIVE lineage(id, parent_id, depth) AS (
                    SELECT g.id, g.base_generation_id, 0
                    FROM wfm_refresh_generation AS g
                    JOIN wfm_active_generation AS a ON a.generation_id = g.id
                    WHERE a.singleton = 1
                    UNION ALL
                    SELECT g.id, g.base_generation_id, lineage.depth + 1
                    FROM wfm_refresh_generation AS g
                    JOIN lineage ON g.id = lineage.parent_id
                )
                SELECT m.state, m.source_type, m.source_key, m.file_size, m.mtime_ns,
                       m.content_sha256, m.adapter_version, m.policy_fingerprint,
                       m.row_count
                FROM wfm_source_manifest AS m
                JOIN lineage ON lineage.id = m.generation_id
                WHERE m.source_type = ? AND m.source_key = ?
                ORDER BY lineage.depth LIMIT 1
                """,
                (source_type, source_key),
            ).fetchone()
        return SourceVersion(*row[1:]) if row is not None and row[0] == "present" else None

    def start_generation(self, *, catalog_sha256: str, model_version: str) -> int:
        _sha256(catalog_sha256, "catalog_sha256")
        _required_text(model_version, "model_version")
        with _write_transaction(self.path) as connection:
            base = connection.execute(
                "SELECT generation_id FROM wfm_active_generation WHERE singleton = 1"
            ).fetchone()
            if base is None:
                raise RuntimeError("active-generation control row is missing")
            cursor = connection.execute(
                """
                INSERT INTO wfm_refresh_generation (
                    started_at, status, base_generation_id, catalog_sha256, model_version
                ) VALUES (?, 'running', ?, ?, ?)
                """,
                (utc_now(), base[0], catalog_sha256, model_version),
            )
            return _inserted_id(cursor)

    def stage_source(
        self,
        generation_id: int,
        source: SourceVersion,
        *,
        bronze_generation_id: int | None = None,
    ) -> int:
        for name in ("source_type", "source_key", "adapter_version", "policy_fingerprint"):
            _required_text(getattr(source, name), name)
        _sha256(source.content_sha256, "content_sha256")
        if source.file_size < 0 or source.mtime_ns < 0:
            raise ValueError("file_size and mtime_ns must be nonnegative")
        if source.row_count is not None and source.row_count < 0:
            raise ValueError("row_count must be nonnegative")
        bronze_owner = generation_id if bronze_generation_id is None else bronze_generation_id
        with _write_transaction(self.path) as connection:
            _running(connection, generation_id)
            if bronze_owner != generation_id:
                owner = connection.execute(
                    """
                    SELECT generation.status, manifest.state, manifest.content_sha256,
                           manifest.adapter_version, manifest.policy_fingerprint,
                           manifest.row_count, manifest.bronze_generation_id
                    FROM wfm_refresh_generation AS generation
                    JOIN wfm_source_manifest AS manifest
                      ON manifest.generation_id = generation.id
                    WHERE generation.id = ? AND manifest.source_type = ?
                      AND manifest.source_key = ?
                    """,
                    (bronze_owner, source.source_type, source.source_key),
                ).fetchone()
                if (
                    owner is None
                    or owner[0] != "succeeded"
                    or owner[1] != "present"
                    or tuple(owner[2:6])
                    != (
                        source.content_sha256,
                        source.adapter_version,
                        source.policy_fingerprint,
                        source.row_count,
                    )
                    or owner[6] != bronze_owner
                ):
                    raise ValueError("reused Bronze owner is not matching successful evidence")
            existing = connection.execute(
                """
                SELECT id, state, file_size, mtime_ns, content_sha256, adapter_version,
                       policy_fingerprint, row_count, bronze_generation_id
                FROM wfm_source_manifest
                WHERE generation_id = ? AND source_type = ? AND source_key = ?
                """,
                (generation_id, source.source_type, source.source_key),
            ).fetchone()
            fingerprint = (
                source.file_size,
                source.mtime_ns,
                source.content_sha256,
                source.adapter_version,
                source.policy_fingerprint,
                source.row_count,
                bronze_owner,
            )
            if existing is not None:
                if existing["state"] != "present" or tuple(existing[2:]) != fingerprint:
                    raise ValueError("source key already staged with different evidence")
                return int(existing["id"])
            cursor = connection.execute(
                """
                INSERT INTO wfm_source_manifest (
                    generation_id, source_type, source_key, file_size, mtime_ns,
                    content_sha256, adapter_version, policy_fingerprint, row_count,
                    bronze_generation_id, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation_id,
                    source.source_type,
                    source.source_key,
                    *fingerprint,
                    utc_now(),
                ),
            )
            return _inserted_id(cursor)

    def stage_removed_source(self, generation_id: int, *, source_type: str, source_key: str) -> int:
        """Make a previously active source absent without mutating older evidence."""
        _required_text(source_type, "source_type")
        _required_text(source_key, "source_key")
        with _write_transaction(self.path) as connection:
            _running(connection, generation_id)
            existing = connection.execute(
                """
                SELECT id, state FROM wfm_source_manifest
                WHERE generation_id = ? AND source_type = ? AND source_key = ?
                """,
                (generation_id, source_type, source_key),
            ).fetchone()
            if existing is not None:
                if existing["state"] != "removed":
                    raise ValueError("source key already staged as present")
                return int(existing["id"])
            cursor = connection.execute(
                """
                INSERT INTO wfm_source_manifest (
                    generation_id, source_type, source_key, state, file_size, mtime_ns,
                    content_sha256, adapter_version, policy_fingerprint, recorded_at
                ) VALUES (?, ?, ?, 'removed', 0, 0, '', '', '', ?)
                """,
                (generation_id, source_type, source_key, utc_now()),
            )
            return _inserted_id(cursor)

    def record_quality_issue(
        self,
        generation_id: int,
        *,
        issue_code: str,
        severity: str,
        details: str,
        source_key: str | None = None,
    ) -> int:
        _required_text(issue_code, "issue_code")
        _required_text(details, "details")
        if severity not in {"info", "warning", "error"}:
            raise ValueError("severity must be info, warning, or error")
        with _write_transaction(self.path) as connection:
            _running(connection, generation_id)
            cursor = connection.execute(
                """
                INSERT INTO wfm_quality_issue (
                    generation_id, source_key, issue_code, severity, details, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (generation_id, source_key, issue_code, severity, details, utc_now()),
            )
            return _inserted_id(cursor)

    def record_quality_issues(
        self,
        generation_id: int,
        issues: Iterable[QualityIssue],
    ) -> int:
        """Persist a batch of findings in one write transaction."""
        batch = tuple(issues)
        for issue in batch:
            _required_text(issue.issue_code, "issue_code")
            _required_text(issue.details, "details")
            if issue.severity not in {"info", "warning", "error"}:
                raise ValueError("severity must be info, warning, or error")
        if not batch:
            return 0
        recorded_at = utc_now()
        with _write_transaction(self.path) as connection:
            _running(connection, generation_id)
            connection.executemany(
                """
                INSERT INTO wfm_quality_issue (
                    generation_id, source_key, issue_code, severity, details, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        generation_id,
                        issue.source_key,
                        issue.issue_code,
                        issue.severity,
                        issue.details,
                        recorded_at,
                    )
                    for issue in batch
                ],
            )
        return len(batch)

    def activate_generation(
        self,
        generation_id: int,
        *,
        publish: Callable[[sqlite3.Connection, int], None] | None = None,
    ) -> None:
        """Commit validated facts and the active pointer together, or neither."""
        with _write_transaction(self.path) as connection:
            generation = _running(connection, generation_id)
            active = connection.execute(
                "SELECT generation_id FROM wfm_active_generation WHERE singleton = 1"
            ).fetchone()
            if active is None:
                raise RuntimeError("active-generation control row is missing")
            if active[0] != generation["base_generation_id"]:
                raise RuntimeError("active generation changed since this refresh began")
            has_error = connection.execute(
                """
                SELECT 1 FROM wfm_quality_issue
                WHERE generation_id = ? AND severity = 'error' LIMIT 1
                """,
                (generation_id,),
            ).fetchone()
            if has_error is not None:
                raise ValueError("refresh generation has blocking quality issues")
            if publish is not None:
                publish(connection, generation_id)
            connection.execute(
                """
                UPDATE wfm_refresh_generation
                SET status = 'succeeded', finished_at = ? WHERE id = ?
                """,
                (utc_now(), generation_id),
            )
            connection.execute(
                "UPDATE wfm_active_generation SET generation_id = ? WHERE singleton = 1",
                (generation_id,),
            )

    def fail_generation(self, generation_id: int, *, reason: str) -> None:
        _required_text(reason, "reason")
        with _write_transaction(self.path) as connection:
            _running(connection, generation_id)
            connection.execute(
                """
                UPDATE wfm_refresh_generation
                SET status = 'failed', finished_at = ?, failure_reason = ? WHERE id = ?
                """,
                (utc_now(), reason, generation_id),
            )

    def restore_previous_generation(self, *, expected_active_id: int) -> int | None:
        """Atomically undo one activation; never silently discard a newer one."""
        with _write_transaction(self.path) as connection:
            active = connection.execute(
                "SELECT generation_id FROM wfm_active_generation WHERE singleton = 1"
            ).fetchone()
            if active is None or active[0] != expected_active_id:
                raise RuntimeError("active generation changed; rollback was not applied")
            row = connection.execute(
                """
                SELECT status, base_generation_id FROM wfm_refresh_generation WHERE id = ?
                """,
                (expected_active_id,),
            ).fetchone()
            if row is None or row[0] != "succeeded":
                raise ValueError("only an active successful generation can be rolled back")
            previous = row[1]
            connection.execute(
                "UPDATE wfm_active_generation SET generation_id = ? WHERE singleton = 1",
                (previous,),
            )
            return previous
