"""Streaming Agent Status and LILO evidence contracts.

The source exports can contain millions of rows.  Preflight therefore keeps
only bounded counters and findings in memory.  Publication replays the exact
byte-bound source inside the generation activation transaction and inserts in
bounded batches; a changed source aborts and rolls back the whole generation.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

from wfmhub2_compat.refresh_store import QualityIssue, RefreshStore, SourceVersion
from wfmhub2_compat.source_contracts import AgentScope, FteSnapshot, ScopeMatch, SourceContractError

ActualKind = Literal["agent_status", "lilo"]

STATUS_REQUIRED_HEADERS = {
    "[Serial Number]",
    "[Status]",
    "[Status Start Date and Time]",
    "[Agent]",
    "[Agent ID]",
    "[Status Duration]",
    "[Queue]",
}
LILO_REQUIRED_HEADERS = {
    "[Agent]",
    "[Agent ID]",
    "[First Log-on Time]",
    "[Last Log-off Time]",
}
STATUS_ADAPTER_VERSION = "agent-status-v2"
LILO_ADAPTER_VERSION = "lilo-v1"
LILO_POLICY_FINGERPRINT = hashlib.sha256(
    b"lilo|row-date-login-logout-single-iso-filename|scope-v1"
).hexdigest()
_FILENAME_DATE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
_INVALID_IDS = {"", "-", "N/A", "NA", "NULL", "NONE"}
_BATCH_SIZE = 5000
_INSERT_LILO = """
INSERT INTO wfm_raw_lilo (
    generation_id, source_key, source_row, extract_date, source_agent_id,
    roster_client_id, agent_name, first_login, raw_last_logout, last_logout,
    overnight_adjusted, scope_match
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
_INSERT_STATUS = """
INSERT INTO wfm_raw_agent_status (
    generation_id, source_key, source_row, serial_number, extract_date,
    source_agent_id, roster_client_id, agent_name, status, actual_category,
    status_start, status_end, duration_seconds, queue, scope_match
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass(frozen=True)
class _Fingerprint:
    file_size: int
    mtime_ns: int
    content_sha256: str


@dataclass(frozen=True)
class StatusPolicy:
    categories: Mapping[str, str]
    fingerprint: str

    def classify(self, value: str | None) -> str:
        normalized = _normalized_status(value)
        configured = self.categories.get(normalized)
        return configured if configured is not None else _fallback_status(value)


@dataclass(frozen=True)
class LiloRow:
    source_row: int
    extract_date: date
    source_agent_id: str | None
    roster_client_id: str
    agent_name: str | None
    first_login: datetime | None
    raw_last_logout: datetime | None
    last_logout: datetime | None
    overnight_adjusted: bool
    scope_match: ScopeMatch


@dataclass(frozen=True)
class AgentStatusRow:
    source_row: int
    serial_number: str
    extract_date: date
    source_agent_id: str | None
    roster_client_id: str
    agent_name: str | None
    status: str | None
    actual_category: str
    status_start: datetime
    status_end: datetime
    duration_seconds: int
    queue: str | None
    scope_match: ScopeMatch


@dataclass(frozen=True)
class ActualSourcePlan:
    path: Path
    source_key: str
    kind: ActualKind
    version: SourceVersion
    findings: tuple[QualityIssue, ...]
    accepted_rows: int
    scoped_out_rows: int
    rejected_rows: int
    date_from: date | None
    date_to: date | None
    date_field: str | None = None
    fallback_date: date | None = None


def default_status_policy_path() -> Path:
    """Resolve the reviewed policy in both source and packaged layouts."""
    return Path(__file__).resolve().parents[2] / "config/actual_status_rules.toml"


def load_status_policy(path: Path | None = None) -> StatusPolicy:
    policy_path = path or default_status_policy_path()
    try:
        payload = policy_path.read_bytes()
        decoded: dict[str, Any] = tomllib.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise SourceContractError("Agent Status policy could not be read") from exc
    raw_rules_value = decoded.get("status_rules")
    if not isinstance(raw_rules_value, list) or not raw_rules_value:
        raise SourceContractError("Agent Status policy must define status_rules")
    raw_rules = cast(list[object], raw_rules_value)
    categories: dict[str, str] = {}
    allowed = {"Productive", "Auxiliary", "Break", "Lunch", "Unavailable", "Logged Off"}
    for index, raw_rule in enumerate(raw_rules, 1):
        if not isinstance(raw_rule, dict):
            raise SourceContractError(f"Agent Status policy rule {index} is not a table")
        rule = cast(dict[object, object], raw_rule)
        label = rule.get("status")
        category = rule.get("attendance_category")
        if not isinstance(label, str) or not isinstance(category, str) or category not in allowed:
            raise SourceContractError(f"Agent Status policy rule {index} is invalid")
        normalized = _normalized_status(label)
        if not normalized or normalized in categories:
            raise SourceContractError(f"Agent Status policy rule {index} is duplicate or blank")
        categories[normalized] = category
    fingerprint = hashlib.sha256(b"agent-status-policy-v1\0" + payload).hexdigest()
    return StatusPolicy(categories, fingerprint)


def _fingerprint(path: Path) -> _Fingerprint:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return _Fingerprint(stat.st_size, stat.st_mtime_ns, digest.hexdigest())


def _version_fingerprint(version: SourceVersion) -> _Fingerprint:
    return _Fingerprint(version.file_size, version.mtime_ns, version.content_sha256)


def _clean(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _normalize_id(value: object) -> str | None:
    text = _clean(value)
    if text is None or text.upper() in _INVALID_IDS:
        return None
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def _parse_date(value: object) -> date | None:
    text = _clean(value)
    if text is None:
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _parse_datetime(value: object) -> datetime | None:
    text = _clean(value)
    if text is None:
        return None
    for pattern in (
        None,
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ):
        try:
            return (
                datetime.fromisoformat(text)
                if pattern is None
                else datetime.strptime(text, pattern)
            )
        except ValueError:
            continue
    return None


def _duration_seconds(value: object) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    parts = text.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + round(float(parts[2]))
        if len(parts) == 2:
            return int(parts[0]) * 3600 + round(float(parts[1])) * 60
        return round(float(text))
    except ValueError:
        return None


def _normalized_status(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _fallback_status(value: str | None) -> str:
    text = (value or "").upper().strip()
    if text == "LOGGED OFF":
        return "Logged Off"
    if any(token in text for token in ("LUNCH", "MEAL", "REPAS", "DÉJEUNER", "DEJEUNER")):
        return "Lunch"
    if "BREAK" in text or text in {"PAUSE ECRAN", "PAUSE ÉCRAN"}:
        return "Break"
    if text == "UNAVAILABLE":
        return "Unavailable"
    productive = ("AVAILABLE", "INBOUND", "OUTBOUND", "CALL SETUP", "RINGBACK", "HOLD", "WRAPUP")
    return "Productive" if any(token in text for token in productive) else "Auxiliary"


def _headers(path: Path, required: set[str], label: str) -> list[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            raw_headers = next(csv.reader(handle), None)
            headers = [] if raw_headers is None else [str(value) for value in raw_headers]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SourceContractError(f"{label} could not be read as UTF-8 CSV") from exc
    missing = sorted(required - set(headers))
    if missing:
        raise SourceContractError(f"{label} missing columns: {', '.join(missing)}")
    return headers


def _filename_fallback(path: Path) -> date | None:
    values = [
        datetime.strptime(value, "%Y-%m-%d").date() for value in _FILENAME_DATE.findall(path.name)
    ]
    return min(values) if values and min(values) == max(values) else None


def _lilo_contract(path: Path) -> tuple[str | None, date | None]:
    headers = _headers(path, LILO_REQUIRED_HEADERS, "LILO")
    normalized = {re.sub(r"[^A-Z0-9]+", "", header.upper()): header for header in headers}
    date_field = next(
        (
            normalized[key]
            for key in ("BUSINESSDATE", "EXTRACTDATE", "REPORTDATE", "DATE")
            if key in normalized
        ),
        None,
    )
    return date_field, _filename_fallback(path)


def _iter_lilo(
    path: Path,
    scope: AgentScope,
    *,
    date_field: str | None,
    fallback_date: date | None,
) -> Iterator[tuple[LiloRow | None, Literal["outside", "invalid"] | None]]:
    _headers(path, LILO_REQUIRED_HEADERS, "LILO")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for source_row, row in enumerate(reader, 2):
                source_agent_id = _normalize_id(row.get("[Agent ID]"))
                agent_name = _clean(row.get("[Agent]"))
                first = _parse_datetime(row.get("[First Log-on Time]"))
                raw_last = _parse_datetime(row.get("[Last Log-off Time]"))
                extract_date = (
                    (_parse_date(row.get(date_field)) if date_field else None)
                    or (first.date() if first else None)
                    or (raw_last.date() if raw_last else None)
                    or fallback_date
                )
                if extract_date is None:
                    yield None, "invalid"
                    continue
                resolution = scope.resolve(source_agent_id, agent_name, extract_date)
                if resolution is None:
                    yield None, "outside"
                    continue
                last = raw_last
                adjusted = False
                if first is not None and last is not None and last < first:
                    last += timedelta(days=1)
                    adjusted = True
                yield (
                    LiloRow(
                        source_row,
                        extract_date,
                        source_agent_id,
                        resolution.canonical_client_id,
                        agent_name,
                        first,
                        raw_last,
                        last,
                        adjusted,
                        resolution.match,
                    ),
                    None,
                )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SourceContractError("LILO could not be read as UTF-8 CSV") from exc


def _iter_status(
    path: Path,
    scope: AgentScope,
    policy: StatusPolicy,
) -> Iterator[tuple[AgentStatusRow | None, Literal["outside", "invalid"] | None]]:
    _headers(path, STATUS_REQUIRED_HEADERS, "Agent Status")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for source_row, row in enumerate(reader, 2):
                start = _parse_datetime(row.get("[Status Start Date and Time]"))
                seconds = _duration_seconds(row.get("[Status Duration]"))
                end = (
                    start + timedelta(seconds=seconds)
                    if start is not None and seconds is not None
                    else None
                )
                if start is None or end is None or end <= start or seconds is None:
                    yield None, "invalid"
                    continue
                source_agent_id = _normalize_id(row.get("[Agent ID]"))
                agent_name = _clean(row.get("[Agent]"))
                resolution = scope.resolve(source_agent_id, agent_name, start.date())
                if resolution is None:
                    yield None, "outside"
                    continue
                serial = _clean(row.get("[Serial Number]"))
                if serial is None:
                    material = repr(sorted((str(key), value) for key, value in row.items()))
                    serial = hashlib.sha256(material.encode("utf-8")).hexdigest()
                status = _clean(row.get("[Status]"))
                yield (
                    AgentStatusRow(
                        source_row,
                        serial,
                        start.date(),
                        source_agent_id,
                        resolution.canonical_client_id,
                        agent_name,
                        status,
                        policy.classify(status),
                        start,
                        end,
                        seconds,
                        _clean(row.get("[Queue]")),
                        resolution.match,
                    ),
                    None,
                )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SourceContractError("Agent Status could not be read as UTF-8 CSV") from exc


def preflight_actual_source(
    path: Path,
    *,
    source_key: str,
    kind: ActualKind,
    roster: FteSnapshot,
    status_policy: StatusPolicy | None = None,
) -> ActualSourcePlan:
    before = _fingerprint(path)
    scope = AgentScope.from_snapshot(roster)
    date_field: str | None = None
    fallback_date: date | None = None
    policy_fingerprint = LILO_POLICY_FINGERPRINT
    if kind == "lilo":
        date_field, fallback_date = _lilo_contract(path)
        records: Iterator[tuple[LiloRow | AgentStatusRow | None, str | None]] = _iter_lilo(
            path, scope, date_field=date_field, fallback_date=fallback_date
        )
        adapter_version = LILO_ADAPTER_VERSION
    else:
        if status_policy is None:
            raise SourceContractError("Agent Status policy is required")
        _headers(path, STATUS_REQUIRED_HEADERS, "Agent Status")
        records = _iter_status(path, scope, status_policy)
        adapter_version = STATUS_ADAPTER_VERSION
        policy_fingerprint = status_policy.fingerprint

    accepted = scoped_out = rejected = unmapped_status_rows = 0
    date_from: date | None = None
    date_to: date | None = None
    for row, reason in records:
        if reason == "outside":
            scoped_out += 1
        elif reason == "invalid":
            rejected += 1
        elif row is not None:
            accepted += 1
            if (
                kind == "agent_status"
                and isinstance(row, AgentStatusRow)
                and status_policy is not None
                and _normalized_status(row.status) not in status_policy.categories
            ):
                unmapped_status_rows += 1
            date_from = row.extract_date if date_from is None else min(date_from, row.extract_date)
            date_to = row.extract_date if date_to is None else max(date_to, row.extract_date)
    if _fingerprint(path) != before:
        raise SourceContractError(f"source changed while it was being parsed: {path.name}")

    findings: list[QualityIssue] = []
    prefix = "AGENT_STATUS" if kind == "agent_status" else "LILO"
    if rejected:
        findings.append(
            QualityIssue(
                f"{prefix}_REJECTED_ROWS",
                "warning",
                f"{rejected} rows were skipped because required row-level evidence was invalid.",
                source_key,
            )
        )
    if scoped_out:
        findings.append(
            QualityIssue(
                f"{prefix}_OUTSIDE_ROSTER_ROWS",
                "info",
                f"{scoped_out} rows were outside the effective roster scope and were skipped.",
                source_key,
            )
        )
    if unmapped_status_rows:
        findings.append(
            QualityIssue(
                "AGENT_STATUS_UNMAPPED_LABELS",
                "warning",
                f"{unmapped_status_rows} rows used the conservative fallback status classifier.",
                source_key,
            )
        )
    version = SourceVersion(
        kind,
        source_key,
        before.file_size,
        before.mtime_ns,
        before.content_sha256,
        adapter_version,
        policy_fingerprint,
        accepted,
    )
    return ActualSourcePlan(
        path,
        source_key,
        kind,
        version,
        tuple(findings),
        accepted,
        scoped_out,
        rejected,
        date_from,
        date_to,
        date_field,
        fallback_date,
    )


def stage_actual_plans(
    store: RefreshStore, generation_id: int, plans: Sequence[ActualSourcePlan]
) -> None:
    for plan in plans:
        store.stage_source(generation_id, plan.version)
        store.record_quality_issues(generation_id, plan.findings)


def _require_evidence(
    connection: sqlite3.Connection, generation_id: int, plan: ActualSourcePlan
) -> None:
    row = connection.execute(
        """
        SELECT state, source_type, source_key, file_size, mtime_ns, content_sha256,
               adapter_version, policy_fingerprint, row_count
        FROM wfm_source_manifest
        WHERE generation_id = ? AND source_type = ? AND source_key = ?
        """,
        (generation_id, plan.version.source_type, plan.version.source_key),
    ).fetchone()
    if row is None or row[0] != "present" or SourceVersion(*row[1:]) != plan.version:
        raise ValueError(f"actual source evidence mismatch: {plan.source_key}")


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _publish_lilo(
    connection: sqlite3.Connection,
    generation_id: int,
    plan: ActualSourcePlan,
    scope: AgentScope,
) -> tuple[int, int, int]:
    batch: list[tuple[object, ...]] = []
    accepted = scoped_out = rejected = 0
    for row, reason in _iter_lilo(
        plan.path, scope, date_field=plan.date_field, fallback_date=plan.fallback_date
    ):
        if reason == "outside":
            scoped_out += 1
        elif reason == "invalid":
            rejected += 1
        elif row is not None:
            accepted += 1
            batch.append(
                (
                    generation_id,
                    plan.source_key,
                    row.source_row,
                    _iso(row.extract_date),
                    row.source_agent_id,
                    row.roster_client_id,
                    row.agent_name,
                    _iso(row.first_login),
                    _iso(row.raw_last_logout),
                    _iso(row.last_logout),
                    int(row.overnight_adjusted),
                    row.scope_match,
                )
            )
            if len(batch) >= _BATCH_SIZE:
                connection.executemany(_INSERT_LILO, batch)
                batch.clear()
    if batch:
        connection.executemany(_INSERT_LILO, batch)
    return accepted, scoped_out, rejected


def _publish_status(
    connection: sqlite3.Connection,
    generation_id: int,
    plan: ActualSourcePlan,
    scope: AgentScope,
    policy: StatusPolicy,
) -> tuple[int, int, int]:
    batch: list[tuple[object, ...]] = []
    accepted = scoped_out = rejected = 0
    for row, reason in _iter_status(plan.path, scope, policy):
        if reason == "outside":
            scoped_out += 1
        elif reason == "invalid":
            rejected += 1
        elif row is not None:
            accepted += 1
            batch.append(
                (
                    generation_id,
                    plan.source_key,
                    row.source_row,
                    row.serial_number,
                    _iso(row.extract_date),
                    row.source_agent_id,
                    row.roster_client_id,
                    row.agent_name,
                    row.status,
                    row.actual_category,
                    _iso(row.status_start),
                    _iso(row.status_end),
                    row.duration_seconds,
                    row.queue,
                    row.scope_match,
                )
            )
            if len(batch) >= _BATCH_SIZE:
                connection.executemany(_INSERT_STATUS, batch)
                batch.clear()
    if batch:
        connection.executemany(_INSERT_STATUS, batch)
    return accepted, scoped_out, rejected


def publish_actual_plans(
    connection: sqlite3.Connection,
    generation_id: int,
    plans: Sequence[ActualSourcePlan],
    *,
    roster: FteSnapshot,
    status_policy: StatusPolicy | None,
) -> None:
    scope = AgentScope.from_snapshot(roster)
    for plan in plans:
        _require_evidence(connection, generation_id, plan)
        expected_fingerprint = _version_fingerprint(plan.version)
        if _fingerprint(plan.path) != expected_fingerprint:
            raise SourceContractError(f"actual source changed before publication: {plan.path.name}")
        if plan.kind == "lilo":
            counts = _publish_lilo(connection, generation_id, plan, scope)
        else:
            if (
                status_policy is None
                or status_policy.fingerprint != plan.version.policy_fingerprint
            ):
                raise SourceContractError("Agent Status policy changed before publication")
            counts = _publish_status(connection, generation_id, plan, scope, status_policy)
        expected_counts = (plan.accepted_rows, plan.scoped_out_rows, plan.rejected_rows)
        if counts != expected_counts or _fingerprint(plan.path) != expected_fingerprint:
            raise SourceContractError(f"actual source changed during publication: {plan.path.name}")
