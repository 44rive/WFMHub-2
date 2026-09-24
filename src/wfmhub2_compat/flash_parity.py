"""Read-only, legacy-Flash-aligned additive evidence for parity review.

This deliberately does not evaluate service ratios or imply parity with the
old workbook. The exact queue allowlists come from Portable v0.36.0.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import tomllib
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs

from wfmhub2_compat.operate_evidence import (
    OperateQueryError,
    OperateReadError,
    catalog_for_home,
)

_PROFILE_ID = re.compile(r"[a-z0-9_]{1,40}\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_COLUMNS = (
    "offered",
    "answered",
    "abandoned",
    "short_abandoned",
    "abandoned_within_target",
    "answered_within_target",
    "talk_seconds",
    "hold_seconds",
    "wrap_seconds",
    "handled_seconds",
    "call_legs",
    "transferred_legs",
)
_PUBLIC_COLUMNS = (
    "offered",
    "answered",
    "abandoned",
    "shortAbandoned",
    "abandonedWithinTarget",
    "answeredWithinTarget",
    "talkSeconds",
    "holdSeconds",
    "wrapSeconds",
    "handledSeconds",
    "callLegs",
    "transferredLegs",
)


@dataclass(frozen=True)
class FlashProfile:
    profile_id: str
    label: str
    effective_from: date
    effective_to: date | None
    queues: tuple[str, ...]

    def active_on(self, day: date) -> bool:
        return self.effective_from <= day and (
            self.effective_to is None or day <= self.effective_to
        )


def parse_flash_query(query: str) -> tuple[date, str | None]:
    if len(query) > 256:
        raise OperateQueryError("invalid Flash parity query")
    try:
        fields = parse_qs(query, keep_blank_values=True, max_num_fields=2)
    except ValueError as exc:
        raise OperateQueryError("invalid Flash parity query") from exc
    if set(fields) - {"date", "profile"}:
        raise OperateQueryError("invalid Flash parity query")
    days = fields.get("date", [])
    if len(days) != 1 or _DATE.fullmatch(days[0]) is None:
        raise OperateQueryError("date must be exactly YYYY-MM-DD")
    try:
        day = date.fromisoformat(days[0])
    except ValueError as exc:
        raise OperateQueryError("date must be a real calendar day") from exc
    requested = fields.get("profile", [])
    if len(requested) > 1 or (requested and _PROFILE_ID.fullmatch(requested[0]) is None):
        raise OperateQueryError("invalid Flash profile")
    return day, requested[0] if requested else None


def load_flash_profiles(path: Path | None = None) -> tuple[str, tuple[FlashProfile, ...]]:
    selected = path or Path(__file__).resolve().parents[2] / "config/legacy_flash_profiles.toml"
    content = selected.read_bytes()
    if len(content) > 32_768:
        raise OperateReadError("Flash profile catalog exceeds its size limit")
    try:
        raw = cast(dict[str, object], tomllib.loads(content.decode("utf-8")))
        rows = raw["profiles"]
        if not isinstance(rows, list) or not 1 <= len(cast(list[object], rows)) <= 16:
            raise ValueError("invalid profile count")
        profiles: list[FlashProfile] = []
        seen: set[str] = set()
        for item in cast(list[object], rows):
            if not isinstance(item, dict):
                raise ValueError("invalid Flash profile row")
            row = cast(dict[str, object], item)
            profile_id = row["id"]
            label = row["label"]
            queues = row["flash_queues"]
            sources = row["flash_source_systems"]
            if (
                not isinstance(profile_id, str)
                or _PROFILE_ID.fullmatch(profile_id) is None
                or profile_id in seen
                or not isinstance(label, str)
                or not 1 <= len(label) <= 80
                or sources != ["CALL_BY_CALL"]
                or not isinstance(queues, list)
                or not 1 <= len(cast(list[object], queues)) <= 64
                or any(
                    not isinstance(queue, str) or not 1 <= len(queue) <= 160
                    for queue in cast(list[object], queues)
                )
            ):
                raise ValueError("invalid Flash profile")
            queue_names = cast(list[str], queues)
            if len({queue.casefold() for queue in queue_names}) != len(queue_names):
                raise ValueError("duplicate Flash queue")
            start = row["effective_from"]
            end = row.get("effective_to")
            if not isinstance(start, date) or (end is not None and not isinstance(end, date)):
                raise ValueError("invalid effective date")
            if end is not None and end < start:
                raise ValueError("invalid effective period")
            profiles.append(FlashProfile(profile_id, label, start, end, tuple(queue_names)))
            seen.add(profile_id)
    except (KeyError, TypeError, ValueError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise OperateReadError("Flash profile catalog is invalid") from exc
    return hashlib.sha256(content).hexdigest(), tuple(profiles)


def _not_ready(day: date, reason: str) -> dict[str, Any]:
    return {
        "status": "not_ready",
        "reason": reason,
        "businessDate": day.isoformat(),
        "generationId": None,
        "catalogSha256": None,
        "profiles": [],
        "selectedProfile": None,
        "serviceHours": [],
        "totals": None,
    }


def read_flash_parity(
    database: Path,
    home: Path,
    day: date,
    requested_profile: str | None = None,
    *,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    """Compare exact legacy Flash queue populations within one active cut."""
    catalog_sha, all_profiles = load_flash_profiles(catalog_path)
    active_profiles = tuple(profile for profile in all_profiles if profile.active_on(day))
    if requested_profile is not None and requested_profile not in {
        profile.profile_id for profile in active_profiles
    }:
        raise OperateQueryError("Flash profile is not active on the selected date")
    selected = next(
        (profile for profile in active_profiles if profile.profile_id == requested_profile),
        active_profiles[0] if requested_profile is None and active_profiles else None,
    )
    if selected is None:
        raise OperateQueryError("no Flash profile is active on the selected date")

    with closing(sqlite3.connect(database, timeout=30)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        active = connection.execute(
            """SELECT generation.id, generation.status, generation.catalog_sha256
               FROM wfm_active_generation AS pointer
               JOIN wfm_refresh_generation AS generation
                 ON generation.id = pointer.generation_id
               WHERE pointer.singleton = 1"""
        ).fetchone()
        if active is None or active["status"] != "succeeded":
            return _not_ready(day, "NO_ACTIVE_GENERATION")
        source_catalog = catalog_for_home(home)
        if source_catalog is None:
            return _not_ready(day, "SOURCE_ROOT_UNAVAILABLE")
        if source_catalog != active["catalog_sha256"]:
            return _not_ready(day, "SOURCE_ROOT_CHANGED")

        marks = ",".join("?" for _ in selected.queues)
        columns = ", ".join(f"sum({name}) AS {name}" for name in _COLUMNS)
        rows = connection.execute(
            f"""SELECT interval_start, interval_end, {columns}
                FROM wfm_service_interval
                WHERE generation_id = ? AND business_date = ?
                  AND source_system = 'CALL_BY_CALL'
                  AND upper(queue) IN ({marks})
                GROUP BY interval_start, interval_end
                ORDER BY interval_start, interval_end LIMIT 105""",
            (int(active["id"]), day.isoformat(), *(queue.upper() for queue in selected.queues)),
        ).fetchall()
        if len(rows) > 104:
            raise OperateReadError("Flash interval count exceeds one business day")
        intervals = [
            {
                "intervalStart": str(row["interval_start"]),
                "intervalEnd": str(row["interval_end"]),
                **{
                    public: int(row[column])
                    for column, public in zip(_COLUMNS, _PUBLIC_COLUMNS, strict=True)
                },
            }
            for row in rows
        ]
        generation_id = int(active["id"])

    if catalog_for_home(home) != source_catalog:
        return _not_ready(day, "SOURCE_ROOT_CHANGED")
    by_hour: dict[str, dict[str, int | str]] = {}
    for interval in intervals:
        hour_start = str(interval["intervalStart"])[:13] + ":00:00"
        hour = by_hour.setdefault(
            hour_start, {"hourStart": hour_start, **dict.fromkeys(_PUBLIC_COLUMNS, 0)}
        )
        for name in _PUBLIC_COLUMNS:
            hour[name] = int(hour[name]) + int(interval[name])
    hours = [by_hour[key] for key in sorted(by_hour)]
    totals = (
        {name: sum(int(row[name]) for row in hours) for name in _PUBLIC_COLUMNS} if hours else None
    )
    return {
        "status": "ready",
        "reason": None,
        "businessDate": day.isoformat(),
        "generationId": generation_id,
        "catalogSha256": catalog_sha,
        "profiles": [
            {"id": profile.profile_id, "label": profile.label} for profile in active_profiles
        ],
        "selectedProfile": {"id": selected.profile_id, "label": selected.label},
        "serviceHours": hours,
        "totals": totals,
    }
