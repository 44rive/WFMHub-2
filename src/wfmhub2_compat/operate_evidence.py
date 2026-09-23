"""Privacy-bounded, active-cut evidence for the read-only Operate workspace."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from wfmhub2_compat.rta_refresh import (
    RefreshFailedError,
    catalog_fingerprint,
    resolve_source_root,
)

_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_MAX_QUERY_CHARS = 1024
_MAX_SCOPE_LABEL_CHARS = 160
_MAX_SCOPE_OPTIONS = 128
# A 25-hour DST fall-back day can contain 100 quarter-hours. Leave a small
# bounded margin for source-local business-day conventions crossing midnight.
_MAX_INTERVALS = 104


class OperateQueryError(ValueError):
    """The request contains an invalid date or scope selection."""


class OperateReadError(RuntimeError):
    """The committed evidence cannot be returned within the bounded contract."""


def parse_operate_query(query: str) -> tuple[date, tuple[str, str] | None]:
    """Require one calendar date and either both exact scope keys or neither."""
    if len(query) > _MAX_QUERY_CHARS:
        raise OperateQueryError("invalid operate evidence query")
    try:
        fields = parse_qs(query, keep_blank_values=True, max_num_fields=3)
    except ValueError as exc:
        raise OperateQueryError("invalid operate evidence query") from exc
    if set(fields) - {"date", "serviceScope", "comparisonScope"}:
        raise OperateQueryError("invalid operate evidence query")
    raw_dates = fields.get("date", [])
    if len(raw_dates) != 1 or _DATE_PATTERN.fullmatch(raw_dates[0]) is None:
        raise OperateQueryError("date must be exactly YYYY-MM-DD")
    try:
        business_date = date.fromisoformat(raw_dates[0])
    except ValueError as exc:
        raise OperateQueryError("date must be a real calendar day") from exc
    service = fields.get("serviceScope", [])
    comparison = fields.get("comparisonScope", [])
    if not service and not comparison:
        return business_date, None
    if len(service) != 1 or len(comparison) != 1:
        raise OperateQueryError("service and comparison scopes must be selected together")
    if any(
        not value or len(value) > _MAX_SCOPE_LABEL_CHARS or any(ord(char) < 32 for char in value)
        for value in (service[0], comparison[0])
    ):
        raise OperateQueryError("invalid scope selection")
    return business_date, (service[0], comparison[0])


def _catalog_for_home(home: Path) -> str | None:
    try:
        root = resolve_source_root(home)
        if not root.path.is_dir():
            return None
        return catalog_fingerprint(root.path)
    except (RefreshFailedError, OSError):
        return None


def _empty_result(business_date: date, reason: str) -> dict[str, Any]:
    return {
        "status": "not_ready",
        "reason": reason,
        "businessDate": business_date.isoformat(),
        "generationId": None,
        "serviceScopes": [],
        "selectedScope": None,
        "serviceIntervals": [],
        "attendance": {"scope": "date-wide", "evidenceStates": [], "gapTypes": []},
    }


def read_operate_evidence(
    database: Path,
    home: Path,
    business_date: date,
    requested_scope: tuple[str, str] | None = None,
) -> dict[str, Any]:
    """Read one consistent SQLite snapshot from the successful active cut."""
    with closing(sqlite3.connect(database, timeout=30)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        active = connection.execute(
            """
            SELECT generation.id, generation.status, generation.catalog_sha256
            FROM wfm_active_generation AS pointer
            JOIN wfm_refresh_generation AS generation
              ON generation.id = pointer.generation_id
            WHERE pointer.singleton = 1
            """
        ).fetchone()
        if active is None or active["status"] != "succeeded":
            return _empty_result(business_date, "NO_ACTIVE_GENERATION")

        catalog = _catalog_for_home(home)
        if catalog is None:
            return _empty_result(business_date, "SOURCE_ROOT_UNAVAILABLE")
        if active["catalog_sha256"] != catalog:
            return _empty_result(business_date, "SOURCE_ROOT_CHANGED")

        generation_id = int(active["id"])
        day = business_date.isoformat()
        scope_rows = connection.execute(
            """
            SELECT DISTINCT service_scope, comparison_scope
            FROM wfm_service_interval
            WHERE generation_id = ? AND business_date = ?
            ORDER BY service_scope, comparison_scope
            LIMIT ?
            """,
            (generation_id, day, _MAX_SCOPE_OPTIONS + 1),
        ).fetchall()
        if len(scope_rows) > _MAX_SCOPE_OPTIONS or any(
            len(str(row["service_scope"])) > _MAX_SCOPE_LABEL_CHARS
            or len(str(row["comparison_scope"])) > _MAX_SCOPE_LABEL_CHARS
            for row in scope_rows
        ):
            raise OperateReadError("service scope catalog exceeds the bounded response")
        scopes = [
            {
                "serviceScope": str(row["service_scope"]),
                "comparisonScope": str(row["comparison_scope"]),
            }
            for row in scope_rows
        ]
        selected = (
            scopes[0]
            if requested_scope is None and scopes
            else {
                "serviceScope": requested_scope[0],
                "comparisonScope": requested_scope[1],
            }
            if requested_scope is not None
            else None
        )
        if selected is not None and selected not in scopes:
            raise OperateQueryError("scope is not available for the selected date")

        intervals: list[dict[str, Any]] = []
        if selected is not None:
            rows = connection.execute(
                """
                SELECT interval_start, interval_end,
                       sum(offered) AS offered, sum(answered) AS answered,
                       sum(abandoned) AS abandoned,
                       sum(short_abandoned) AS short_abandoned,
                       sum(abandoned_within_target) AS abandoned_within_target,
                       sum(answered_within_target) AS answered_within_target,
                       sum(talk_seconds) AS talk_seconds,
                       sum(hold_seconds) AS hold_seconds,
                       sum(wrap_seconds) AS wrap_seconds,
                       sum(handled_seconds) AS handled_seconds,
                       sum(call_legs) AS call_legs,
                       sum(transferred_legs) AS transferred_legs
                FROM wfm_service_interval
                WHERE generation_id = ? AND business_date = ?
                  AND service_scope = ? AND comparison_scope = ?
                GROUP BY interval_start, interval_end
                ORDER BY interval_start, interval_end
                LIMIT ?
                """,
                (
                    generation_id,
                    day,
                    selected["serviceScope"],
                    selected["comparisonScope"],
                    _MAX_INTERVALS + 1,
                ),
            ).fetchall()
            if len(rows) > _MAX_INTERVALS:
                raise OperateReadError("service interval count exceeds one business day")
            intervals = [
                {
                    "intervalStart": str(row["interval_start"]),
                    "intervalEnd": str(row["interval_end"]),
                    "offered": int(row["offered"]),
                    "answered": int(row["answered"]),
                    "abandoned": int(row["abandoned"]),
                    "shortAbandoned": int(row["short_abandoned"]),
                    "abandonedWithinTarget": int(row["abandoned_within_target"]),
                    "answeredWithinTarget": int(row["answered_within_target"]),
                    "talkSeconds": int(row["talk_seconds"]),
                    "holdSeconds": int(row["hold_seconds"]),
                    "wrapSeconds": int(row["wrap_seconds"]),
                    "handledSeconds": int(row["handled_seconds"]),
                    "callLegs": int(row["call_legs"]),
                    "transferredLegs": int(row["transferred_legs"]),
                }
                for row in rows
            ]

        evidence_states = [
            {"state": str(row["evidence_state"]), "agentDays": int(row["agent_days"])}
            for row in connection.execute(
                """
                SELECT evidence_state, count(*) AS agent_days
                FROM wfm_attendance_agent_day
                WHERE generation_id = ? AND business_date = ?
                GROUP BY evidence_state ORDER BY evidence_state
                """,
                (generation_id, day),
            )
        ]
        gap_types = [
            {
                "type": str(row["gap_type"]),
                "fragments": int(row["fragments"]),
                "minutes": int(row["minutes"]),
            }
            for row in connection.execute(
                """
                SELECT gap_type, count(*) AS fragments, sum(gap_minutes) AS minutes
                FROM wfm_attendance_gap
                WHERE generation_id = ? AND business_date = ?
                GROUP BY gap_type ORDER BY gap_type
                """,
                (generation_id, day),
            )
        ]

    if _catalog_for_home(home) != catalog:
        return _empty_result(business_date, "SOURCE_ROOT_CHANGED")
    return {
        "status": "ready",
        "reason": None,
        "businessDate": day,
        "generationId": generation_id,
        "serviceScopes": scopes,
        "selectedScope": selected,
        "serviceIntervals": intervals,
        "attendance": {
            "scope": "date-wide",
            "evidenceStates": evidence_states,
            "gapTypes": gap_types,
        },
    }
