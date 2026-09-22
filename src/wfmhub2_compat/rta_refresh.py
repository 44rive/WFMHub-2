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

from wfmhub2_compat.actual_contracts import (
    ActualKind,
    ActualSourcePlan,
    StatusPolicy,
    load_status_policy,
    preflight_actual_source,
    publish_actual_plans,
    stage_actual_plans,
)
from wfmhub2_compat.call_contracts import (
    CallPolicy,
    CallSourcePlan,
    load_call_policy,
    preflight_call_source,
    publish_call_plans,
    stage_call_plans,
)
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
AGENT_STATUS_DIRECTORY = Path("Storm/Agent Status")
LILO_DIRECTORY = Path("Storm/LILO")
CALL_DIRECTORY = Path("Storm/Call by Call")
MAX_SOURCE_POINTER_BYTES = 4096
REFRESH_MODEL_VERSION = "rta-fte-schedule-actuals-calls-v5"
REFRESH_CATALOG_SHA256 = hashlib.sha256(
    b"WFMHub2|FTE/FTE Count.xlsx|Verint/Schedules & Activities/*.txt|"
    b"Storm/Agent Status/*.csv|Storm/LILO/*.csv|Storm/Call by Call/*.csv|v5"
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
) -> tuple[tuple[ActualSourcePlan, ...], StatusPolicy | None]:
    status_paths = _actual_candidates(source_root, AGENT_STATUS_DIRECTORY)
    lilo_paths = _actual_candidates(source_root, LILO_DIRECTORY)
    status_policy = load_status_policy() if status_paths else None
    plans: list[ActualSourcePlan] = []
    source_sets: tuple[tuple[ActualKind, list[Path]], ...] = (
        ("agent_status", status_paths),
        ("lilo", lilo_paths),
    )
    for kind, paths in source_sets:
        for path in paths:
            source_key = _source_key(source_root, path)
            try:
                plans.append(
                    preflight_actual_source(
                        path,
                        source_key=source_key,
                        kind=kind,
                        roster=roster,
                        status_policy=status_policy,
                    )
                )
            except SourceContractError as exc:
                label = "Agent Status" if kind == "agent_status" else "LILO"
                detail = str(exc).replace(str(source_root), "<source-root>")[:240]
                raise RefreshFailedError(
                    f"INVALID_{kind.upper()}_SOURCE",
                    f"{label} source {source_key} failed: {detail}",
                ) from exc
    return tuple(plans), status_policy


def _discover_calls(
    source_root: Path,
    roster: FteSnapshot,
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
    for path in paths:
        source_key = _source_key(source_root, path)
        try:
            plans.append(
                preflight_call_source(
                    path,
                    source_key=source_key,
                    roster=roster,
                    policy=policy,
                )
            )
        except SourceContractError as exc:
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
        (generation_id,) * 13,
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
            actuals, status_policy = _discover_actuals(root.path, roster)
            calls, call_policy = _discover_calls(root.path, roster)
            snapshot = SourceSnapshot(roster, schedules)
            stage_sources(self.store, generation_id, snapshot)
            stage_findings(self.store, generation_id, snapshot)
            stage_actual_plans(self.store, generation_id, actuals)
            stage_call_plans(self.store, generation_id, calls)
            if any(finding.severity == "error" for finding in snapshot.findings):
                raise RefreshFailedError(
                    "BLOCKING_SOURCE_QUALITY",
                    "Source validation found blocking errors. Correct the source rows and retry.",
                )
            source_publish = make_source_publish(snapshot)

            def publish(connection: sqlite3.Connection, active_generation_id: int) -> None:
                source_publish(connection, active_generation_id)
                publish_actual_plans(
                    connection,
                    active_generation_id,
                    actuals,
                    roster=roster,
                    status_policy=status_policy,
                )
                publish_call_plans(
                    connection,
                    active_generation_id,
                    calls,
                    roster=roster,
                    policy=call_policy,
                )

            self.store.activate_generation(generation_id, publish=publish)
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
