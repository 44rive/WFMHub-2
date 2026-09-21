"""Governed, read-only FTE and published-schedule source contracts.

The FTE workbook parser lazy-loads OpenPyXL, a reviewed pure-Python portable
dependency.  Importing this module and starting the host do not require it.
StartEndTimes parsing and all persistence use only the standard library.
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from wfmhub2_compat.refresh_store import QualityIssue, RefreshStore, SourceVersion

FTE_ADAPTER_VERSION = "fte-count-v2"
SCHEDULE_ADAPTER_VERSION = "start-end-times-v2"
FTE_POLICY_FINGERPRINT = "effective-roster-pto-away-v2"
SCHEDULE_POLICY_FINGERPRINT = "published-start-end-explicit-overnight-v2"

_MAX_XLSX_BYTES = 64 * 1024 * 1024
_MAX_SCHEDULE_BYTES = 128 * 1024 * 1024
_INVALID_IDS = {"", "-", "N/A", "NA", "NULL", "NONE"}
_INTERVAL = re.compile(
    r"(?P<start>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+[AP]M)"
    r"\s*-\s*"
    r"(?P<end>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+[AP]M)",
    re.IGNORECASE,
)

Severity = Literal["info", "warning", "error"]
ScheduleState = Literal["SHIFT", "OFF", "INVALID"]
ScopeMatch = Literal["id", "name", "none"]


class SourceContractError(ValueError):
    """A source does not satisfy the file-level governed contract."""


@dataclass(frozen=True)
class _FileFingerprint:
    file_size: int
    mtime_ns: int
    content_sha256: str


class _Worksheet(Protocol):
    title: str

    def iter_rows(
        self,
        *,
        min_row: int | None = None,
        values_only: bool = False,
    ) -> Iterable[tuple[Any, ...]]: ...


class _Workbook(Protocol):
    worksheets: Sequence[_Worksheet]
    sheetnames: Sequence[str]

    def close(self) -> None: ...


@dataclass(frozen=True)
class SourceFinding:
    code: str
    severity: Severity
    details: str
    source_key: str
    source_sheet: str | None = None
    source_row: int | None = None
    source_column: int | None = None


@dataclass(frozen=True)
class FteAgentRow:
    source_key: str
    source_sheet: str
    source_row: int
    client_id: str | None
    employment_status: str | None
    agent_name: str | None
    team_leader: str | None
    ops_manager: str | None
    lob: str | None
    market: str | None
    language: str | None
    location: str | None
    city: str | None
    fte: float | None
    end_date: date | None
    valid: bool
    validation_codes: tuple[str, ...]

    def eligible_on(self, business_date: date) -> bool:
        if not self.valid:
            return False
        if self.employment_status == "Active":
            return True
        return (
            self.employment_status == "Leaver"
            and self.end_date is not None
            and business_date <= self.end_date
        )


@dataclass(frozen=True)
class FteTimeOffRow:
    source_key: str
    source_sheet: str
    source_row: int
    source_kind: Literal["PTO", "AWAY"]
    client_id: str | None
    agent_name: str | None
    start_date: date | None
    end_date: date | None
    day_coverage: str | None
    start_time: time | None
    end_time: time | None
    absence_type: str | None
    record_status: str | None
    comment: str | None
    valid: bool
    validation_codes: tuple[str, ...]

    @property
    def overlay_eligible(self) -> bool:
        """Whether the register status is allowed into operational overlays."""
        if not self.valid:
            return False
        if self.source_kind == "PTO":
            return self.record_status == "APPROVED"
        return self.record_status in {"ACTIVE", "PLANNED", "CLOSED"}


@dataclass(frozen=True)
class FteSnapshot:
    source_key: str
    agents: tuple[FteAgentRow, ...]
    time_off: tuple[FteTimeOffRow, ...]
    findings: tuple[SourceFinding, ...]
    version: SourceVersion

    @property
    def row_count(self) -> int:
        return len(self.agents) + len(self.time_off)


@dataclass(frozen=True)
class ScopeResolution:
    roster_row: FteAgentRow
    canonical_client_id: str
    match: ScopeMatch


@dataclass(frozen=True)
class AgentScope:
    by_id: dict[str, FteAgentRow]
    unique_names: dict[str, FteAgentRow]

    @classmethod
    def from_snapshot(cls, snapshot: FteSnapshot) -> AgentScope:
        by_id = {
            row.client_id: row for row in snapshot.agents if row.valid and row.client_id is not None
        }
        grouped: dict[str, list[FteAgentRow]] = {}
        for row in snapshot.agents:
            key = _normalize_name(row.agent_name)
            if row.valid and key is not None:
                grouped.setdefault(key, []).append(row)
        unique_names = {key: rows[0] for key, rows in grouped.items() if len(rows) == 1}
        return cls(by_id, unique_names)

    def resolve(
        self,
        source_agent_id: str | None,
        agent_name: str | None,
        business_date: date,
    ) -> ScopeResolution | None:
        row = self.by_id.get(source_agent_id) if source_agent_id is not None else None
        match: ScopeMatch = "id"
        if row is None:
            name_key = _normalize_name(agent_name)
            row = self.unique_names.get(name_key) if name_key is not None else None
            match = "name"
        if row is None or not row.eligible_on(business_date):
            return None
        canonical_client_id = row.client_id if match == "id" else source_agent_id
        if canonical_client_id is None:
            return None
        return ScopeResolution(row, canonical_client_id, match)


@dataclass(frozen=True)
class ScheduleRow:
    source_key: str
    source_row: int
    source_column: int
    business_date: date
    source_agent_id: str | None
    roster_client_id: str | None
    agent_name: str | None
    raw_assignment: str
    assignment: str | None
    assignment_type: str | None
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    schedule_state: ScheduleState
    is_overnight: bool
    in_roster_scope: bool
    scope_match: ScopeMatch
    valid: bool
    validation_codes: tuple[str, ...]


@dataclass(frozen=True)
class ScheduleSnapshot:
    source_key: str
    date_from: date
    date_to: date
    shifts: tuple[ScheduleRow, ...]
    findings: tuple[SourceFinding, ...]
    scoped_out: int
    version: SourceVersion

    @property
    def row_count(self) -> int:
        return len(self.shifts)


@dataclass(frozen=True)
class SourceSnapshot:
    roster: FteSnapshot
    schedules: tuple[ScheduleSnapshot, ...]

    @property
    def findings(self) -> tuple[SourceFinding, ...]:
        return self.roster.findings + tuple(
            finding for schedule in self.schedules for finding in schedule.findings
        )

    @property
    def versions(self) -> tuple[SourceVersion, ...]:
        return (self.roster.version, *(schedule.version for schedule in self.schedules))


PublishCallback = Callable[[sqlite3.Connection, int], None]


def _required_text(value: str, label: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise SourceContractError(f"{label} must not be empty")
    return stripped


def _clean(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _normalize_header(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^A-Z0-9]+", "", text.upper())


def _normalize_name(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    decomposed = unicodedata.normalize("NFKD", text).casefold()
    plain = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(re.findall(r"[a-z0-9]+", plain)) or None


def _normalize_id(value: object, *, reject_placeholders: bool = True) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bool, int)):
        text = str(value)
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()
        if re.fullmatch(r"\d+\.0", text):
            text = text[:-2]
    if reject_placeholders and text.upper() in _INVALID_IDS:
        return None
    return text or None


def _date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(value)
    if text is None:
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _time(value: object) -> time | None:
    if isinstance(value, datetime):
        return value.time().replace(tzinfo=None)
    if isinstance(value, time):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = round(float(value) * 24 * 60 * 60)
        if 0 <= seconds < 24 * 60 * 60:
            return (datetime.min + timedelta(seconds=seconds)).time()
    text = _clean(value)
    if text is None:
        return None
    for pattern in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    return None


def _number(value: object) -> float | None:
    if _clean(value) is None:
        return None
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return None


def _fingerprint(path: Path) -> _FileFingerprint:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return _FileFingerprint(stat.st_size, stat.st_mtime_ns, digest.hexdigest())


def _bound_version(
    path: Path,
    before: _FileFingerprint,
    *,
    source_type: str,
    source_key: str,
    adapter_version: str,
    policy_fingerprint: str,
    row_count: int,
) -> SourceVersion:
    """Bind parsed rows to unchanged source bytes and filesystem identity."""
    after = _fingerprint(path)
    if after != before:
        raise SourceContractError(f"source changed while it was being parsed: {path.name}")
    return SourceVersion(
        source_type=source_type,
        source_key=source_key,
        file_size=before.file_size,
        mtime_ns=before.mtime_ns,
        content_sha256=before.content_sha256,
        adapter_version=adapter_version,
        policy_fingerprint=policy_fingerprint,
        row_count=row_count,
    )


def _load_workbook(path: Path) -> _Workbook:
    try:
        module = importlib.import_module("openpyxl")
    except ImportError as exc:
        raise SourceContractError(
            "FTE XLSX parsing requires the packaged pure-Python OpenPyXL capability"
        ) from exc
    loader = cast(Callable[..., object], cast(Any, module).load_workbook)
    workbook = loader(path, read_only=True, data_only=True, keep_links=False)
    return cast(_Workbook, workbook)


_FTE_ALIASES: dict[str, tuple[str, ...]] = {
    "client_id": ("CLIENTID", "AGENTID", "VERINTID", "DATASOURCEID", "DATASOURCEIDS"),
    "agent_name": ("NAME", "AGENTNAME", "AGENT", "EMPLOYEENAME", "FULLNAME"),
    "employment_status": ("STATUS", "EMPLOYMENTSTATUS", "AGENTSTATUS"),
    "team_leader": ("TEAMLEADER", "TEAMLEADERNAME", "TL"),
    "ops_manager": ("OPSMANAGER", "OPERATIONSMANAGER", "OPERATIONSMANAGERNAME"),
    "lob": ("LOB", "LINEOFBUSINESS"),
    "market": ("MARKET",),
    "language": ("LANGUAGE",),
    "location": ("LOCATION", "SITE"),
    "city": ("CITY",),
    "fte": ("FTE", "FTECOUNT"),
    "end_date": ("ENDDATEIFLEAVER", "ENDDATE", "LEAVERENDDATE"),
}
_ROSTER_TITLES = {
    "AGENT",
    "AGENTS",
    "AGENTLIST",
    "AGENTROSTER",
    "FTE",
    "FTECOUNT",
    "FTEAGENT",
    "FTEAGENTS",
    "HEADCOUNT",
    "ROSTER",
}


def _column_indexes(headers: Sequence[object]) -> tuple[dict[str, int], dict[str, list[int]]]:
    normalized: dict[str, list[int]] = {}
    for index, value in enumerate(headers):
        if _clean(value) is not None:
            normalized.setdefault(_normalize_header(value), []).append(index)
    indexes: dict[str, int] = {}
    duplicates: dict[str, list[int]] = {}
    for field, aliases in _FTE_ALIASES.items():
        matches = sorted({index for alias in aliases for index in normalized.get(alias, [])})
        if len(matches) == 1:
            indexes[field] = matches[0]
        elif len(matches) > 1:
            duplicates[field] = matches
    return indexes, duplicates


def _roster_tier(sheet_name: str, fields: set[str]) -> int:
    normalized = _normalize_header(sheet_name)
    if normalized in _ROSTER_TITLES:
        return 3
    if set(re.findall(r"[A-Z0-9]+", sheet_name.upper())) & {"ROSTER", "HEADCOUNT"}:
        return 2
    org = {"lob", "market", "language", "location", "city"}
    if (
        "employment_status" in fields
        and fields & {"team_leader", "ops_manager"}
        and len(fields & org) >= 2
    ):
        return 1
    return 0


def _find_roster(workbook: _Workbook, path: Path) -> tuple[_Worksheet, int, dict[str, int]]:
    candidates: list[tuple[int, _Worksheet, int, dict[str, int]]] = []
    ambiguous: list[str] = []
    for sheet in workbook.worksheets:
        for row_number, values in enumerate(sheet.iter_rows(values_only=True), 1):
            if row_number > 100:
                break
            indexes, duplicates = _column_indexes(values)
            fields = set(indexes) | set(duplicates)
            tier = _roster_tier(sheet.title, fields)
            if tier and {"client_id", "agent_name"} <= fields and duplicates:
                ambiguous.append(
                    f"{sheet.title!r} row {row_number} has multiple aliases for "
                    + ", ".join(sorted(duplicates))
                )
                break
            required = {"client_id", "agent_name", "employment_status"}
            if tier and required <= indexes.keys():
                candidates.append((tier, sheet, row_number, indexes))
                break
    if ambiguous:
        raise SourceContractError(
            "FTE workbook has ambiguous roster headers: " + "; ".join(ambiguous)
        )
    if not candidates:
        searched = ", ".join(workbook.sheetnames) or "(no worksheets)"
        raise SourceContractError(
            f"FTE roster was not found in {path.name}; searched {searched}. "
            "Expected Client ID, Status, and Name on an Agent/FTE/Roster sheet."
        )
    highest = max(candidate[0] for candidate in candidates)
    best = [candidate for candidate in candidates if candidate[0] == highest]
    if len(best) != 1:
        locations = ", ".join(f"{item[1].title!r} row {item[2]}" for item in best)
        raise SourceContractError(
            f"FTE workbook has multiple authoritative roster tables: {locations}"
        )
    _, sheet, header_row, indexes = best[0]
    return sheet, header_row, indexes


def _value(values: Sequence[object], indexes: dict[str, int], field: str) -> object | None:
    index = indexes.get(field)
    return values[index] if index is not None and index < len(values) else None


def _finding(
    code: str,
    severity: Severity,
    details: str,
    *,
    source_key: str,
    sheet: str | None = None,
    row: int | None = None,
    column: int | None = None,
) -> SourceFinding:
    return SourceFinding(code, severity, details, source_key, sheet, row, column)


def _parse_agents(
    sheet: _Worksheet,
    header_row: int,
    indexes: dict[str, int],
    source_key: str,
) -> tuple[list[FteAgentRow], list[SourceFinding]]:
    agents: list[FteAgentRow] = []
    findings: list[SourceFinding] = []
    for source_row, values in enumerate(
        sheet.iter_rows(min_row=header_row + 1, values_only=True), header_row + 1
    ):
        if not any(_clean(value) is not None for value in values):
            continue
        raw_client_id = _value(values, indexes, "client_id")
        client_id = _normalize_id(raw_client_id)
        agent_name = _clean(_value(values, indexes, "agent_name"))
        raw_status = _clean(_value(values, indexes, "employment_status"))
        status_key = " ".join((raw_status or "").upper().replace("_", " ").split())
        status = {"ACTIVE": "Active", "LEAVER": "Leaver"}.get(status_key)
        raw_end_date = _value(values, indexes, "end_date")
        end_date = _date(raw_end_date)
        raw_fte = _value(values, indexes, "fte")
        fte = _number(raw_fte)
        advisories: list[str] = []
        invalid: list[str] = []
        if client_id is None:
            advisories.append("BLANK_CLIENT_ID")
        elif not isinstance(raw_client_id, str):
            advisories.append("CLIENT_ID_NOT_TEXT")
        if agent_name is None:
            invalid.append("MISSING_AGENT_NAME")
        if status is None:
            invalid.append("UNKNOWN_EMPLOYMENT_STATUS")
        if status == "Leaver" and end_date is None:
            invalid.append("LEAVER_END_DATE_REQUIRED")
        if status == "Active" and end_date is not None:
            invalid.append("ACTIVE_END_DATE_NOT_ALLOWED")
        if _clean(raw_end_date) is not None and end_date is None:
            invalid.append("INVALID_END_DATE")
        if _clean(raw_fte) is not None and fte is None:
            invalid.append("INVALID_FTE")
        if fte is not None and fte < 0:
            invalid.append("NEGATIVE_FTE")
        validation_codes = (*advisories, *invalid)
        row = FteAgentRow(
            source_key=source_key,
            source_sheet=sheet.title,
            source_row=source_row,
            client_id=client_id,
            employment_status=status or raw_status,
            agent_name=agent_name,
            team_leader=_clean(_value(values, indexes, "team_leader")),
            ops_manager=_clean(_value(values, indexes, "ops_manager")),
            lob=_clean(_value(values, indexes, "lob")),
            market=_clean(_value(values, indexes, "market")),
            language=_clean(_value(values, indexes, "language")),
            location=_clean(_value(values, indexes, "location")),
            city=_clean(_value(values, indexes, "city")),
            fte=fte,
            end_date=end_date,
            valid=not invalid,
            validation_codes=validation_codes,
        )
        agents.append(row)
        for code in validation_codes:
            findings.append(
                _finding(
                    code,
                    "warning",
                    f"Roster row {source_row} requires review for {code}",
                    source_key=source_key,
                    sheet=sheet.title,
                    row=source_row,
                )
            )
        if _clean(raw_fte) is None:
            findings.append(
                _finding(
                    "MISSING_FTE",
                    "warning",
                    f"Roster row {source_row} has unknown FTE",
                    source_key=source_key,
                    sheet=sheet.title,
                    row=source_row,
                )
            )

    counts = Counter(row.client_id for row in agents if row.client_id is not None)
    duplicate_ids = {client_id for client_id, count in counts.items() if count > 1}
    if duplicate_ids:
        winners: dict[str, int] = {}
        for client_id in duplicate_ids:
            candidates = [row for row in agents if row.client_id == client_id and row.valid]
            if candidates:
                winner = max(
                    candidates,
                    key=lambda row: (
                        row.employment_status == "Active",
                        row.end_date or date.min,
                        row.source_row,
                    ),
                )
                winners[client_id] = winner.source_row
        revised: list[FteAgentRow] = []
        for row in agents:
            if row.client_id in duplicate_ids:
                revised.append(
                    replace(
                        row,
                        valid=row.valid and winners.get(row.client_id) == row.source_row,
                        validation_codes=(*row.validation_codes, "DUPLICATE_CLIENT_ID"),
                    )
                )
                findings.append(
                    _finding(
                        "DUPLICATE_CLIENT_ID",
                        "warning",
                        "Client ID appears more than once; the Active/latest eligible row wins",
                        source_key=source_key,
                        sheet=sheet.title,
                        row=row.source_row,
                    )
                )
            else:
                revised.append(row)
        agents = revised
    if not agents:
        raise SourceContractError(f"FTE roster on sheet {sheet.title!r} has no populated rows")
    return agents, findings


def _find_register(workbook: _Workbook, names: set[str], label: str) -> _Worksheet | None:
    matches = [sheet for sheet in workbook.worksheets if _normalize_header(sheet.title) in names]
    if len(matches) > 1:
        raise SourceContractError(
            f"FTE workbook contains multiple {label} sheets: "
            + ", ".join(repr(sheet.title) for sheet in matches)
        )
    return matches[0] if matches else None


def _register_header(
    sheet: _Worksheet, required: set[str], label: str
) -> tuple[int, dict[str, int]]:
    for row_number, values in enumerate(sheet.iter_rows(values_only=True), 1):
        if row_number > 25:
            break
        indexes = {
            _normalize_header(value): index
            for index, value in enumerate(values)
            if _clean(value) is not None
        }
        if required <= indexes.keys():
            return row_number, indexes
    raise SourceContractError(
        f"FTE {label} sheet {sheet.title!r} is missing required template headers"
    )


def _parse_registers(
    workbook: _Workbook,
    source_key: str,
    roster_ids: set[str],
) -> tuple[list[FteTimeOffRow], list[SourceFinding]]:
    rows: list[FteTimeOffRow] = []
    findings: list[SourceFinding] = []
    configurations: tuple[tuple[Literal["PTO", "AWAY"], set[str], set[str]], ...] = (
        (
            "PTO",
            {"PTO", "PTOS"},
            {
                "CLIENTID",
                "STARTDATE",
                "ENDDATE",
                "DAYCOVERAGE",
                "STARTTIME",
                "ENDTIME",
                "PTOTYPE",
                "APPROVALSTATUS",
            },
        ),
        (
            "AWAY",
            {"AWAY", "AWAYPEOPLE", "LONGABSENCE", "LONGABSENCES"},
            {"CLIENTID", "STARTDATE", "ENDDATE", "AWAYTYPE", "CASESTATUS"},
        ),
    )
    for kind, sheet_names, required in configurations:
        sheet = _find_register(workbook, sheet_names, kind)
        if sheet is None:
            continue
        header_row, indexes = _register_header(sheet, required, kind)
        for source_row, values in enumerate(
            sheet.iter_rows(min_row=header_row + 1, values_only=True), header_row + 1
        ):
            if not any(_clean(value) is not None for value in values):
                continue

            raw_client_id = _value(values, indexes, "CLIENTID")
            client_id = _normalize_id(raw_client_id)
            start_date = _date(_value(values, indexes, "STARTDATE"))
            raw_end_date = _value(values, indexes, "ENDDATE")
            end_date = _date(raw_end_date)
            advisories: list[str] = []
            errors: list[str] = []
            if client_id is None:
                errors.append("BLANK_CLIENT_ID")
            else:
                if not isinstance(raw_client_id, str):
                    advisories.append("CLIENT_ID_NOT_TEXT")
                if client_id not in roster_ids:
                    errors.append("TIME_OFF_CLIENT_NOT_IN_ROSTER")
            if start_date is None:
                errors.append("INVALID_START_DATE")
            if end_date is not None and start_date is not None and end_date < start_date:
                errors.append("END_DATE_BEFORE_START")
            if _clean(raw_end_date) is not None and end_date is None:
                errors.append("INVALID_END_DATE")
            if kind == "PTO":
                coverage_text = " ".join(
                    str(_value(values, indexes, "DAYCOVERAGE") or "")
                    .strip()
                    .upper()
                    .replace("_", " ")
                    .split()
                )
                coverage = {"FULL DAY": "FULL_DAY", "PARTIAL DAY": "PARTIAL_DAY"}.get(coverage_text)
                start_time = _time(_value(values, indexes, "STARTTIME"))
                end_time = _time(_value(values, indexes, "ENDTIME"))
                absence_type = _clean(_value(values, indexes, "PTOTYPE"))
                status = (_clean(_value(values, indexes, "APPROVALSTATUS")) or "").upper() or None
                if end_date is None and "INVALID_END_DATE" not in errors:
                    errors.append("INVALID_END_DATE")
                if coverage is None:
                    errors.append("INVALID_DAY_COVERAGE")
                if coverage == "PARTIAL_DAY":
                    if start_date is not None and end_date is not None and start_date != end_date:
                        errors.append("PARTIAL_PTO_MULTIPLE_DATES")
                    if start_time is None or end_time is None or end_time <= start_time:
                        errors.append("INVALID_PARTIAL_PTO_TIME")
                if absence_type is None:
                    errors.append("MISSING_PTO_TYPE")
                if status not in {"APPROVED", "PENDING", "CANCELLED"}:
                    errors.append("INVALID_PTO_STATUS")
            else:
                coverage = "FULL_DAY"
                start_time = None
                end_time = None
                absence_type = _clean(_value(values, indexes, "AWAYTYPE"))
                status = (_clean(_value(values, indexes, "CASESTATUS")) or "").upper() or None
                if absence_type is None:
                    errors.append("MISSING_AWAY_TYPE")
                if status not in {"ACTIVE", "PLANNED", "CLOSED", "CANCELLED"}:
                    errors.append("INVALID_AWAY_STATUS")
                if end_date is None and status != "ACTIVE":
                    errors.append("OPEN_END_ONLY_FOR_ACTIVE_AWAY")
            row = FteTimeOffRow(
                source_key=source_key,
                source_sheet=sheet.title,
                source_row=source_row,
                source_kind=kind,
                client_id=client_id,
                agent_name=_clean(_value(values, indexes, "NAME")),
                start_date=start_date,
                end_date=end_date,
                day_coverage=coverage,
                start_time=start_time if coverage == "PARTIAL_DAY" else None,
                end_time=end_time if coverage == "PARTIAL_DAY" else None,
                absence_type=absence_type,
                record_status=status,
                comment=_clean(_value(values, indexes, "COMMENT")),
                valid=not errors,
                validation_codes=(*advisories, *errors),
            )
            rows.append(row)
            for code in (*advisories, *errors):
                action = "requires review for" if code in advisories else "was quarantined for"
                findings.append(
                    _finding(
                        code,
                        "warning",
                        f"{kind} row {source_row} {action} {code}",
                        source_key=source_key,
                        sheet=sheet.title,
                        row=source_row,
                    )
                )
    return rows, findings


def parse_fte_workbook(path: Path, *, source_key: str) -> FteSnapshot:
    """Parse, but never modify, one governed FTE Count workbook."""
    source_key = _required_text(source_key, "source_key")
    if not path.is_file():
        raise SourceContractError(f"FTE source does not exist: {path}")
    if path.stat().st_size > _MAX_XLSX_BYTES:
        raise SourceContractError("FTE workbook exceeds the 64 MiB safety limit")
    fingerprint = _fingerprint(path)
    workbook = _load_workbook(path)
    try:
        sheet, header_row, indexes = _find_roster(workbook, path)
        agents, agent_findings = _parse_agents(sheet, header_row, indexes, source_key)
        valid_ids = {row.client_id for row in agents if row.valid and row.client_id is not None}
        time_off, register_findings = _parse_registers(workbook, source_key, valid_ids)
    finally:
        workbook.close()
    row_count = len(agents) + len(time_off)
    version = _bound_version(
        path,
        fingerprint,
        source_type="fte_roster",
        source_key=source_key,
        adapter_version=FTE_ADAPTER_VERSION,
        policy_fingerprint=FTE_POLICY_FINGERPRINT,
        row_count=row_count,
    )
    return FteSnapshot(
        source_key,
        tuple(agents),
        tuple(time_off),
        tuple(agent_findings + register_findings),
        version,
    )


def _parse_schedule_date(value: str) -> date | None:
    for pattern in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            continue
    return None


def _parse_interval(raw: str) -> tuple[str | None, datetime | None, datetime | None]:
    match = _INTERVAL.search(raw)
    if match is None:
        return raw or None, None, None
    assignment = raw[: match.start()].strip()
    if "|" in assignment:
        prefix, remainder = assignment.split("|", 1)
        if prefix.strip().startswith("."):
            assignment = remainder.strip()
    start = datetime.strptime(match.group("start").upper(), "%m/%d/%Y %I:%M %p")
    end = datetime.strptime(match.group("end").upper(), "%m/%d/%Y %I:%M %p")
    return assignment or None, start, end


def _assignment_type(raw: str, assignment: str | None) -> str:
    if raw.strip().upper() == "OFF":
        return "Off"
    text = (assignment or raw).upper()
    if any(token in text for token in ("SICKNESS", "VACATION", "LEAVE - UNPAID", "ANNUAL LEAVE")):
        return "Planned absence"
    if any(token in text for token in ("TRAINING", "TRAINER", "QUALITY MONITORING")):
        return "Non-phone planned"
    return "Work"


def parse_start_end_times(
    path: Path,
    *,
    source_key: str,
    roster: FteSnapshot,
) -> ScheduleSnapshot:
    """Normalize the wide published StartEndTimes TSV at its business-date grain.

    Explicit next-day end timestamps are accepted as overnight shifts.  A
    same-day end before the start is invalid; the parser never invents a day.
    """
    source_key = _required_text(source_key, "source_key")
    if not path.is_file():
        raise SourceContractError(f"StartEndTimes source does not exist: {path}")
    if path.stat().st_size > _MAX_SCHEDULE_BYTES:
        raise SourceContractError("StartEndTimes source exceeds the 128 MiB safety limit")
    fingerprint = _fingerprint(path)
    scope = AgentScope.from_snapshot(roster)
    rows: list[ScheduleRow] = []
    findings: list[SourceFinding] = []
    scoped_out = 0
    try:
        handle = path.open("r", encoding="cp1252", newline="")
    except UnicodeDecodeError as exc:
        raise SourceContractError("StartEndTimes is not valid Windows-1252 text") from exc
    with handle:
        reader = csv.reader(handle, delimiter="\t", strict=True)
        try:
            headers = next(reader)
        except StopIteration as exc:
            raise SourceContractError("StartEndTimes extract is empty") from exc
        headers = [
            value.strip().lstrip("\ufeff") if index == 0 else value.strip()
            for index, value in enumerate(headers)
        ]
        if len(headers) < 3 or headers[:2] != ["Name", "Data Source IDs"]:
            raise SourceContractError("StartEndTimes must begin with Name and Data Source IDs")
        date_columns: list[tuple[int, date]] = []
        blank_columns: list[int] = []
        for index, header in enumerate(headers[2:], 2):
            if not header:
                blank_columns.append(index)
                continue
            parsed_date = _parse_schedule_date(header)
            if parsed_date is None:
                raise SourceContractError(
                    f"StartEndTimes header column {index + 1} is not a business date"
                )
            date_columns.append((index, parsed_date))
        if not date_columns:
            raise SourceContractError("StartEndTimes contains no business-date columns")
        business_dates = [business_date for _, business_date in date_columns]
        if len(business_dates) != len(set(business_dates)):
            raise SourceContractError("StartEndTimes contains duplicate business-date columns")
        for source_row, values in enumerate(reader, 2):
            for index in blank_columns:
                if index < len(values) and _clean(values[index]) is not None:
                    raise SourceContractError(
                        f"StartEndTimes row {source_row}, column {index + 1} has data "
                        "without a header"
                    )
            name = _clean(values[0] if values else None)
            raw_id_value = values[1] if len(values) > 1 else None
            source_agent_id = _normalize_id(raw_id_value)
            raw_agent_id = _normalize_id(raw_id_value, reject_placeholders=False)
            if name is None and raw_agent_id is None:
                continue
            for offset, business_date in date_columns:
                raw = _clean(values[offset] if offset < len(values) else None)
                if raw is None:
                    continue
                source_column = offset + 1
                resolution = scope.resolve(source_agent_id, name, business_date)
                roster_client_id = (
                    resolution.canonical_client_id if resolution is not None else None
                )
                scope_match: ScopeMatch = resolution.match if resolution is not None else "none"
                in_scope = resolution is not None
                if not in_scope:
                    scoped_out += 1
                    findings.append(
                        _finding(
                            "SCHEDULE_OUTSIDE_EFFECTIVE_ROSTER",
                            "info",
                            "Schedule cell is outside the Active/datestamped-Leaver roster scope",
                            source_key=source_key,
                            row=source_row,
                            column=source_column,
                        )
                    )
                elif scope_match == "name" and source_agent_id is not None:
                    findings.append(
                        _finding(
                            "SCHEDULE_ID_NAME_FALLBACK",
                            "warning",
                            "Populated schedule ID did not match the roster; exact unique name "
                            "was used as an auditable scope crosswalk",
                            source_key=source_key,
                            row=source_row,
                            column=source_column,
                        )
                    )
                errors: list[str] = []
                is_off = raw.upper() == "OFF"
                if is_off:
                    assignment = "Off"
                    start = None
                    end = None
                    state: ScheduleState = "OFF"
                else:
                    assignment, start, end = _parse_interval(raw)
                    state = "SHIFT"
                    if start is None or end is None:
                        errors.append("MALFORMED_SHIFT_INTERVAL")
                    else:
                        if start.date() != business_date:
                            errors.append("SHIFT_START_DATE_MISMATCH")
                        if end <= start:
                            errors.append("SHIFT_END_NOT_AFTER_START")
                        if end.date() not in {business_date, business_date + timedelta(days=1)}:
                            errors.append("SHIFT_END_DATE_OUT_OF_RANGE")
                        if end - start > timedelta(hours=24):
                            errors.append("SHIFT_EXCEEDS_24_HOURS")
                    if errors:
                        state = "INVALID"
                row = ScheduleRow(
                    source_key=source_key,
                    source_row=source_row,
                    source_column=source_column,
                    business_date=business_date,
                    source_agent_id=raw_agent_id,
                    roster_client_id=roster_client_id,
                    agent_name=name,
                    raw_assignment=raw,
                    assignment=assignment,
                    assignment_type=_assignment_type(raw, assignment),
                    scheduled_start=start,
                    scheduled_end=end,
                    schedule_state=state,
                    is_overnight=bool(
                        state == "SHIFT"
                        and start is not None
                        and end is not None
                        and end.date() > start.date()
                    ),
                    in_roster_scope=in_scope,
                    scope_match=scope_match,
                    valid=not errors,
                    validation_codes=tuple(errors),
                )
                rows.append(row)
                for code in errors:
                    findings.append(
                        _finding(
                            code,
                            "error",
                            "StartEndTimes row "
                            f"{source_row}, column {source_column} violates {code}",
                            source_key=source_key,
                            row=source_row,
                            column=source_column,
                        )
                    )
    version = _bound_version(
        path,
        fingerprint,
        source_type="published_schedule",
        source_key=source_key,
        adapter_version=SCHEDULE_ADAPTER_VERSION,
        policy_fingerprint=SCHEDULE_POLICY_FINGERPRINT,
        row_count=len(rows),
    )
    return ScheduleSnapshot(
        source_key=source_key,
        date_from=min(business_dates),
        date_to=max(business_dates),
        shifts=tuple(rows),
        findings=tuple(findings),
        scoped_out=scoped_out,
        version=version,
    )


def stage_sources(store: RefreshStore, generation_id: int, snapshot: SourceSnapshot) -> None:
    """Stage the exact byte-bound versions carried by a parsed snapshot."""
    for version in snapshot.versions:
        store.stage_source(generation_id, version)


def stage_findings(store: RefreshStore, generation_id: int, snapshot: SourceSnapshot) -> None:
    """Persist parser findings before attempting generation activation."""
    issues: list[QualityIssue] = []
    for finding in snapshot.findings:
        location: list[str] = []
        if finding.source_sheet is not None:
            location.append(f"sheet={finding.source_sheet}")
        if finding.source_row is not None:
            location.append(f"row={finding.source_row}")
        if finding.source_column is not None:
            location.append(f"column={finding.source_column}")
        details = finding.details
        if location:
            details = f"{details} ({', '.join(location)})"
        issues.append(
            QualityIssue(
                issue_code=finding.code,
                severity=finding.severity,
                details=details,
                source_key=finding.source_key,
            )
        )
    store.record_quality_issues(generation_id, issues)


def _iso(value: date | datetime | time | None) -> str | None:
    return value.isoformat() if value is not None else None


def _require_source_evidence(
    connection: sqlite3.Connection,
    generation_id: int,
    snapshot: SourceSnapshot,
) -> None:
    for expected in snapshot.versions:
        row = connection.execute(
            """
            SELECT state, source_type, source_key, file_size, mtime_ns,
                   content_sha256, adapter_version, policy_fingerprint, row_count
            FROM wfm_source_manifest
            WHERE generation_id = ? AND source_type = ? AND source_key = ?
            """,
            (generation_id, expected.source_type, expected.source_key),
        ).fetchone()
        if row is None or row[0] != "present" or SourceVersion(*row[1:]) != expected:
            raise ValueError(
                "published snapshot is not bound to matching source evidence: "
                f"{expected.source_type}/{expected.source_key}"
            )


def publish_source_snapshot(
    connection: sqlite3.Connection,
    generation_id: int,
    snapshot: SourceSnapshot,
) -> None:
    """Write one full roster/schedule snapshot inside activation's transaction."""
    if any(finding.severity == "error" for finding in snapshot.findings):
        raise ValueError("source snapshot contains blocking quality findings")
    _require_source_evidence(connection, generation_id, snapshot)
    schedule_precedence = {
        version.source_key: (version.mtime_ns, version.source_key)
        for version in snapshot.versions
        if version.source_type == "published_schedule"
    }
    schedule_rows = [row for schedule in snapshot.schedules for row in schedule.shifts]
    scope = AgentScope.from_snapshot(snapshot.roster)
    canonical_agents = {
        row.client_id: row
        for row in snapshot.roster.agents
        if row.valid and row.client_id is not None
    }
    for schedule_row in schedule_rows:
        if not schedule_row.valid or not schedule_row.in_roster_scope:
            continue
        resolution = scope.resolve(
            schedule_row.source_agent_id,
            schedule_row.agent_name,
            schedule_row.business_date,
        )
        if resolution is None or resolution.canonical_client_id != schedule_row.roster_client_id:
            continue
        canonical_agents.setdefault(
            resolution.canonical_client_id,
            replace(resolution.roster_row, client_id=resolution.canonical_client_id),
        )
    canonical_schedule: dict[tuple[str, date], ScheduleRow] = {}
    for row in schedule_rows:
        if not row.valid or not row.in_roster_scope or row.roster_client_id is None:
            continue
        key = (row.roster_client_id, row.business_date)
        existing = canonical_schedule.get(key)
        row_rank = (*schedule_precedence[row.source_key], row.source_row, row.source_column)
        if existing is None:
            canonical_schedule[key] = row
            continue
        existing_rank = (
            *schedule_precedence[existing.source_key],
            existing.source_row,
            existing.source_column,
        )
        if row_rank > existing_rank:
            canonical_schedule[key] = row
    connection.executemany(
        """
        INSERT INTO wfm_raw_fte_agent (
            generation_id, source_key, source_sheet, source_row, client_id,
            employment_status, agent_name, team_leader, ops_manager, lob, market,
            language, location, city, fte, end_date, valid, validation_codes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                generation_id,
                row.source_key,
                row.source_sheet,
                row.source_row,
                row.client_id,
                row.employment_status,
                row.agent_name,
                row.team_leader,
                row.ops_manager,
                row.lob,
                row.market,
                row.language,
                row.location,
                row.city,
                row.fte,
                _iso(row.end_date),
                int(row.valid),
                json.dumps(row.validation_codes),
            )
            for row in snapshot.roster.agents
        ],
    )
    connection.executemany(
        """
        INSERT INTO wfm_agent_roster (
            generation_id, client_id, employment_status, agent_name, team_leader,
            ops_manager, lob, market, language, location, city, fte,
            eligible_through, source_key, source_sheet, source_row
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                generation_id,
                row.client_id,
                row.employment_status,
                row.agent_name,
                row.team_leader,
                row.ops_manager,
                row.lob,
                row.market,
                row.language,
                row.location,
                row.city,
                row.fte,
                _iso(row.end_date),
                row.source_key,
                row.source_sheet,
                row.source_row,
            )
            for row in sorted(canonical_agents.values(), key=lambda item: item.client_id or "")
        ],
    )
    connection.executemany(
        """
        INSERT INTO wfm_raw_fte_time_off (
            generation_id, source_key, source_sheet, source_row, source_kind,
            client_id, agent_name, start_date, end_date, day_coverage, start_time,
            end_time, absence_type, record_status, comment, valid, validation_codes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                generation_id,
                row.source_key,
                row.source_sheet,
                row.source_row,
                row.source_kind,
                row.client_id,
                row.agent_name,
                _iso(row.start_date),
                _iso(row.end_date),
                row.day_coverage,
                _iso(row.start_time),
                _iso(row.end_time),
                row.absence_type,
                row.record_status,
                row.comment,
                int(row.valid),
                json.dumps(row.validation_codes),
            )
            for row in snapshot.roster.time_off
        ],
    )
    connection.executemany(
        """
        INSERT INTO wfm_time_off (
            generation_id, source_kind, client_id, start_date, end_date,
            day_coverage, start_time, end_time, absence_type, record_status,
            overlay_eligible, comment, source_key, source_sheet, source_row
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                generation_id,
                row.source_kind,
                row.client_id,
                _iso(row.start_date),
                _iso(row.end_date),
                row.day_coverage,
                _iso(row.start_time),
                _iso(row.end_time),
                row.absence_type,
                row.record_status,
                int(row.overlay_eligible),
                row.comment,
                row.source_key,
                row.source_sheet,
                row.source_row,
            )
            for row in snapshot.roster.time_off
            if row.valid
        ],
    )
    connection.executemany(
        """
        INSERT INTO wfm_raw_schedule_shift (
            generation_id, source_key, source_row, source_column, business_date,
            source_agent_id, roster_client_id, agent_name, raw_assignment,
            assignment, assignment_type, scheduled_start, scheduled_end,
            schedule_state, is_overnight, in_roster_scope, scope_match, valid,
            validation_codes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                generation_id,
                row.source_key,
                row.source_row,
                row.source_column,
                _iso(row.business_date),
                row.source_agent_id,
                row.roster_client_id,
                row.agent_name,
                row.raw_assignment,
                row.assignment,
                row.assignment_type,
                _iso(row.scheduled_start),
                _iso(row.scheduled_end),
                row.schedule_state,
                int(row.is_overnight),
                int(row.in_roster_scope),
                row.scope_match,
                int(row.valid),
                json.dumps(row.validation_codes),
            )
            for row in schedule_rows
        ],
    )
    connection.executemany(
        """
        INSERT INTO wfm_schedule_shift (
            generation_id, business_date, roster_client_id, source_agent_id,
            agent_name, assignment, assignment_type, scheduled_start,
            scheduled_end, schedule_state, is_overnight, scope_match, source_key,
            source_row, source_column
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                generation_id,
                _iso(row.business_date),
                row.roster_client_id,
                row.source_agent_id,
                row.agent_name,
                row.assignment,
                row.assignment_type,
                _iso(row.scheduled_start),
                _iso(row.scheduled_end),
                row.schedule_state,
                int(row.is_overnight),
                row.scope_match,
                row.source_key,
                row.source_row,
                row.source_column,
            )
            for row in sorted(
                canonical_schedule.values(),
                key=lambda item: (
                    item.business_date,
                    item.roster_client_id or "",
                    item.source_key,
                ),
            )
        ],
    )


def make_source_publish(snapshot: SourceSnapshot) -> PublishCallback:
    """Return the callback intended for ``RefreshStore.activate_generation``."""

    def publish(connection: sqlite3.Connection, generation_id: int) -> None:
        publish_source_snapshot(connection, generation_id, snapshot)

    return publish
