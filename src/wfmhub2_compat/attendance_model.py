"""Governed attendance read model for the policy-compatible host.

Agent Status is primary when it covers enough elapsed scheduled work. LILO can
fill missing boundaries, but it never overrides explicit status gaps. Missing
evidence remains unknown. Exact gap fragments are retained for later review;
this module does not create or recommend attendance actions.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, cast

from wfmhub2_compat.source_contracts import SourceContractError

_MODEL_VERSION = b"attendance-read-model-v1"
GapType = Literal["LATE", "LOGGED_OFF", "UNAVAILABLE", "EARLY_LEAVE", "NO_SHOW"]


@dataclass(frozen=True)
class AttendancePolicy:
    late_tolerance_minutes: int
    status_gap_tolerance_minutes: int
    minimum_status_coverage: float
    fingerprint: str


@dataclass(frozen=True)
class _Interval:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class _StatusSegment:
    start: datetime
    end: datetime
    category: str
    status: str | None
    source_key: str
    source_row: int


@dataclass(frozen=True)
class _Gap:
    gap_type: GapType
    start: datetime
    end: datetime
    evidence_basis: str
    source_keys: tuple[str, ...]
    provisional: bool = False


def default_attendance_policy_path() -> Path:
    """Resolve the reviewed policy in source and packaged layouts."""
    return Path(__file__).resolve().parents[2] / "config/attendance_rules.toml"


def load_attendance_policy(path: Path | None = None) -> AttendancePolicy:
    policy_path = path or default_attendance_policy_path()
    try:
        payload = policy_path.read_bytes()
        decoded: dict[str, Any] = tomllib.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise SourceContractError("Attendance policy could not be read") from exc
    raw_value = decoded.get("attendance")
    if not isinstance(raw_value, dict):
        raise SourceContractError("Attendance policy must define [attendance]")
    raw = cast(dict[str, object], raw_value)
    late = raw.get("late_tolerance_minutes")
    gap = raw.get("status_gap_tolerance_minutes")
    coverage = raw.get("minimum_status_coverage")
    if (
        not isinstance(late, int)
        or isinstance(late, bool)
        or late < 0
        or not isinstance(gap, int)
        or isinstance(gap, bool)
        or gap < 0
        or not isinstance(coverage, (int, float))
        or isinstance(coverage, bool)
        or not 0 < float(coverage) <= 1
    ):
        raise SourceContractError("Attendance policy values are invalid")
    fingerprint = hashlib.sha256(_MODEL_VERSION + b"\0" + payload).hexdigest()
    return AttendancePolicy(late, gap, float(coverage), fingerprint)


def _dt(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _day(value: object) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _clock(value: object) -> time | None:
    if value is None:
        return None
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        return None


def _minutes(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def _merge(intervals: Iterable[_Interval]) -> list[_Interval]:
    ordered = sorted((item for item in intervals if item.end > item.start), key=lambda x: x.start)
    merged: list[_Interval] = []
    for item in ordered:
        if not merged or item.start > merged[-1].end:
            merged.append(item)
        elif item.end > merged[-1].end:
            merged[-1] = _Interval(merged[-1].start, item.end)
    return merged


def _subtract(start: datetime, end: datetime, blocked: Iterable[_Interval]) -> list[_Interval]:
    if end <= start:
        return []
    output: list[_Interval] = []
    cursor = start
    for item in _merge(
        _Interval(max(start, value.start), min(end, value.end))
        for value in blocked
        if value.end > start and value.start < end
    ):
        if item.start > cursor:
            output.append(_Interval(cursor, item.start))
        cursor = max(cursor, item.end)
    if cursor < end:
        output.append(_Interval(cursor, end))
    return output


def _intersections(interval: _Interval, allowed: Sequence[_Interval]) -> list[_Interval]:
    return [
        _Interval(max(interval.start, item.start), min(interval.end, item.end))
        for item in allowed
        if item.end > interval.start and item.start < interval.end
    ]


def _required_dates(start: datetime, end: datetime) -> set[date]:
    last = (end - timedelta(microseconds=1)).date()
    return {
        start.date() + timedelta(days=offset) for offset in range((last - start.date()).days + 1)
    }


def _time_off(
    connection: sqlite3.Connection,
    generation_id: int,
    client_id: str,
    start: datetime,
    end: datetime,
) -> tuple[list[_Interval], tuple[str, ...]]:
    rows = connection.execute(
        """
        SELECT start_date, COALESCE(end_date, start_date),
               day_coverage, start_time, end_time, source_key
        FROM wfm_time_off
        WHERE generation_id = ? AND client_id = ? AND overlay_eligible = 1
          AND start_date <= ? AND COALESCE(end_date, start_date) >= ?
        ORDER BY start_date, source_kind, source_key, source_row
        """,
        (generation_id, client_id, end.date().isoformat(), start.date().isoformat()),
    ).fetchall()
    intervals: list[_Interval] = []
    sources: set[str] = set()
    for raw_from, raw_to, coverage, raw_start_time, raw_end_time, source_key in rows:
        date_from = _day(raw_from)
        date_to = _day(raw_to)
        if date_from is None or date_to is None:
            continue
        sources.add(str(source_key))
        if str(coverage) == "PARTIAL_DAY":
            start_time = _clock(raw_start_time)
            end_time = _clock(raw_end_time)
            if start_time is not None and end_time is not None and end_time > start_time:
                intervals.append(
                    _Interval(
                        datetime.combine(date_from, start_time),
                        datetime.combine(date_from, end_time),
                    )
                )
            continue
        # A full-day register row belongs to the published shift's business
        # date, so it covers the complete shift even when that shift crosses
        # midnight. Calendar-day clipping would leave a false overnight gap.
        if date_from <= start.date() <= date_to:
            intervals.append(_Interval(start, end))
    clipped = [
        _Interval(max(start, item.start), min(end, item.end))
        for item in intervals
        if item.end > start and item.start < end
    ]
    return _merge(clipped), tuple(sorted(sources))


def _status_segments(
    connection: sqlite3.Connection,
    generation_id: int,
    client_id: str,
    start: datetime,
    end: datetime,
) -> tuple[list[_StatusSegment], tuple[str, ...]]:
    rows = connection.execute(
        """
        SELECT raw.source_key, raw.source_row, raw.status, raw.actual_category,
               raw.status_start, raw.status_end
        FROM wfm_source_manifest AS manifest
        JOIN wfm_raw_agent_status AS raw
          ON raw.generation_id = manifest.bronze_generation_id
         AND raw.source_key = manifest.source_key
        WHERE manifest.generation_id = ? AND manifest.source_type = 'agent_status'
          AND manifest.state = 'present' AND raw.roster_client_id = ?
          AND raw.status_start < ? AND raw.status_end > ?
        ORDER BY raw.status_start, raw.source_key, raw.source_row
        """,
        (generation_id, client_id, end.isoformat(), start.isoformat()),
    ).fetchall()
    parsed: list[_StatusSegment] = []
    sources: set[str] = set()
    for source_key, source_row, status, category, raw_start, raw_end in rows:
        item_start = _dt(raw_start)
        item_end = _dt(raw_end)
        if item_start is None or item_end is None or item_end <= item_start:
            continue
        sources.add(str(source_key))
        parsed.append(
            _StatusSegment(
                max(start, item_start),
                min(end, item_end),
                str(category),
                str(status) if status is not None else None,
                str(source_key),
                int(source_row),
            )
        )
    boundaries = sorted({start, end, *(row.start for row in parsed), *(row.end for row in parsed)})
    exclusive: list[_StatusSegment] = []
    for left, right in pairwise(boundaries):
        active = [row for row in parsed if row.start < right and row.end > left]
        if not active or right <= left:
            continue
        chosen = max(active, key=lambda row: (row.start, row.source_key, row.source_row))
        exclusive.append(
            _StatusSegment(
                left,
                right,
                chosen.category,
                chosen.status,
                chosen.source_key,
                chosen.source_row,
            )
        )
    return exclusive, tuple(sorted(sources))


def _lilo_evidence(
    connection: sqlite3.Connection,
    generation_id: int,
    client_id: str,
    start: datetime,
    end: datetime,
) -> tuple[datetime | None, datetime | None, bool, tuple[str, ...]]:
    required = _required_dates(start, end)
    placeholders = ",".join("?" for _ in required)
    rows = connection.execute(
        f"""
        SELECT raw.first_login, raw.last_logout, raw.source_key
        FROM wfm_source_manifest AS manifest
        JOIN wfm_raw_lilo AS raw
          ON raw.generation_id = manifest.bronze_generation_id
         AND raw.source_key = manifest.source_key
        WHERE manifest.generation_id = ? AND manifest.source_type = 'lilo'
          AND manifest.state = 'present' AND raw.roster_client_id = ?
          AND raw.extract_date IN ({placeholders})
        ORDER BY raw.source_key, raw.source_row
        """,
        (generation_id, client_id, *(value.isoformat() for value in sorted(required))),
    ).fetchall()
    first_candidates = sorted(
        value
        for raw_first, _, _ in rows
        if (value := _dt(raw_first)) is not None and start - timedelta(hours=4) <= value <= end
    )
    last_candidates = sorted(
        value
        for _, raw_last, _ in rows
        if (value := _dt(raw_last)) is not None and start <= value <= end + timedelta(hours=4)
    )
    return (
        first_candidates[0] if first_candidates else None,
        last_candidates[-1] if last_candidates else None,
        bool(rows),
        tuple(sorted({str(row[2]) for row in rows})),
    )


def _loaded_dates(connection: sqlite3.Connection, generation_id: int, table: str) -> set[date]:
    source_type = {
        "wfm_raw_agent_status": "agent_status",
        "wfm_raw_lilo": "lilo",
    }.get(table)
    if source_type is None:
        raise ValueError("unsupported evidence table")
    return {
        parsed
        for (value,) in connection.execute(
            f"""
            SELECT DISTINCT raw.extract_date FROM wfm_source_manifest AS manifest
            JOIN {table} AS raw
              ON raw.generation_id = manifest.bronze_generation_id
             AND raw.source_key = manifest.source_key
            WHERE manifest.generation_id = ? AND manifest.source_type = ?
              AND manifest.state = 'present'
            """,
            (generation_id, source_type),
        )
        if (parsed := _day(value)) is not None
    }


def _gap_key(agent_day_key: str, gap: _Gap) -> str:
    material = "|".join(
        (
            agent_day_key,
            gap.gap_type,
            gap.start.isoformat(),
            gap.end.isoformat(),
            gap.evidence_basis,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _json_sources(*values: Iterable[str]) -> str:
    return json.dumps(sorted({item for value in values for item in value}), separators=(",", ":"))


def _day_model(
    connection: sqlite3.Connection,
    generation_id: int,
    row: Mapping[str, object],
    *,
    policy: AttendancePolicy,
    as_of: datetime,
    status_loaded_dates: set[date],
    lilo_loaded_dates: set[date],
) -> tuple[tuple[object, ...], list[_Gap]]:
    business_date = str(row["business_date"])
    client_id = str(row["roster_client_id"])
    agent_day_key = f"{business_date.replace('-', '')}-{client_id}"
    start = _dt(row["scheduled_start"])
    end = _dt(row["scheduled_end"])
    assignment_type = str(row["assignment_type"])
    schedule_state = str(row["schedule_state"])
    scheduled_minutes = _minutes(start, end) if start is not None and end is not None else 0
    if schedule_state == "OFF" or assignment_type == "Off":
        return (
            (
                generation_id,
                agent_day_key,
                business_date,
                client_id,
                row["assignment"],
                assignment_type,
                row["scheduled_start"],
                row["scheduled_end"],
                scheduled_minutes,
                0,
                0,
                None,
                None,
                "NONE",
                0,
                0.0,
                0,
                0,
                0,
                0,
                0,
                "Off",
                "NOT_REQUIRED",
                0,
                0,
                0,
                as_of.isoformat(),
                row["source_key"],
                "[]",
                policy.fingerprint,
            ),
            [],
        )
    if start is None or end is None or end <= start:
        raise ValueError(f"canonical shift has invalid boundaries: {agent_day_key}")

    time_off, time_off_sources = _time_off(connection, generation_id, client_id, start, end)
    planned_absence = assignment_type == "Planned absence"
    if planned_absence:
        time_off = [_Interval(start, end)]
    planned_time_off_minutes = sum(_minutes(item.start, item.end) for item in time_off)
    working = _subtract(start, end, time_off)
    planned_work_minutes = sum(_minutes(item.start, item.end) for item in working)
    required_dates = _required_dates(start, end)
    status_source_loaded = required_dates <= status_loaded_dates
    lilo_source_loaded = required_dates <= lilo_loaded_dates
    lilo_first, lilo_last, lilo_row_present, lilo_sources = _lilo_evidence(
        connection, generation_id, client_id, start, end
    )
    evidence_end = min(end, as_of) if as_of > start else start
    gross_status, status_sources = _status_segments(
        connection, generation_id, client_id, start, evidence_end
    )
    status_segments: list[_StatusSegment] = []
    for item in gross_status:
        for overlap in _intersections(_Interval(item.start, item.end), working):
            status_segments.append(
                _StatusSegment(
                    overlap.start,
                    overlap.end,
                    item.category,
                    item.status,
                    item.source_key,
                    item.source_row,
                )
            )
    status_covered_minutes = sum(_minutes(item.start, item.end) for item in status_segments)
    elapsed_work_minutes = sum(
        _minutes(item.start, min(item.end, as_of))
        for item in working
        if item.start < as_of and min(item.end, as_of) > item.start
    )
    coverage_ratio = status_covered_minutes / elapsed_work_minutes if elapsed_work_minutes else 0.0
    status_is_primary = bool(gross_status) and coverage_ratio >= policy.minimum_status_coverage
    status_presence = [item for item in status_segments if item.category != "Logged Off"]
    status_first = min((item.start for item in status_presence), default=None)
    status_last = max((item.end for item in status_presence), default=None)
    bounded_lilo_first = lilo_first if lilo_first is not None and lilo_first <= as_of else None
    bounded_lilo_last = min(lilo_last, as_of) if lilo_last is not None else None
    if status_is_primary and status_first is not None:
        actual_first = status_first
    else:
        actual_first = min(
            (value for value in (bounded_lilo_first, status_first) if value is not None),
            default=None,
        )
    if status_is_primary and status_last is not None:
        actual_last = status_last
    else:
        actual_last = max(
            (value for value in (bounded_lilo_last, status_last) if value is not None),
            default=None,
        )
    evidence_parts: list[str] = []
    if lilo_row_present:
        evidence_parts.append("LILO")
    if gross_status:
        evidence_parts.append("AGENT_STATUS")
    actual_evidence = "+".join(evidence_parts) or "NONE"

    shift_not_started = as_of < start
    shift_in_progress = start <= as_of < end
    shift_complete = as_of >= end
    raw_late = _minutes(start, actual_first) if actual_first is not None else 0
    usable_pair = bool(
        actual_first is not None
        and actual_last is not None
        and actual_last >= actual_first
        and actual_last > start
        and actual_first < end
    )
    late_intervals = (
        [
            part
            for segment in working
            for part in _intersections(_Interval(start, min(actual_first, end)), [segment])
        ]
        if usable_pair and actual_first is not None and actual_first > start
        else []
    )
    early_intervals = (
        [
            part
            for segment in working
            for part in _intersections(_Interval(max(actual_last, start), end), [segment])
        ]
        if usable_pair and actual_last is not None and shift_complete and end > actual_last
        else []
    )
    late_minutes = sum(_minutes(item.start, item.end) for item in late_intervals)
    early_minutes = sum(_minutes(item.start, item.end) for item in early_intervals)
    if late_minutes <= policy.late_tolerance_minutes:
        late_minutes = 0
        late_intervals = []
    if early_minutes <= policy.late_tolerance_minutes:
        early_minutes = 0
        early_intervals = []

    blank_lilo_row = bool(
        lilo_source_loaded and lilo_row_present and lilo_first is None and lilo_last is None
    )
    status_proves_disconnected = bool(
        status_segments and not status_presence and coverage_ratio >= policy.minimum_status_coverage
    )
    no_show_intervals = (
        working
        if (blank_lilo_row or status_proves_disconnected) and not planned_absence and shift_complete
        else []
    )
    no_show_minutes = sum(_minutes(item.start, item.end) for item in no_show_intervals)

    gaps: list[_Gap] = []
    evidence_sources = tuple(sorted({*status_sources, *lilo_sources}))
    for item in no_show_intervals:
        gaps.append(_Gap("NO_SHOW", item.start, item.end, actual_evidence, evidence_sources))
    for item in late_intervals:
        gaps.append(
            _Gap(
                "LATE",
                item.start,
                item.end,
                actual_evidence,
                evidence_sources,
                shift_in_progress,
            )
        )
    for item in early_intervals:
        gaps.append(_Gap("EARLY_LEAVE", item.start, item.end, actual_evidence, evidence_sources))
    if actual_first is not None and actual_last is not None and actual_last > actual_first:
        category_gaps: tuple[tuple[str, GapType], ...] = (
            ("Logged Off", "LOGGED_OFF"),
            ("Unavailable", "UNAVAILABLE"),
        )
        for category, gap_type in category_gaps:
            matching = _merge(
                _Interval(item.start, item.end)
                for item in gross_status
                if item.category == category
            )
            for item in matching:
                clipped = _Interval(max(item.start, actual_first), min(item.end, actual_last))
                if clipped.end <= clipped.start:
                    continue
                for work_part in _intersections(clipped, working):
                    if (
                        _minutes(work_part.start, work_part.end)
                        > policy.status_gap_tolerance_minutes
                    ):
                        gap_sources = tuple(
                            sorted(
                                {
                                    segment.source_key
                                    for segment in gross_status
                                    if segment.category == category
                                    and segment.start < work_part.end
                                    and segment.end > work_part.start
                                }
                            )
                        )
                        gaps.append(
                            _Gap(
                                gap_type,
                                work_part.start,
                                work_part.end,
                                "AGENT_STATUS",
                                gap_sources,
                                shift_in_progress,
                            )
                        )

    full_time_off = bool(scheduled_minutes and planned_time_off_minutes >= scheduled_minutes)
    if planned_absence or full_time_off:
        result = "Planned absence"
        evidence_state = "NOT_REQUIRED"
        gaps = []
        late_minutes = early_minutes = no_show_minutes = 0
    elif shift_not_started:
        result = "Not started"
        evidence_state = "NOT_STARTED"
    elif shift_in_progress and late_minutes:
        result = "Late - shift in progress"
        evidence_state = "PROVISIONAL"
    elif (
        shift_in_progress
        and actual_first is None
        and elapsed_work_minutes > policy.late_tolerance_minutes
        and (blank_lilo_row or status_proves_disconnected)
    ):
        result = "Not seen - shift in progress"
        evidence_state = "PROVISIONAL"
    elif shift_in_progress:
        result = "Shift in progress"
        evidence_state = "PROVISIONAL"
    elif not status_source_loaded and not lilo_source_loaded:
        result = "Data not loaded"
        evidence_state = "UNKNOWN"
    elif no_show_minutes:
        result = "No show - partial time off" if planned_time_off_minutes else "No show"
        evidence_state = "COMPLETE"
    elif actual_first is None and actual_last is None:
        result = "Missing actual evidence"
        evidence_state = "UNKNOWN"
    elif actual_first is None or actual_last is None:
        result = "Incomplete actual evidence"
        evidence_state = "UNKNOWN"
    elif not usable_pair:
        result = "No schedule overlap"
        evidence_state = "UNKNOWN"
    elif late_minutes and early_minutes:
        result = "Late + early leave"
        evidence_state = "COMPLETE"
    elif late_minutes:
        result = "Late"
        evidence_state = "COMPLETE"
    elif early_minutes:
        result = "Early leave"
        evidence_state = "COMPLETE"
    else:
        result = "Present - partial time off" if planned_time_off_minutes else "Present"
        evidence_state = "COMPLETE"
    source_keys_json = _json_sources(
        (str(row["source_key"]),), status_sources, lilo_sources, time_off_sources
    )
    daily = (
        generation_id,
        agent_day_key,
        business_date,
        client_id,
        row["assignment"],
        assignment_type,
        start.isoformat(),
        end.isoformat(),
        scheduled_minutes,
        planned_work_minutes,
        planned_time_off_minutes,
        actual_first.isoformat() if actual_first is not None else None,
        actual_last.isoformat() if actual_last is not None else None,
        actual_evidence,
        status_covered_minutes,
        coverage_ratio,
        int(status_is_primary),
        raw_late,
        late_minutes,
        early_minutes,
        no_show_minutes,
        result,
        evidence_state,
        int(status_source_loaded),
        int(lilo_source_loaded),
        int(lilo_row_present),
        as_of.isoformat(),
        row["source_key"],
        source_keys_json,
        policy.fingerprint,
    )
    return daily, gaps


_INSERT_DAY = """
INSERT INTO wfm_attendance_agent_day (
    generation_id, agent_day_key, business_date, roster_client_id, assignment,
    assignment_type, scheduled_start, scheduled_end, scheduled_minutes,
    planned_work_minutes, planned_time_off_minutes, actual_first_seen,
    actual_last_seen, actual_evidence, status_covered_minutes,
    status_coverage_ratio, status_is_primary, raw_late_minutes, late_minutes,
    early_leave_minutes, no_show_minutes, attendance_result, evidence_state,
    status_source_loaded, lilo_source_loaded, lilo_row_present, evaluation_as_of,
    schedule_source_key, source_keys_json, policy_fingerprint
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def build_attendance_model(
    connection: sqlite3.Connection,
    generation_id: int,
    *,
    policy: AttendancePolicy,
    as_of: datetime | None = None,
) -> tuple[int, int]:
    """Build daily attendance and exact gaps inside generation activation."""
    evaluation_time = (as_of or datetime.now()).replace(microsecond=0)
    status_loaded_dates = _loaded_dates(connection, generation_id, "wfm_raw_agent_status")
    lilo_loaded_dates = _loaded_dates(connection, generation_id, "wfm_raw_lilo")
    previous_row_factory = connection.row_factory
    connection.row_factory = sqlite3.Row
    try:
        shifts = [
            dict(row)
            for row in connection.execute(
                """
                SELECT business_date, roster_client_id, assignment, assignment_type,
                       scheduled_start, scheduled_end, schedule_state, source_key
                FROM wfm_schedule_shift
                WHERE generation_id = ?
                ORDER BY business_date, roster_client_id
                """,
                (generation_id,),
            )
        ]
    finally:
        connection.row_factory = previous_row_factory
    day_rows: list[tuple[object, ...]] = []
    gap_rows: list[tuple[object, ...]] = []
    for shift in shifts:
        day_row, gaps = _day_model(
            connection,
            generation_id,
            cast(Mapping[str, object], shift),
            policy=policy,
            as_of=evaluation_time,
            status_loaded_dates=status_loaded_dates,
            lilo_loaded_dates=lilo_loaded_dates,
        )
        day_rows.append(day_row)
        agent_day_key = str(day_row[1])
        business_date = str(day_row[2])
        client_id = str(day_row[3])
        for gap in gaps:
            gap_rows.append(
                (
                    generation_id,
                    _gap_key(agent_day_key, gap),
                    agent_day_key,
                    business_date,
                    client_id,
                    gap.gap_type,
                    gap.start.isoformat(),
                    gap.end.isoformat(),
                    _minutes(gap.start, gap.end),
                    gap.evidence_basis,
                    json.dumps(gap.source_keys, separators=(",", ":")),
                    int(gap.provisional),
                    policy.fingerprint,
                )
            )
    if day_rows:
        connection.executemany(_INSERT_DAY, day_rows)
    if gap_rows:
        connection.executemany(
            """
            INSERT INTO wfm_attendance_gap (
                generation_id, gap_key, agent_day_key, business_date,
                roster_client_id, gap_type, gap_start, gap_end, gap_minutes,
                evidence_basis, source_keys_json, is_provisional,
                policy_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            gap_rows,
        )
    return len(day_rows), len(gap_rows)
