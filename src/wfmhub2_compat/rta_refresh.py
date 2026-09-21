"""Governed local source refresh for the policy-compatible RTA host.

The coordinator reads a fixed folder contract.  It never accepts uploaded
content and never writes into the source tree.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from wfmhub2_compat.refresh_store import RefreshStore
from wfmhub2_compat.source_contracts import (
    FteSnapshot,
    ScheduleSnapshot,
    SourceContractError,
    SourceSnapshot,
    make_source_publish,
    parse_fte_workbook,
    parse_start_end_times,
    stage_findings,
    stage_sources,
)

SOURCE_POINTER = Path("data/source-root.txt")
DEFAULT_SOURCE_ROOT = Path("extracts")
FTE_DIRECTORY = Path("FTE")
SCHEDULE_DIRECTORY = Path("Verint/Schedules & Activities")
MAX_SOURCE_POINTER_BYTES = 4096
REFRESH_MODEL_VERSION = "rta-fte-schedule-v2"
REFRESH_CATALOG_SHA256 = hashlib.sha256(
    b"WFMHub2|FTE/FTE Count.xlsx|Verint/Schedules & Activities/*.txt|v2"
).hexdigest()


def _catalog_fingerprint(root: Path) -> str:
    """Bind a published generation to the selected local source directory."""
    material = f"{REFRESH_CATALOG_SHA256}|{root.resolve()}".encode()
    return hashlib.sha256(material).hexdigest()


class RefreshBusyError(RuntimeError):
    """Another process-local refresh owns the coordinator lock."""


class RefreshFailedError(RuntimeError):
    """A safe, actionable refresh error suitable for the local API."""

    def __init__(self, code: str, message: str, *, generation_id: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.generation_id = generation_id


@dataclass(frozen=True)
class ResolvedSourceRoot:
    path: Path
    mode: Literal["default", "configured"]
    display_name: str

    def api_value(self) -> dict[str, str]:
        result = {"mode": self.mode, "displayName": self.display_name}
        if self.mode == "configured":
            result["pointerPath"] = SOURCE_POINTER.as_posix()
        return result


def _configuration_problem(code: str, message: str) -> RefreshFailedError:
    return RefreshFailedError(code, message)


def resolve_source_root(home: Path) -> ResolvedSourceRoot:
    """Resolve the default extracts tree or a read-only local pointer."""
    pointer = home / SOURCE_POINTER
    if not pointer.exists():
        return ResolvedSourceRoot(home / DEFAULT_SOURCE_ROOT, "default", "extracts")
    if not pointer.is_file():
        raise _configuration_problem(
            "INVALID_SOURCE_ROOT_POINTER",
            "data/source-root.txt must be a regular UTF-8 text file.",
        )
    size = pointer.stat().st_size
    if size == 0 or size > MAX_SOURCE_POINTER_BYTES:
        raise _configuration_problem(
            "INVALID_SOURCE_ROOT_POINTER",
            "data/source-root.txt must contain one bounded path line.",
        )
    try:
        text = pointer.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise _configuration_problem(
            "INVALID_SOURCE_ROOT_POINTER",
            "data/source-root.txt must be valid UTF-8.",
        ) from exc
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].strip() or lines[0] != lines[0].strip():
        raise _configuration_problem(
            "INVALID_SOURCE_ROOT_POINTER",
            "data/source-root.txt must contain exactly one absolute path line.",
        )
    configured = Path(lines[0])
    if not configured.is_absolute() or not configured.is_dir():
        raise _configuration_problem(
            "INVALID_SOURCE_ROOT_POINTER",
            "The configured source root must be an existing absolute directory.",
        )
    return ResolvedSourceRoot(configured, "configured", "Configured local folder")


def _is_candidate_file(path: Path, suffix: str) -> bool:
    return (
        path.is_file()
        and not path.name.startswith("~$")
        and not path.name.startswith(".")
        and path.suffix.casefold() == suffix
    )


def _source_key(source_root: Path, path: Path) -> str:
    return path.relative_to(source_root).as_posix()


def _discover_roster(source_root: Path) -> FteSnapshot:
    directory = source_root / FTE_DIRECTORY
    candidates = (
        sorted(
            (path for path in directory.iterdir() if _is_candidate_file(path, ".xlsx")),
            key=lambda path: path.name.casefold(),
        )
        if directory.is_dir()
        else []
    )
    matches: list[FteSnapshot] = []
    for path in candidates:
        try:
            matches.append(parse_fte_workbook(path, source_key=_source_key(source_root, path)))
        except SourceContractError:
            continue
    if not matches:
        if candidates:
            raise RefreshFailedError(
                "INVALID_FTE_SOURCE",
                "No workbook in FTE contains one valid roster contract. "
                "Check its Agent/FTE headers.",
            )
        raise RefreshFailedError(
            "MISSING_FTE_SOURCE",
            "Place the FTE roster workbook under FTE and run refresh again.",
        )
    if len(matches) > 1:
        raise RefreshFailedError(
            "AMBIGUOUS_FTE_SOURCE",
            "More than one workbook contains an authoritative FTE roster; keep one current source.",
        )
    return matches[0]


def _schedule_header_matches(path: Path) -> bool:
    try:
        with path.open("r", encoding="cp1252", newline="") as handle:
            headers = next(csv.reader(handle, delimiter="\t", strict=True))
    except (OSError, StopIteration, csv.Error):
        return False
    normalized = [
        value.strip().lstrip("\ufeff") if index == 0 else value.strip()
        for index, value in enumerate(headers)
    ]
    if len(normalized) < 3 or normalized[:2] != ["Name", "Data Source IDs"]:
        return False
    # Activities is a separate contract and must never become the shift boundary.
    if {"Scheduling Period", "Shift Assignment", "Shift Events"} <= set(normalized):
        return False
    # Once a file presents as a wide schedule, malformed date columns must
    # fail validation instead of being silently dropped as an unsupported file.
    return any(
        _is_date(value, pattern)
        for value in normalized[2:]
        for pattern in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y")
    )


def _is_date(value: str, pattern: str) -> bool:
    try:
        datetime.strptime(value, pattern)
    except ValueError:
        return False
    return True


def _discover_schedules(source_root: Path, roster: FteSnapshot) -> tuple[ScheduleSnapshot, ...]:
    directory = source_root / SCHEDULE_DIRECTORY
    candidates = (
        sorted(
            (
                path
                for path in directory.iterdir()
                if _is_candidate_file(path, ".txt") and _schedule_header_matches(path)
            ),
            key=lambda path: path.name.casefold(),
        )
        if directory.is_dir()
        else []
    )
    if not candidates:
        raise RefreshFailedError(
            "MISSING_PUBLISHED_SCHEDULE",
            "Place at least one wide StartEndTimes text export under "
            "Verint/Schedules & Activities and run refresh again.",
        )
    schedules: list[ScheduleSnapshot] = []
    for path in candidates:
        try:
            schedules.append(
                parse_start_end_times(
                    path,
                    source_key=_source_key(source_root, path),
                    roster=roster,
                )
            )
        except SourceContractError as exc:
            detail = str(exc).replace(str(source_root), "<source-root>")[:240]
            raise RefreshFailedError(
                "INVALID_PUBLISHED_SCHEDULE",
                f"Published schedule {_source_key(source_root, path)} failed: {detail}",
            ) from exc
        except (csv.Error, UnicodeError, OSError) as exc:
            problem = (
                "Malformed TSV quoting or field boundary"
                if isinstance(exc, csv.Error)
                else "Text encoding could not be read"
                if isinstance(exc, UnicodeError)
                else "Source file could not be read"
            )
            raise RefreshFailedError(
                "INVALID_PUBLISHED_SCHEDULE",
                f"Published schedule {_source_key(source_root, path)} failed: {problem}.",
            ) from exc
    return tuple(schedules)


def _generation_summary(connection: sqlite3.Connection, generation_id: int) -> dict[str, Any]:
    connection.row_factory = sqlite3.Row
    generation = connection.execute(
        """
        SELECT id, status, started_at, finished_at, failure_reason, catalog_sha256
        FROM wfm_refresh_generation WHERE id = ?
        """,
        (generation_id,),
    ).fetchone()
    if generation is None:
        raise RuntimeError("refresh generation is missing")
    counts = connection.execute(
        """
        SELECT
          (SELECT count(*) FROM wfm_agent_roster WHERE generation_id = ?) AS roster_agents,
          (SELECT count(*) FROM wfm_time_off WHERE generation_id = ?) AS time_off_records,
          (SELECT count(*) FROM wfm_schedule_shift WHERE generation_id = ?) AS schedule_assignments,
          (SELECT count(*) FROM wfm_source_manifest
             WHERE generation_id = ? AND state = 'present') AS source_files
        """,
        (generation_id, generation_id, generation_id, generation_id),
    ).fetchone()
    schedule_range = connection.execute(
        """
        SELECT min(business_date), max(business_date)
        FROM wfm_schedule_shift WHERE generation_id = ?
        """,
        (generation_id,),
    ).fetchone()
    quality = {"info": 0, "warning": 0, "error": 0}
    for severity, count in connection.execute(
        """
        SELECT severity, count(*) FROM wfm_quality_issue
        WHERE generation_id = ? GROUP BY severity
        """,
        (generation_id,),
    ):
        quality[str(severity)] = int(count)
    result: dict[str, Any] = {
        "generationId": int(generation["id"]),
        "status": str(generation["status"]),
        "startedAt": str(generation["started_at"]),
        "finishedAt": generation["finished_at"],
        "counts": {
            "rosterAgents": int(counts["roster_agents"]),
            "timeOffRecords": int(counts["time_off_records"]),
            "scheduleAssignments": int(counts["schedule_assignments"]),
            "sourceFiles": int(counts["source_files"]),
        },
        "dateRange": {
            "from": schedule_range[0],
            "to": schedule_range[1],
        },
        "qualityCounts": quality,
        "sourceCatalogFingerprint": str(generation["catalog_sha256"]),
    }
    if generation["failure_reason"] is not None:
        result["failureCode"] = str(generation["failure_reason"])
    return result


class RtaRefreshCoordinator:
    """Single-process refresh coordinator and safe source-health reader."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.store = RefreshStore(home / "data/control.sqlite")
        self._refresh_lock = threading.Lock()

    def source_health(self) -> dict[str, Any]:
        selected_fingerprint: str | None = None
        try:
            root = resolve_source_root(self.home)
            root_value: dict[str, Any] = root.api_value()
            selected_fingerprint = _catalog_fingerprint(root.path)
        except RefreshFailedError as exc:
            root_value = {
                "mode": "invalid",
                "pointerPath": SOURCE_POINTER.as_posix(),
                "errorCode": exc.code,
            }
        with closing(sqlite3.connect(self.store.path)) as connection:
            active_row = connection.execute(
                "SELECT generation_id FROM wfm_active_generation WHERE singleton = 1"
            ).fetchone()
            latest_row = connection.execute(
                "SELECT id FROM wfm_refresh_generation ORDER BY id DESC LIMIT 1"
            ).fetchone()
            active = (
                _generation_summary(connection, int(active_row[0]))
                if active_row is not None and active_row[0] is not None
                else None
            )
            latest = (
                _generation_summary(connection, int(latest_row[0]))
                if latest_row is not None
                else None
            )
        active_counts = active["counts"] if active is not None else None
        active_range = active["dateRange"] if active is not None else None
        source_ready = (
            active is not None
            and selected_fingerprint is not None
            and active["sourceCatalogFingerprint"] == selected_fingerprint
        )
        if active is not None:
            active.pop("sourceCatalogFingerprint")
        if latest is not None:
            latest.pop("sourceCatalogFingerprint")
        return {
            "status": (
                "configuration_error"
                if root_value["mode"] == "invalid"
                else "ready"
                if source_ready
                else "source_changed"
                if active is not None
                else "not_ready"
            ),
            "ready": source_ready,
            "sourceRoot": root_value,
            "configuredSources": {
                "fte": FTE_DIRECTORY.as_posix(),
                "publishedSchedules": SCHEDULE_DIRECTORY.as_posix(),
            },
            "activeGeneration": active,
            "activeGenerationId": active["generationId"] if active is not None else None,
            "latestRefresh": latest,
            "quality": active["qualityCounts"]
            if active is not None
            else {"info": 0, "warning": 0, "error": 0},
            "sources": {
                "roster": {
                    "ready": source_ready,
                    "agentCount": active_counts["rosterAgents"] if active_counts else 0,
                    "timeOffCount": active_counts["timeOffRecords"] if active_counts else 0,
                    "fileCount": 1 if active_counts else 0,
                },
                "schedule": {
                    "ready": source_ready,
                    "shiftCount": active_counts["scheduleAssignments"] if active_counts else 0,
                    "fileCount": active_counts["sourceFiles"] - 1 if active_counts else 0,
                    "minDate": active_range["from"] if active_range else None,
                    "maxDate": active_range["to"] if active_range else None,
                },
            },
        }

    def refresh(self) -> dict[str, Any]:
        if not self._refresh_lock.acquire(blocking=False):
            raise RefreshBusyError("A source refresh is already running.")
        generation_id: int | None = None
        try:
            root = resolve_source_root(self.home)
            generation_id = self.store.start_generation(
                catalog_sha256=_catalog_fingerprint(root.path),
                model_version=REFRESH_MODEL_VERSION,
            )
            roster = _discover_roster(root.path)
            schedules = _discover_schedules(root.path, roster)
            snapshot = SourceSnapshot(roster, schedules)
            stage_sources(self.store, generation_id, snapshot)
            stage_findings(self.store, generation_id, snapshot)
            if any(finding.severity == "error" for finding in snapshot.findings):
                raise RefreshFailedError(
                    "BLOCKING_SOURCE_QUALITY",
                    "Source validation found blocking errors. Correct the source rows and retry.",
                )
            self.store.activate_generation(
                generation_id,
                publish=make_source_publish(snapshot),
            )
            return {
                "status": "succeeded",
                "generationId": generation_id,
                "sourceHealth": self.source_health(),
            }
        except RefreshFailedError as exc:
            if generation_id is not None:
                self.store.fail_generation(generation_id, reason=exc.code)
            raise RefreshFailedError(
                exc.code,
                exc.message,
                generation_id=generation_id,
            ) from exc
        except Exception as exc:
            code = "REFRESH_FAILED"
            if generation_id is not None:
                self.store.fail_generation(generation_id, reason=code)
            raise RefreshFailedError(
                code,
                "Refresh failed safely; the previous active generation was preserved.",
                generation_id=generation_id,
            ) from exc
        finally:
            self._refresh_lock.release()


def validate_refresh_body(payload: Any) -> None:
    if not isinstance(payload, dict) or payload:
        raise ValueError("refresh request must be an empty JSON object")


def encode_api_json(payload: dict[str, Any]) -> bytes:
    """Shared deterministic encoding, primarily useful to boundary tests."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
