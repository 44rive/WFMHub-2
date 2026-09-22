"""Governed local source refresh for the policy-compatible RTA host.

The coordinator reads a fixed folder contract.  It never accepts uploaded
content and never writes into the source tree.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import threading
import time
import traceback
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from wfmhub2_compat.actual_contracts import (
    LILO_ADAPTER_VERSION,
    LILO_POLICY_FINGERPRINT,
    STATUS_ADAPTER_VERSION,
    ActualKind,
    ActualSourcePlan,
    StatusPolicy,
    load_status_policy,
    preflight_actual_source,
    publish_actual_plans,
    stage_actual_plans,
)
from wfmhub2_compat.attendance_model import (
    AttendancePolicy,
    build_attendance_model,
    load_attendance_policy,
)
from wfmhub2_compat.call_contracts import (
    CALL_ADAPTER_VERSION,
    CallPolicy,
    CallSourcePlan,
    load_call_policy,
    preflight_call_source,
    publish_call_plans,
    stage_call_plans,
)
from wfmhub2_compat.refresh_store import RefreshStore
from wfmhub2_compat.source_contracts import (
    FTE_ADAPTER_VERSION,
    FTE_POLICY_FINGERPRINT,
    SCHEDULE_ADAPTER_VERSION,
    SCHEDULE_POLICY_FINGERPRINT,
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
AGENT_STATUS_DIRECTORY = Path("Storm/Agent Status")
LILO_DIRECTORY = Path("Storm/LILO")
CALL_DIRECTORY = Path("Storm/Call by Call")
MAX_SOURCE_POINTER_BYTES = 4096
REFRESH_MODEL_VERSION = "rta-fte-schedule-actuals-calls-attendance-v6"
REFRESH_CATALOG_SHA256 = hashlib.sha256(
    b"WFMHub2|FTE/FTE Count.xlsx|Verint/Schedules & Activities/*.txt|"
    b"Storm/Agent Status/*.csv|Storm/LILO/*.csv|Storm/Call by Call/*.csv|"
    b"attendance-read-model-v1|v6"
).hexdigest()
DIAGNOSTIC_PATH = Path("data/diagnostics/refresh-failure.txt")

ProgressCallback = Callable[[str, str, int, int], None]


@dataclass(frozen=True)
class SourceInventoryEntry:
    source_type: str
    source_key: str
    file_size: int
    mtime_ns: int


def _candidate_paths(source_root: Path, directory: Path, suffix: str) -> list[Path]:
    candidate_directory = source_root / directory
    if not candidate_directory.is_dir():
        return []
    return sorted(
        (path for path in candidate_directory.iterdir() if _is_candidate_file(path, suffix)),
        key=lambda path: path.name.casefold(),
    )


def _source_inventory(source_root: Path) -> tuple[SourceInventoryEntry, ...]:
    """Read only cheap metadata for the exact governed candidate set."""
    typed_paths: list[tuple[str, Path]] = []
    typed_paths.extend(
        ("fte_roster", path) for path in _candidate_paths(source_root, FTE_DIRECTORY, ".xlsx")
    )
    typed_paths.extend(
        ("published_schedule", path)
        for path in _candidate_paths(source_root, SCHEDULE_DIRECTORY, ".txt")
        if _schedule_header_matches(path)
    )
    typed_paths.extend(
        ("agent_status", path)
        for path in _candidate_paths(source_root, AGENT_STATUS_DIRECTORY, ".csv")
    )
    typed_paths.extend(
        ("lilo", path) for path in _candidate_paths(source_root, LILO_DIRECTORY, ".csv")
    )
    typed_paths.extend(
        ("call_by_call", path) for path in _candidate_paths(source_root, CALL_DIRECTORY, ".csv")
    )
    inventory: list[SourceInventoryEntry] = []
    for source_type, path in typed_paths:
        stat = path.stat()
        inventory.append(
            SourceInventoryEntry(
                source_type,
                _source_key(source_root, path),
                stat.st_size,
                stat.st_mtime_ns,
            )
        )
    return tuple(sorted(inventory, key=lambda item: (item.source_type, item.source_key)))


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


def _source_changed_problem() -> RefreshFailedError:
    return RefreshFailedError(
        "SOURCE_CHANGED_DURING_REFRESH",
        "A source file changed while refresh was reading it. Wait for the export or copy "
        "to finish, then retry. The previous active generation was preserved.",
    )


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


def _discover_roster(source_root: Path, progress: ProgressCallback | None = None) -> FteSnapshot:
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
    for index, path in enumerate(candidates, 1):
        if progress is not None:
            progress("roster", _source_key(source_root, path), index - 1, len(candidates))
        try:
            matches.append(parse_fte_workbook(path, source_key=_source_key(source_root, path)))
        except SourceContractError as exc:
            if "changed" in str(exc).lower():
                raise _source_changed_problem() from exc
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


def _discover_schedules(
    source_root: Path,
    roster: FteSnapshot,
    progress: ProgressCallback | None = None,
) -> tuple[ScheduleSnapshot, ...]:
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
    for index, path in enumerate(candidates, 1):
        if progress is not None:
            progress("schedules", _source_key(source_root, path), index - 1, len(candidates))
        try:
            schedules.append(
                parse_start_end_times(
                    path,
                    source_key=_source_key(source_root, path),
                    roster=roster,
                )
            )
        except SourceContractError as exc:
            if "changed" in str(exc).lower():
                raise _source_changed_problem() from exc
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


def _actual_candidates(source_root: Path, directory: Path) -> list[Path]:
    source_directory = source_root / directory
    if not source_directory.is_dir():
        return []
    return sorted(
        (path for path in source_directory.iterdir() if _is_candidate_file(path, ".csv")),
        key=lambda path: path.name.casefold(),
    )


def _discover_actuals(
    source_root: Path,
    roster: FteSnapshot,
    progress: ProgressCallback | None = None,
    stage_database: Path | None = None,
    generation_id: int | None = None,
) -> tuple[tuple[ActualSourcePlan, ...], StatusPolicy | None]:
    status_paths = _actual_candidates(source_root, AGENT_STATUS_DIRECTORY)
    lilo_paths = _actual_candidates(source_root, LILO_DIRECTORY)
    status_policy = load_status_policy() if status_paths else None
    plans: list[ActualSourcePlan] = []
    source_sets: tuple[tuple[ActualKind, list[Path]], ...] = (
        ("agent_status", status_paths),
        ("lilo", lilo_paths),
    )
    total = len(status_paths) + len(lilo_paths)
    completed = 0
    for kind, paths in source_sets:
        for path in paths:
            source_key = _source_key(source_root, path)
            if progress is not None:
                progress("actuals", source_key, completed, total)
            try:
                plans.append(
                    preflight_actual_source(
                        path,
                        source_key=source_key,
                        kind=kind,
                        roster=roster,
                        status_policy=status_policy,
                        stage_database=stage_database,
                        generation_id=generation_id,
                    )
                )
            except SourceContractError as exc:
                if "changed" in str(exc).lower():
                    raise _source_changed_problem() from exc
                label = "Agent Status" if kind == "agent_status" else "LILO"
                detail = str(exc).replace(str(source_root), "<source-root>")[:240]
                raise RefreshFailedError(
                    f"INVALID_{kind.upper()}_SOURCE",
                    f"{label} source {source_key} failed: {detail}",
                ) from exc
            completed += 1
    return tuple(plans), status_policy


def _discover_calls(
    source_root: Path,
    roster: FteSnapshot,
    progress: ProgressCallback | None = None,
    stage_database: Path | None = None,
    generation_id: int | None = None,
) -> tuple[tuple[CallSourcePlan, ...], CallPolicy | None]:
    paths = _actual_candidates(source_root, CALL_DIRECTORY)
    if not paths:
        return (), None
    try:
        policy = load_call_policy()
    except (SourceContractError, ValueError) as exc:
        raise RefreshFailedError(
            "INVALID_CALL_POLICY",
            "The packaged queue mapping or service rules are invalid.",
        ) from exc
    plans: list[CallSourcePlan] = []
    for index, path in enumerate(paths, 1):
        source_key = _source_key(source_root, path)
        if progress is not None:
            progress("calls", source_key, index - 1, len(paths))
        try:
            plans.append(
                preflight_call_source(
                    path,
                    source_key=source_key,
                    roster=roster,
                    policy=policy,
                    stage_database=stage_database,
                    generation_id=generation_id,
                )
            )
        except SourceContractError as exc:
            if "changed" in str(exc).lower():
                raise _source_changed_problem() from exc
            detail = str(exc).replace(str(source_root), "<source-root>")[:240]
            raise RefreshFailedError(
                "INVALID_CALL_BY_CALL_SOURCE",
                f"Call by Call source {source_key} failed: {detail}",
            ) from exc
    return tuple(plans), policy


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
          (SELECT count(*) FROM wfm_raw_agent_status WHERE generation_id = ?) AS agent_status_rows,
          (SELECT count(*) FROM wfm_raw_lilo WHERE generation_id = ?) AS lilo_rows,
          (SELECT count(*) FROM wfm_raw_call_leg WHERE generation_id = ?) AS raw_call_legs,
          (SELECT count(*) FROM wfm_call_leg WHERE generation_id = ?) AS canonical_call_legs,
          (SELECT count(*) FROM wfm_service_interval WHERE generation_id = ?) AS service_intervals,
          (SELECT count(*) FROM wfm_attendance_agent_day
             WHERE generation_id = ?) AS attendance_agent_days,
          (SELECT count(*) FROM wfm_attendance_gap
             WHERE generation_id = ?) AS attendance_gap_fragments,
          (SELECT count(*) FROM wfm_attendance_agent_day
             WHERE generation_id = ? AND status_is_primary = 1) AS status_primary_days,
          (SELECT count(*) FROM wfm_attendance_agent_day
             WHERE generation_id = ? AND evidence_state = 'UNKNOWN') AS attendance_unknown_days,
          (SELECT count(*) FROM wfm_source_manifest
             WHERE generation_id = ? AND state = 'present') AS source_files,
          (SELECT count(*) FROM wfm_source_manifest
             WHERE generation_id = ? AND state = 'present'
               AND source_type = 'published_schedule') AS schedule_files,
          (SELECT count(*) FROM wfm_source_manifest
             WHERE generation_id = ? AND state = 'present'
               AND source_type = 'agent_status') AS agent_status_files,
          (SELECT count(*) FROM wfm_source_manifest
             WHERE generation_id = ? AND state = 'present'
               AND source_type = 'lilo') AS lilo_files,
          (SELECT count(*) FROM wfm_source_manifest
             WHERE generation_id = ? AND state = 'present'
               AND source_type = 'call_by_call') AS call_files
        """,
        (generation_id,) * 17,
    ).fetchone()
    schedule_range = connection.execute(
        """
        SELECT min(business_date), max(business_date)
        FROM wfm_schedule_shift WHERE generation_id = ?
        """,
        (generation_id,),
    ).fetchone()
    status_range = connection.execute(
        """
        SELECT min(extract_date), max(extract_date)
        FROM wfm_raw_agent_status WHERE generation_id = ?
        """,
        (generation_id,),
    ).fetchone()
    lilo_range = connection.execute(
        """
        SELECT min(extract_date), max(extract_date)
        FROM wfm_raw_lilo WHERE generation_id = ?
        """,
        (generation_id,),
    ).fetchone()
    call_range = connection.execute(
        """
        SELECT min(business_date), max(business_date)
        FROM wfm_call_leg WHERE generation_id = ?
        """,
        (generation_id,),
    ).fetchone()
    attendance_range = connection.execute(
        """
        SELECT min(business_date), max(business_date)
        FROM wfm_attendance_agent_day WHERE generation_id = ?
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
            "agentStatusRows": int(counts["agent_status_rows"]),
            "liloRows": int(counts["lilo_rows"]),
            "rawCallLegs": int(counts["raw_call_legs"]),
            "canonicalCallLegs": int(counts["canonical_call_legs"]),
            "serviceIntervals": int(counts["service_intervals"]),
            "attendanceAgentDays": int(counts["attendance_agent_days"]),
            "attendanceGapFragments": int(counts["attendance_gap_fragments"]),
            "statusPrimaryDays": int(counts["status_primary_days"]),
            "attendanceUnknownDays": int(counts["attendance_unknown_days"]),
            "sourceFiles": int(counts["source_files"]),
            "scheduleFiles": int(counts["schedule_files"]),
            "agentStatusFiles": int(counts["agent_status_files"]),
            "liloFiles": int(counts["lilo_files"]),
            "callFiles": int(counts["call_files"]),
        },
        "dateRange": {
            "from": schedule_range[0],
            "to": schedule_range[1],
        },
        "actualDateRanges": {
            "agentStatus": {"from": status_range[0], "to": status_range[1]},
            "lilo": {"from": lilo_range[0], "to": lilo_range[1]},
            "callByCall": {"from": call_range[0], "to": call_range[1]},
            "attendance": {"from": attendance_range[0], "to": attendance_range[1]},
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
        self._progress_lock = threading.Lock()
        self._progress: dict[str, Any] | None = None
        self._progress_started = 0.0

    def _set_progress(
        self,
        stage: str,
        message: str,
        completed_files: int = 0,
        total_files: int = 0,
    ) -> None:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self._progress_lock:
            if self._progress is None:
                self._progress_started = time.monotonic()
                started_at = now
            else:
                started_at = str(self._progress["startedAt"])
            self._progress = {
                "status": "running",
                "stage": stage,
                "message": message,
                "completedFiles": completed_files,
                "totalFiles": total_files,
                "startedAt": started_at,
            }

    def _progress_callback(self, stage: str, source_key: str, completed: int, total: int) -> None:
        label = {
            "roster": "Validating roster",
            "schedules": "Validating schedules",
            "actuals": "Validating Status and LILO",
            "calls": "Validating Call by Call",
            "publishing_actuals": "Publishing Status and LILO",
            "publishing_calls": "Publishing Call by Call",
        }.get(stage, "Refreshing sources")
        self._set_progress(stage, f"{label}: {source_key}", completed, total)

    def _progress_value(self) -> dict[str, Any] | None:
        with self._progress_lock:
            if self._progress is None:
                return None
            result = dict(self._progress)
            result["elapsedSeconds"] = max(0, int(time.monotonic() - self._progress_started))
            return result

    def _clear_progress(self) -> None:
        with self._progress_lock:
            self._progress = None
            self._progress_started = 0.0

    def _reusable_generation_id(
        self,
        source_root: Path,
        inventory: tuple[SourceInventoryEntry, ...],
    ) -> int | None:
        """Return the active cut only when cheap evidence and contracts match exactly."""
        expected_contracts: dict[str, tuple[str, str]] = {
            "fte_roster": (FTE_ADAPTER_VERSION, FTE_POLICY_FINGERPRINT),
            "published_schedule": (
                SCHEDULE_ADAPTER_VERSION,
                SCHEDULE_POLICY_FINGERPRINT,
            ),
            "lilo": (LILO_ADAPTER_VERSION, LILO_POLICY_FINGERPRINT),
        }
        try:
            if any(item.source_type == "agent_status" for item in inventory):
                status_policy = load_status_policy()
                expected_contracts["agent_status"] = (
                    STATUS_ADAPTER_VERSION,
                    status_policy.fingerprint,
                )
            if any(item.source_type == "call_by_call" for item in inventory):
                call_policy = load_call_policy()
                expected_contracts["call_by_call"] = (
                    CALL_ADAPTER_VERSION,
                    call_policy.fingerprint,
                )
            attendance_policy = load_attendance_policy()
        except (OSError, UnicodeError, ValueError, SourceContractError):
            return None

        with closing(sqlite3.connect(self.store.path)) as connection:
            connection.row_factory = sqlite3.Row
            generation = connection.execute(
                """
                SELECT generation.id, generation.status, generation.catalog_sha256,
                       generation.model_version
                FROM wfm_active_generation AS active
                JOIN wfm_refresh_generation AS generation
                  ON generation.id = active.generation_id
                WHERE active.singleton = 1
                """
            ).fetchone()
            if (
                generation is None
                or generation["status"] != "succeeded"
                or generation["catalog_sha256"] != _catalog_fingerprint(source_root)
                or generation["model_version"] != REFRESH_MODEL_VERSION
            ):
                return None
            manifest_rows = connection.execute(
                """
                SELECT source_type, source_key, state, file_size, mtime_ns,
                       adapter_version, policy_fingerprint
                FROM wfm_source_manifest WHERE generation_id = ?
                """,
                (int(generation["id"]),),
            ).fetchall()
            attendance_fingerprints = {
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT DISTINCT policy_fingerprint
                    FROM wfm_attendance_agent_day WHERE generation_id = ?
                    """,
                    (int(generation["id"]),),
                )
            }

        active = {
            (str(row["source_type"]), str(row["source_key"])): (
                str(row["state"]),
                int(row["file_size"]),
                int(row["mtime_ns"]),
                str(row["adapter_version"]),
                str(row["policy_fingerprint"]),
            )
            for row in manifest_rows
        }
        current = {
            (item.source_type, item.source_key): (item.file_size, item.mtime_ns)
            for item in inventory
        }
        if set(active) != set(current):
            return None
        for key, metadata in current.items():
            state, file_size, mtime_ns, adapter, policy = active[key]
            contract = expected_contracts.get(key[0])
            if (
                state != "present"
                or (file_size, mtime_ns) != metadata
                or contract is None
                or (adapter, policy) != contract
            ):
                return None
        if attendance_fingerprints and attendance_fingerprints != {attendance_policy.fingerprint}:
            return None
        return int(generation["id"])

    def _write_failure_diagnostic(
        self,
        *,
        stage: str,
        code: str,
        generation_id: int | None,
        exc: BaseException,
        print_traceback: bool = True,
    ) -> bool:
        saved = False
        try:
            destination = self.home / DIAGNOSTIC_PATH
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(".tmp")
            body = "\n".join(
                (
                    "WFMHub 2 refresh failure diagnostic",
                    f"recorded_at={datetime.now(UTC).isoformat(timespec='seconds')}",
                    f"stage={stage}",
                    f"code={code}",
                    f"generation_id={generation_id if generation_id is not None else 'none'}",
                    f"exception_type={type(exc).__name__}",
                    "",
                    "".join(traceback.format_exception(exc)),
                )
            )
            temporary.write_text(body, encoding="utf-8")
            os.replace(temporary, destination)
            saved = True
        except OSError:
            # Diagnostics are best-effort; never replace the original refresh failure.
            pass
        if print_traceback:
            traceback.print_exception(exc)
        return saved

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
        active_actual_ranges = active["actualDateRanges"] if active is not None else None
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
            "refreshProgress": self._progress_value(),
            "sourceRoot": root_value,
            "configuredSources": {
                "fte": FTE_DIRECTORY.as_posix(),
                "publishedSchedules": SCHEDULE_DIRECTORY.as_posix(),
                "agentStatus": AGENT_STATUS_DIRECTORY.as_posix(),
                "lilo": LILO_DIRECTORY.as_posix(),
                "callByCall": CALL_DIRECTORY.as_posix(),
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
                    "fileCount": active_counts["scheduleFiles"] if active_counts else 0,
                    "minDate": active_range["from"] if active_range else None,
                    "maxDate": active_range["to"] if active_range else None,
                },
                "agentStatus": {
                    "ready": bool(
                        source_ready and active_counts and active_counts["agentStatusFiles"] > 0
                    ),
                    "rowCount": active_counts["agentStatusRows"] if active_counts else 0,
                    "fileCount": active_counts["agentStatusFiles"] if active_counts else 0,
                    "minDate": (
                        active_actual_ranges["agentStatus"]["from"]
                        if active_actual_ranges
                        else None
                    ),
                    "maxDate": (
                        active_actual_ranges["agentStatus"]["to"] if active_actual_ranges else None
                    ),
                },
                "lilo": {
                    "ready": bool(
                        source_ready and active_counts and active_counts["liloFiles"] > 0
                    ),
                    "rowCount": active_counts["liloRows"] if active_counts else 0,
                    "fileCount": active_counts["liloFiles"] if active_counts else 0,
                    "minDate": active_actual_ranges["lilo"]["from"]
                    if active_actual_ranges
                    else None,
                    "maxDate": active_actual_ranges["lilo"]["to"] if active_actual_ranges else None,
                },
                "callByCall": {
                    "ready": bool(
                        source_ready and active_counts and active_counts["callFiles"] > 0
                    ),
                    "rawLegCount": active_counts["rawCallLegs"] if active_counts else 0,
                    "canonicalLegCount": (
                        active_counts["canonicalCallLegs"] if active_counts else 0
                    ),
                    "serviceIntervalCount": (
                        active_counts["serviceIntervals"] if active_counts else 0
                    ),
                    "fileCount": active_counts["callFiles"] if active_counts else 0,
                    "minDate": (
                        active_actual_ranges["callByCall"]["from"] if active_actual_ranges else None
                    ),
                    "maxDate": (
                        active_actual_ranges["callByCall"]["to"] if active_actual_ranges else None
                    ),
                },
                "attendance": {
                    "ready": bool(
                        source_ready
                        and active_counts
                        and active_counts["attendanceAgentDays"] > 0
                        and (
                            active_counts["agentStatusFiles"] > 0 or active_counts["liloFiles"] > 0
                        )
                    ),
                    "agentDayCount": active_counts["attendanceAgentDays"] if active_counts else 0,
                    "gapFragmentCount": active_counts["attendanceGapFragments"]
                    if active_counts
                    else 0,
                    "statusPrimaryCount": active_counts["statusPrimaryDays"]
                    if active_counts
                    else 0,
                    "unknownCount": active_counts["attendanceUnknownDays"] if active_counts else 0,
                    "minDate": (
                        active_actual_ranges["attendance"]["from"] if active_actual_ranges else None
                    ),
                    "maxDate": (
                        active_actual_ranges["attendance"]["to"] if active_actual_ranges else None
                    ),
                },
            },
        }

    def refresh(self) -> dict[str, Any]:
        if not self._refresh_lock.acquire(blocking=False):
            raise RefreshBusyError("A source refresh is already running.")
        generation_id: int | None = None
        stage = "resolving_sources"
        started = time.monotonic()
        try:
            self._set_progress(stage, "Resolving the configured source folder")
            root = resolve_source_root(self.home)
            stage = "inventory"
            self._set_progress(stage, "Checking source metadata")
            inventory = _source_inventory(root.path)
            reusable = self._reusable_generation_id(root.path, inventory)
            if reusable is not None:
                self._set_progress(
                    "complete", "Sources are unchanged", len(inventory), len(inventory)
                )
                result = {
                    "status": "succeeded",
                    "generationId": reusable,
                    "unchanged": True,
                    "durationMs": int((time.monotonic() - started) * 1000),
                    "sourceHealth": self.source_health(),
                }
                return result
            generation_id = self.store.start_generation(
                catalog_sha256=_catalog_fingerprint(root.path),
                model_version=REFRESH_MODEL_VERSION,
            )
            stage = "roster"
            roster = _discover_roster(root.path, self._progress_callback)
            stage = "schedules"
            schedules = _discover_schedules(root.path, roster, self._progress_callback)
            snapshot = SourceSnapshot(roster, schedules)
            if any(finding.severity == "error" for finding in snapshot.findings):
                stage = "staging_evidence"
                self._set_progress(stage, "Recording blocking source findings")
                stage_sources(self.store, generation_id, snapshot)
                stage_findings(self.store, generation_id, snapshot)
                raise RefreshFailedError(
                    "BLOCKING_SOURCE_QUALITY",
                    "Source validation found blocking errors. Correct the source rows and retry.",
                )
            stage = "actuals"
            actuals, status_policy = _discover_actuals(
                root.path,
                roster,
                self._progress_callback,
                self.store.path,
                generation_id,
            )
            stage = "calls"
            calls, call_policy = _discover_calls(
                root.path,
                roster,
                self._progress_callback,
                self.store.path,
                generation_id,
            )
            stage = "attendance_policy"
            self._set_progress(stage, "Loading attendance policy")
            attendance_policy: AttendancePolicy = load_attendance_policy()
            stage = "staging_evidence"
            self._set_progress(stage, "Recording validated source evidence")
            stage_sources(self.store, generation_id, snapshot)
            stage_findings(self.store, generation_id, snapshot)
            stage_actual_plans(self.store, generation_id, actuals)
            stage_call_plans(self.store, generation_id, calls)
            source_publish = make_source_publish(snapshot)

            def publish(connection: sqlite3.Connection, active_generation_id: int) -> None:
                nonlocal stage
                stage = "publishing_roster_schedules"
                self._set_progress(stage, "Publishing roster and schedules")
                source_publish(connection, active_generation_id)
                stage = "publishing_actuals"
                publish_actual_plans(
                    connection,
                    active_generation_id,
                    actuals,
                    roster=roster,
                    status_policy=status_policy,
                    progress=self._progress_callback,
                    rows_staged=True,
                )
                stage = "attendance"
                self._set_progress(stage, "Building attendance evidence")
                build_attendance_model(
                    connection,
                    active_generation_id,
                    policy=attendance_policy,
                )
                stage = "publishing_calls"
                publish_call_plans(
                    connection,
                    active_generation_id,
                    calls,
                    roster=roster,
                    policy=call_policy,
                    progress=self._progress_callback,
                    rows_staged=True,
                )

            stage = "commit"
            self._set_progress(stage, "Publishing the validated generation")
            self.store.activate_generation(generation_id, publish=publish)
            self._set_progress("complete", "Refresh complete")
            return {
                "status": "succeeded",
                "generationId": generation_id,
                "unchanged": False,
                "durationMs": int((time.monotonic() - started) * 1000),
                "sourceHealth": self.source_health(),
            }
        except RefreshFailedError as exc:
            if generation_id is not None:
                self.store.fail_generation(generation_id, reason=exc.code)
            self._write_failure_diagnostic(
                stage=stage,
                code=exc.code,
                generation_id=generation_id,
                exc=exc,
                print_traceback=False,
            )
            raise RefreshFailedError(
                exc.code,
                exc.message,
                generation_id=generation_id,
            ) from exc
        except Exception as exc:
            stage_code = "".join(character if character.isalnum() else "_" for character in stage)
            type_code = "".join(
                character if character.isalnum() else "_" for character in type(exc).__name__
            )
            source_changed = isinstance(exc, SourceContractError) and "changed" in str(exc).lower()
            code = (
                "SOURCE_CHANGED_DURING_REFRESH"
                if source_changed
                else f"REFRESH_FAILED_{stage_code}_{type_code}".upper()
            )
            if generation_id is not None:
                self.store.fail_generation(generation_id, reason=code)
            diagnostic_saved = self._write_failure_diagnostic(
                stage=stage,
                code=code,
                generation_id=generation_id,
                exc=exc,
            )
            message = (
                "A source file changed while refresh was reading it. Wait for the export or copy "
                "to finish, then retry. The previous active generation was preserved."
                if source_changed
                else f"Refresh failed safely during {stage.replace('_', ' ')} "
                f"({type(exc).__name__}). The previous active generation was preserved. "
                + (
                    f"Details were saved locally to {DIAGNOSTIC_PATH.as_posix()}."
                    if diagnostic_saved
                    else "The diagnostic file could not be written; see the launcher console."
                )
            )
            raise RefreshFailedError(
                code,
                message,
                generation_id=generation_id,
            ) from exc
        finally:
            self._clear_progress()
            self._refresh_lock.release()


def validate_refresh_body(payload: Any) -> None:
    if not isinstance(payload, dict) or payload:
        raise ValueError("refresh request must be an empty JSON object")


def encode_api_json(payload: dict[str, Any]) -> bytes:
    """Shared deterministic encoding, primarily useful to boundary tests."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
