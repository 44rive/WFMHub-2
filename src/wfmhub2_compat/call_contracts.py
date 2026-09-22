"""Streaming Call-by-Call evidence and additive service-demand facts.

The legacy Storm export can be very large, so validation retains only bounded
counts while optionally staging generation-keyed Bronze rows in the same
single parse. Calls enter through either of two explicit lanes: an effective
roster identity or a reviewed queue mapping. This preserves
abandoned/unassigned queue demand without widening employee scope.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import tomllib
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from wfmhub2_compat.catalog import load_queue_mapping_snapshot
from wfmhub2_compat.refresh_store import QualityIssue, RefreshStore, SourceVersion
from wfmhub2_compat.source_contracts import AgentScope, FteSnapshot, SourceContractError

CALL_REQUIRED_HEADERS = {
    "Call Date/Time",
    "Call End Date/Time",
    "Call ID",
    "Call Reference Number",
    "Agent ID",
    "Agent",
    "Talk Time",
    "Hold Time",
    "Total Wrap Time",
}
CALL_ADAPTER_VERSION = "storm-call-by-call-v1"
_BATCH_SIZE = 5000
_INVALID_IDS = {"", "-", "N/A", "NA", "NULL", "NONE"}


@dataclass(frozen=True)
class _Fingerprint:
    file_size: int
    mtime_ns: int
    content_sha256: str


@dataclass(frozen=True)
class ServiceMapping:
    service_scope: str | None
    comparison_scope: str | None
    designation: str | None
    status: Literal["MAPPED", "FALLBACK_LOB", "UNMAPPED"]


@dataclass(frozen=True)
class CallPolicy:
    mapping_sha256: str
    rules_sha256: str
    fingerprint: str
    target_seconds: int
    short_abandon_seconds: int
    queue_rows: dict[tuple[str, str], ServiceMapping]
    scope_rollups: dict[str, str]

    def map_actual(
        self,
        source_system: str,
        queue: str | None,
        business_partner: str | None,
        lob: str | None,
    ) -> ServiceMapping:
        for value in (queue, business_partner):
            value_key = _catalog_key(value)
            for system in (source_system, "STORM", "ANY"):
                result = self.queue_rows.get((_catalog_key(system), value_key))
                if value_key and result is not None:
                    return result
        if lob is not None and lob.strip():
            value = lob.strip()
            return ServiceMapping(value, value, None, "FALLBACK_LOB")
        return ServiceMapping(None, None, None, "UNMAPPED")


@dataclass(frozen=True)
class CallRow:
    source_row: int
    call_key: str
    interaction_key: str
    business_date: date
    call_start: datetime
    call_end: datetime | None
    communication_type: str | None
    call_direction: str | None
    business_partner_id: str | None
    lob: str | None
    service: str | None
    call_reference_number: str | None
    call_id: str | None
    call_progress: str | None
    queue_wait_seconds: int | None
    queue_id: str | None
    queue: str | None
    call_treatment: str | None
    source_agent_id: str | None
    roster_client_id: str | None
    agent_name: str | None
    clearing_party: str | None
    talk_seconds: int | None
    hold_seconds: int | None
    wrap_seconds: int | None
    completion_code: str | None
    transferred: bool | None
    shared_call_reference: str | None
    ringing_seconds: int | None
    internal: bool | None
    direct: bool | None
    language: str | None
    post_call_survey_mode: str | None
    pcs_status: str | None
    raw_payload_json: str
    service_scope: str | None
    comparison_scope: str | None
    designation: str | None
    mapping_status: str
    agent_eligible: bool
    service_eligible: bool
    scope_match: str
    validation_codes: str


@dataclass(frozen=True)
class CallSourcePlan:
    path: Path
    source_key: str
    version: SourceVersion
    findings: tuple[QualityIssue, ...]
    accepted_rows: int
    service_rows: int
    scoped_out_rows: int
    rejected_rows: int
    unmapped_rows: int
    degraded_rows: int
    date_from: date | None
    date_to: date | None
    bronze_generation_id: int | None = None


@dataclass
class _ServiceBucket:
    offered: int = 0
    answered: int = 0
    abandoned: int = 0
    short_abandoned: int = 0
    abandoned_within_target: int = 0
    answered_within_target: int = 0
    talk_seconds: int = 0
    hold_seconds: int = 0
    wrap_seconds: int = 0
    handled_seconds: int = 0
    call_legs: int = 0
    transferred_legs: int = 0
    source_files: set[str] = field(default_factory=lambda: set[str]())


def default_queue_mapping_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config/queue_mapping.csv"


def default_service_rules_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config/service_rules.toml"


def _catalog_key(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def load_call_policy(
    mapping_path: Path | None = None,
    rules_path: Path | None = None,
) -> CallPolicy:
    mapping = load_queue_mapping_snapshot(mapping_path or default_queue_mapping_path())
    selected_rules = rules_path or default_service_rules_path()
    try:
        rules_bytes = selected_rules.read_bytes()
        payload = tomllib.loads(rules_bytes.decode("utf-8"))
        service = payload["service"]
        target = int(service["target_seconds"])
        short = int(service["short_abandon_seconds"])
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise SourceContractError("service rules could not be read") from exc
    if target <= 0 or short < 0 or short >= target:
        raise SourceContractError("service rules require 0 <= short abandon < target seconds")

    rollups = {
        _catalog_key(row.source_value): row.service_scope
        for row in mapping.mappings
        if row.mapping_type == "scope_rollup"
    }
    queue_rows: dict[tuple[str, str], ServiceMapping] = {}
    for row in mapping.mappings:
        if row.mapping_type != "queue":
            continue
        comparison = rollups.get(_catalog_key(row.service_scope), row.service_scope)
        queue_rows[(_catalog_key(row.source_system), _catalog_key(row.source_value))] = (
            ServiceMapping(row.service_scope, comparison, row.designation or None, "MAPPED")
        )
    rules_sha256 = hashlib.sha256(rules_bytes).hexdigest()
    fingerprint = hashlib.sha256(
        (
            "call-policy-v1|"
            f"{mapping.sha256}|{rules_sha256}|roster-or-mapped-queue|inbound-entry-leg"
        ).encode()
    ).hexdigest()
    return CallPolicy(
        mapping.sha256,
        rules_sha256,
        fingerprint,
        target,
        short,
        queue_rows,
        rollups,
    )


def _fingerprint(path: Path) -> _Fingerprint:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return _Fingerprint(stat.st_size, stat.st_mtime_ns, digest.hexdigest())


def _metadata_matches(path: Path, expected: _Fingerprint) -> bool:
    """Detect movement without rereading a large file solely to hash it again."""
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns) == (expected.file_size, expected.mtime_ns)


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


def _boolean(value: object) -> bool | None:
    text = str(value or "").strip().upper()
    if text in {"1", "TRUE", "YES", "Y"}:
        return True
    if text in {"0", "FALSE", "NO", "N"}:
        return False
    return None


def _headers(path: Path) -> dict[str, str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            raw = next(csv.reader(handle, strict=True), None)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SourceContractError("Call by Call could not be read as UTF-8 CSV") from exc
    headers = [] if raw is None else [str(value) for value in raw]
    mapping: dict[str, str] = {}
    for header in headers:
        normalized = header.strip().strip("[]")
        if normalized in mapping:
            raise SourceContractError(f"Call by Call duplicates column: {normalized}")
        mapping[normalized] = header
    missing = sorted(CALL_REQUIRED_HEADERS - set(mapping))
    if missing:
        raise SourceContractError(f"Call by Call missing columns: {', '.join(missing)}")
    return mapping


def _value(row: dict[str, str], headers: dict[str, str], name: str) -> str | None:
    return row.get(headers.get(name, ""))


def _iter_calls(
    path: Path,
    scope: AgentScope,
    policy: CallPolicy,
) -> Iterator[tuple[CallRow | None, Literal["outside", "invalid"] | None]]:
    headers = _headers(path)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            for source_row, raw_row in enumerate(reader, 2):

                def get(name: str, row: dict[str, str] = raw_row) -> str | None:
                    return _value(row, headers, name)

                start = _parse_datetime(_value(raw_row, headers, "Call Date/Time"))
                if start is None:
                    yield None, "invalid"
                    continue
                source_agent_id = _normalize_id(_value(raw_row, headers, "Agent ID"))
                agent_name = _clean(_value(raw_row, headers, "Agent"))
                resolution = scope.resolve(source_agent_id, agent_name, start.date())
                queue = _clean(_value(raw_row, headers, "Queue"))
                business_partner = _clean(_value(raw_row, headers, "BusinessPartnerID"))
                lob = _clean(_value(raw_row, headers, "LineOfBusiness"))
                # The reviewed legacy Call-by-Call contract admits service only
                # through an exact queue mapping.  Business partner and LOB are
                # retained as evidence but never widen service scope.
                mapped = policy.map_actual("STORM", queue, None, None)
                if resolution is None and mapped.status != "MAPPED":
                    yield None, "outside"
                    continue

                end = _parse_datetime(get("Call End Date/Time"))
                if end is not None and end < start:
                    end += timedelta(days=1)
                call_reference = _clean(get("Call Reference Number"))
                call_id = _clean(get("Call ID"))
                direction = _clean(get("Call Direction"))
                clearing_party = _clean(get("Clearing Party"))
                shared_reference = _clean(get("Shared Call Reference"))
                identity_agent_id = (
                    resolution.canonical_client_id if resolution is not None else source_agent_id
                )
                raw_payload = json.dumps(
                    {str(key): value for key, value in raw_row.items()},
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                key_parts: list[object] = [
                    call_reference,
                    call_id,
                    direction,
                    identity_agent_id,
                    start,
                    clearing_party,
                ]
                if not call_reference and not call_id:
                    key_parts.append(raw_payload)
                call_key = hashlib.sha256(
                    "|".join(str(value or "") for value in key_parts).encode("utf-8")
                ).hexdigest()
                interaction_key = shared_reference or call_reference or call_id or call_key
                agent_eligible = resolution is not None
                service_eligible = mapped.status == "MAPPED" and (direction or "").upper() == "I"
                scope_match = resolution.match if resolution is not None else "queue"
                raw_durations = {
                    "queue_wait_seconds": get("Total Queue Wait Time"),
                    "talk_seconds": get("Talk Time"),
                    "hold_seconds": get("Hold Time"),
                    "wrap_seconds": get("Total Wrap Time"),
                    "ringing_seconds": get("Ringing Duration"),
                }
                durations: dict[str, int | None] = {}
                quality_codes: set[str] = set()
                for field_name, raw_value in raw_durations.items():
                    parsed = _duration_seconds(raw_value)
                    if parsed is not None and parsed < 0:
                        parsed = None
                    if _clean(raw_value) is not None and parsed is None:
                        quality_codes.add("INVALID_DURATION")
                    durations[field_name] = parsed
                if queue is None:
                    quality_codes.add("MISSING_QUEUE")
                if (direction or "").upper() not in {"I", "O"}:
                    quality_codes.add("MISSING_CALL_DIRECTION")
                if service_eligible and durations["queue_wait_seconds"] is None:
                    quality_codes.add("MISSING_RESPONSE_CLOCK")
                yield (
                    CallRow(
                        source_row,
                        call_key,
                        interaction_key,
                        start.date(),
                        start,
                        end,
                        _clean(get("Communication Type")),
                        direction,
                        business_partner,
                        lob,
                        _clean(get("Service")),
                        call_reference,
                        call_id,
                        _clean(get("CallProgress")),
                        durations["queue_wait_seconds"],
                        _normalize_id(get("Queue ID")),
                        queue,
                        _clean(get("Call Treatment")),
                        source_agent_id,
                        resolution.canonical_client_id if resolution is not None else None,
                        agent_name,
                        clearing_party,
                        durations["talk_seconds"],
                        durations["hold_seconds"],
                        durations["wrap_seconds"],
                        _clean(get("Call Completion Code")),
                        _boolean(get("Transferred?")),
                        shared_reference,
                        durations["ringing_seconds"],
                        _boolean(get("Internal")),
                        _boolean(get("Direct")),
                        _clean(get("Language")),
                        _clean(get("PostCallSurveyMode")),
                        _clean(get("PCSStatus")),
                        raw_payload,
                        mapped.service_scope,
                        mapped.comparison_scope,
                        mapped.designation,
                        mapped.status,
                        agent_eligible,
                        service_eligible,
                        scope_match,
                        json.dumps(sorted(quality_codes), separators=(",", ":")),
                    ),
                    None,
                )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SourceContractError("Call by Call could not be read as UTF-8 CSV") from exc


def preflight_call_source(
    path: Path,
    *,
    source_key: str,
    roster: FteSnapshot,
    policy: CallPolicy,
    stage_database: Path | None = None,
    generation_id: int | None = None,
    initial_fingerprint: tuple[int, int, str] | None = None,
) -> CallSourcePlan:
    if (stage_database is None) != (generation_id is None):
        raise ValueError("stage_database and generation_id must be provided together")
    before = (
        _Fingerprint(*initial_fingerprint)
        if initial_fingerprint is not None
        else _fingerprint(path)
    )
    if not _metadata_matches(path, before):
        raise SourceContractError(f"source changed before parsing: {path.name}")
    accepted = service_rows = scoped_out = rejected = unmapped = degraded = 0
    date_from: date | None = None
    date_to: date | None = None
    scope = AgentScope.from_snapshot(roster)
    connection: sqlite3.Connection | None = None
    batch: list[tuple[object, ...]] = []
    try:
        if stage_database is not None:
            connection = sqlite3.connect(stage_database, timeout=30)
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
        for row, reason in _iter_calls(path, scope, policy):
            if reason == "outside":
                scoped_out += 1
            elif reason == "invalid":
                rejected += 1
            elif row is not None:
                accepted += 1
                service_rows += int(row.service_eligible)
                unmapped += int(row.mapping_status != "MAPPED")
                degraded += int(row.validation_codes != "[]")
                date_from = (
                    row.business_date if date_from is None else min(date_from, row.business_date)
                )
                date_to = row.business_date if date_to is None else max(date_to, row.business_date)
                if connection is not None and generation_id is not None:
                    batch.append(_raw_values(generation_id, source_key, row))
                    if len(batch) >= _BATCH_SIZE:
                        connection.executemany(_INSERT_RAW, batch)
                        batch.clear()
        if connection is not None and batch:
            connection.executemany(_INSERT_RAW, batch)
        if not _metadata_matches(path, before):
            raise SourceContractError(f"source changed while it was being parsed: {path.name}")
        if connection is not None:
            connection.commit()
    except BaseException:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()

    findings: list[QualityIssue] = []
    if rejected:
        findings.append(
            QualityIssue(
                "CALL_REJECTED_ROWS",
                "warning",
                f"{rejected} rows were skipped because Call Date/Time was invalid.",
                source_key,
            )
        )
    if scoped_out:
        findings.append(
            QualityIssue(
                "CALL_OUTSIDE_SCOPE_ROWS",
                "info",
                f"{scoped_out} rows matched neither the effective roster nor a reviewed queue.",
                source_key,
            )
        )
    if unmapped:
        findings.append(
            QualityIssue(
                "CALL_UNMAPPED_AGENT_ROWS",
                "info",
                f"{unmapped} roster-scoped rows had no reviewed queue mapping "
                "and are not service demand.",
                source_key,
            )
        )
    if degraded:
        findings.append(
            QualityIssue(
                "CALL_DEGRADED_ROWS",
                "warning",
                f"{degraded} admitted rows had missing service fields or invalid durations.",
                source_key,
            )
        )
    version = SourceVersion(
        "call_by_call",
        source_key,
        before.file_size,
        before.mtime_ns,
        before.content_sha256,
        CALL_ADAPTER_VERSION,
        policy.fingerprint,
        accepted,
    )
    return CallSourcePlan(
        path,
        source_key,
        version,
        tuple(findings),
        accepted,
        service_rows,
        scoped_out,
        rejected,
        unmapped,
        degraded,
        date_from,
        date_to,
    )


def stage_call_plans(
    store: RefreshStore,
    generation_id: int,
    plans: Sequence[CallSourcePlan],
) -> None:
    for plan in plans:
        store.stage_source(
            generation_id, plan.version, bronze_generation_id=plan.bronze_generation_id
        )
        store.record_quality_issues(generation_id, plan.findings)


_RAW_COLUMNS = (
    "generation_id",
    "source_key",
    "source_row",
    "call_key",
    "interaction_key",
    "business_date",
    "call_start",
    "call_end",
    "communication_type",
    "call_direction",
    "business_partner_id",
    "lob",
    "service",
    "call_reference_number",
    "call_id",
    "call_progress",
    "queue_wait_seconds",
    "queue_id",
    "queue",
    "call_treatment",
    "source_agent_id",
    "roster_client_id",
    "agent_name",
    "clearing_party",
    "talk_seconds",
    "hold_seconds",
    "wrap_seconds",
    "completion_code",
    "transferred",
    "shared_call_reference",
    "ringing_seconds",
    "internal",
    "direct",
    "language",
    "post_call_survey_mode",
    "pcs_status",
    "raw_payload_json",
    "service_scope",
    "comparison_scope",
    "designation",
    "mapping_status",
    "agent_eligible",
    "service_eligible",
    "scope_match",
    "validation_codes",
)
_INSERT_RAW = (
    f"INSERT INTO wfm_raw_call_leg ({', '.join(_RAW_COLUMNS)}) "
    f"VALUES ({', '.join('?' for _ in _RAW_COLUMNS)})"
)


def _raw_values(generation_id: int, source_key: str, row: CallRow) -> tuple[object, ...]:
    values: list[object] = [generation_id, source_key]
    for name in _RAW_COLUMNS[2:]:
        value = getattr(row, name)
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        elif isinstance(value, bool):
            value = int(value)
        values.append(value)
    return tuple(values)


def _require_evidence(
    connection: sqlite3.Connection,
    generation_id: int,
    plan: CallSourcePlan,
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
        raise ValueError(f"Call by Call source evidence mismatch: {plan.source_key}")


def _publish_raw_plan(
    connection: sqlite3.Connection,
    generation_id: int,
    plan: CallSourcePlan,
    scope: AgentScope,
    policy: CallPolicy,
) -> tuple[int, int, int, int]:
    batch: list[tuple[object, ...]] = []
    accepted = service_rows = scoped_out = rejected = 0
    for row, reason in _iter_calls(plan.path, scope, policy):
        if reason == "outside":
            scoped_out += 1
        elif reason == "invalid":
            rejected += 1
        elif row is not None:
            accepted += 1
            service_rows += int(row.service_eligible)
            batch.append(_raw_values(generation_id, plan.source_key, row))
            if len(batch) >= _BATCH_SIZE:
                connection.executemany(_INSERT_RAW, batch)
                batch.clear()
    if batch:
        connection.executemany(_INSERT_RAW, batch)
    return accepted, service_rows, scoped_out, rejected


def _publish_canonical(connection: sqlite3.Connection, generation_id: int) -> None:
    columns = ", ".join(_RAW_COLUMNS)
    selected = ", ".join(("? AS generation_id", *(f"ranked.{name}" for name in _RAW_COLUMNS[1:])))
    connection.execute(
        f"""
        INSERT INTO wfm_call_leg ({columns})
        SELECT {selected}
        FROM (
            SELECT raw.*,
                   row_number() OVER (
                       PARTITION BY raw.call_key
                       ORDER BY manifest.mtime_ns DESC, raw.source_key DESC, raw.source_row DESC
                   ) AS row_rank
            FROM wfm_source_manifest AS manifest
            JOIN wfm_raw_call_leg AS raw
              ON raw.generation_id = manifest.bronze_generation_id
             AND raw.source_key = manifest.source_key
            WHERE manifest.generation_id = ?
              AND manifest.source_type = 'call_by_call'
              AND manifest.state = 'present'
        ) AS ranked
        WHERE ranked.row_rank = 1
        """,
        (generation_id, generation_id),
    )


def _language(row: sqlite3.Row) -> str:
    suffix = str(row["service_scope"] or "").rsplit(" ", 1)[-1].upper()
    if suffix in {"FR", "VL", "NL", "DE", "EN"}:
        return suffix
    return str(row["language"] or "").strip().upper() or "(blank)"


def _publish_service_intervals(
    connection: sqlite3.Connection,
    generation_id: int,
    policy: CallPolicy,
) -> None:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT source_key, business_date, call_start, service_scope, comparison_scope,
               queue, designation, language, source_agent_id, talk_seconds, hold_seconds,
               wrap_seconds, queue_wait_seconds, ringing_seconds, transferred
        FROM wfm_call_leg
        WHERE generation_id = ? AND service_eligible = 1
        ORDER BY call_start, call_key
        """,
        (generation_id,),
    )
    buckets: dict[tuple[str, ...], _ServiceBucket] = {}
    for row in rows:
        call_start = datetime.fromisoformat(str(row["call_start"]))
        interval_start = call_start.replace(
            minute=(call_start.minute // 15) * 15,
            second=0,
            microsecond=0,
        )
        interval_end = interval_start + timedelta(minutes=15)
        key = (
            str(row["business_date"]),
            interval_start.isoformat(),
            interval_end.isoformat(),
            str(row["service_scope"]),
            str(row["comparison_scope"]),
            str(row["queue"] or "UNNAMED MAPPED QUEUE"),
            str(row["designation"] or ""),
            _language(row),
        )
        bucket = buckets.setdefault(key, _ServiceBucket())
        talk = int(row["talk_seconds"] or 0)
        hold = int(row["hold_seconds"] or 0)
        wrap = int(row["wrap_seconds"] or 0)
        answered = bool(row["source_agent_id"]) or talk + hold + wrap > 0
        wait = row["queue_wait_seconds"]
        response = int(wait) + int(row["ringing_seconds"] or 0) if wait is not None else None
        bucket.offered += 1
        bucket.answered += int(answered)
        bucket.abandoned += int(not answered)
        bucket.short_abandoned += int(
            not answered and response is not None and response < policy.short_abandon_seconds
        )
        bucket.abandoned_within_target += int(
            not answered
            and response is not None
            and policy.short_abandon_seconds <= response < policy.target_seconds
        )
        bucket.answered_within_target += int(
            answered and response is not None and response < policy.target_seconds
        )
        bucket.talk_seconds += talk
        bucket.hold_seconds += hold
        bucket.wrap_seconds += wrap
        bucket.handled_seconds = bucket.talk_seconds + bucket.hold_seconds + bucket.wrap_seconds
        bucket.call_legs += 1
        bucket.transferred_legs += int(bool(row["transferred"]))
        bucket.source_files.add(str(row["source_key"]))

    insert = """
        INSERT INTO wfm_service_interval (
            generation_id, business_date, interval_start, interval_end, source_system,
            service_scope, comparison_scope, queue, designation, language, offered,
            answered, abandoned, short_abandoned, abandoned_within_target,
            answered_within_target, talk_seconds, hold_seconds, wrap_seconds,
            handled_seconds, call_legs, transferred_legs, source_files_json,
            mapping_sha256, policy_fingerprint
        ) VALUES (
            ?, ?, ?, ?, 'CALL_BY_CALL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """
    values: list[tuple[object, ...]] = []
    for key, bucket in sorted(buckets.items()):
        values.append(
            (
                generation_id,
                *key,
                bucket.offered,
                bucket.answered,
                bucket.abandoned,
                bucket.short_abandoned,
                bucket.abandoned_within_target,
                bucket.answered_within_target,
                bucket.talk_seconds,
                bucket.hold_seconds,
                bucket.wrap_seconds,
                bucket.handled_seconds,
                bucket.call_legs,
                bucket.transferred_legs,
                json.dumps(sorted(bucket.source_files), separators=(",", ":")),
                policy.mapping_sha256,
                policy.fingerprint,
            )
        )
    if values:
        connection.executemany(insert, values)


def publish_call_plans(
    connection: sqlite3.Connection,
    generation_id: int,
    plans: Sequence[CallSourcePlan],
    *,
    roster: FteSnapshot,
    policy: CallPolicy | None,
    progress: Callable[[str, str, int, int], None] | None = None,
    rows_staged: bool = False,
) -> None:
    if not plans:
        return
    if policy is None:
        raise SourceContractError("Call by Call policy is required")
    scope = AgentScope.from_snapshot(roster)
    for index, plan in enumerate(plans, 1):
        if progress is not None:
            progress("publishing_calls", plan.source_key, index - 1, len(plans))
        _require_evidence(connection, generation_id, plan)
        if plan.version.policy_fingerprint != policy.fingerprint:
            raise SourceContractError("Call by Call policy changed before publication")
        expected = _Fingerprint(
            plan.version.file_size,
            plan.version.mtime_ns,
            plan.version.content_sha256,
        )
        if not _metadata_matches(plan.path, expected):
            raise SourceContractError(
                f"Call by Call source changed before publication: {plan.path.name}"
            )
        counts = (
            (
                plan.accepted_rows,
                plan.service_rows,
                plan.scoped_out_rows,
                plan.rejected_rows,
            )
            if rows_staged
            else _publish_raw_plan(connection, generation_id, plan, scope, policy)
        )
        if rows_staged and plan.bronze_generation_id is None:
            staged_counts = connection.execute(
                """
                SELECT count(*), COALESCE(sum(service_eligible), 0)
                FROM wfm_source_manifest AS manifest
                JOIN wfm_raw_call_leg AS raw
                  ON raw.generation_id = manifest.bronze_generation_id
                 AND raw.source_key = manifest.source_key
                WHERE manifest.generation_id = ?
                  AND manifest.source_type = 'call_by_call'
                  AND manifest.source_key = ? AND manifest.state = 'present'
                """,
                (generation_id, plan.source_key),
            ).fetchone()
            if staged_counts is None or tuple(map(int, staged_counts)) != (
                plan.accepted_rows,
                plan.service_rows,
            ):
                raise ValueError(f"staged Call by Call row count mismatch: {plan.source_key}")
        expected_counts = (
            plan.accepted_rows,
            plan.service_rows,
            plan.scoped_out_rows,
            plan.rejected_rows,
        )
        if counts != expected_counts or not _metadata_matches(plan.path, expected):
            raise SourceContractError(
                f"Call by Call source changed during publication: {plan.path.name}"
            )
    _publish_canonical(connection, generation_id)
    _publish_service_intervals(connection, generation_id, policy)
