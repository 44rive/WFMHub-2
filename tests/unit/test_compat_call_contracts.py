from __future__ import annotations

import csv
import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from wfmhub2_compat.call_contracts import (
    CallPolicy,
    load_call_policy,
    preflight_call_source,
    publish_call_plans,
    stage_call_plans,
)
from wfmhub2_compat.refresh_store import RefreshStore, SourceVersion
from wfmhub2_compat.source_contracts import FteAgentRow, FteSnapshot, SourceContractError

EMPTY_CATALOG = hashlib.sha256(b"").hexdigest()
CALL_HEADERS = [
    "[Call Date/Time]",
    "[Call End Date/Time]",
    "[Call ID]",
    "[Call Reference Number]",
    "[Agent ID]",
    "[Agent]",
    "[Talk Time]",
    "[Hold Time]",
    "[Total Wrap Time]",
    "[Call Direction]",
    "[Total Queue Wait Time]",
    "[Ringing Duration]",
    "[Queue]",
    "[Transferred?]",
    "[PCSStatus]",
]


def _roster() -> FteSnapshot:
    row = FteAgentRow(
        "FTE/FTE Count.xlsx",
        "Agent",
        2,
        "00123",
        "Active",
        "Ada Agent",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        1.0,
        None,
        True,
        (),
    )
    version = SourceVersion(
        "fte",
        "FTE/FTE Count.xlsx",
        1,
        1,
        hashlib.sha256(b"fte").hexdigest(),
        "test",
        "test",
        1,
    )
    return FteSnapshot("FTE/FTE Count.xlsx", (row,), (), (), version)


def _policy(tmp_path: Path) -> CallPolicy:
    mapping = tmp_path / "queue_mapping.csv"
    mapping.write_text(
        "mapping_type,source_system,source_value,service_scope,designation\n"
        "scope_rollup,CONFIG,Demo FR,Demo,Demo total\n"
        "queue,STORM,SYNTHETIC_FR,Demo FR,Demo queue\n",
        encoding="utf-8",
    )
    rules = tmp_path / "service_rules.toml"
    rules.write_text(
        'version = "1"\n[service]\ntarget_seconds = 30\nshort_abandon_seconds = 5\n',
        encoding="utf-8",
    )
    return load_call_policy(mapping, rules)


def _write_calls(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CALL_HEADERS)
        writer.writerows(rows)


def _row(
    call_id: str,
    *,
    agent_id: str = "",
    agent_name: str = "",
    queue: str = "SYNTHETIC_FR",
    wait: str = "00:00:04",
    talk: str = "",
    direction: str = "I",
    pcs_status: str = "",
) -> list[str]:
    return [
        "08/01/2026 08:07",
        "08/01/2026 08:10",
        call_id,
        f"ref-{call_id}",
        agent_id,
        agent_name,
        talk,
        "",
        "",
        direction,
        wait,
        "00:00:00",
        queue,
        "N",
        pcs_status,
    ]


def _publish(
    tmp_path: Path,
    paths: tuple[Path, ...],
    policy: CallPolicy,
) -> tuple[RefreshStore, int]:
    plans = tuple(
        preflight_call_source(
            path,
            source_key=f"Storm/Call by Call/{path.name}",
            roster=_roster(),
            policy=policy,
        )
        for path in paths
    )
    store = RefreshStore(tmp_path / "control.sqlite")
    generation = store.start_generation(catalog_sha256=EMPTY_CATALOG, model_version="calls-v1")
    stage_call_plans(store, generation, plans)
    store.activate_generation(
        generation,
        publish=lambda connection, generation_id: publish_call_plans(
            connection,
            generation_id,
            plans,
            roster=_roster(),
            policy=policy,
        ),
    )
    return store, generation


def test_dual_scope_lanes_and_service_components_are_explicit(tmp_path: Path) -> None:
    path = tmp_path / "calls.csv"
    _write_calls(
        path,
        [
            _row("short"),
            _row("target-abandon", wait="00:00:20"),
            _row(
                "answered",
                agent_id="00123",
                agent_name="Ada Agent",
                wait="00:00:20",
                talk="00:01:00",
            ),
            _row(
                "agent-only",
                agent_id="00123",
                agent_name="Ada Agent",
                queue="UNMAPPED",
                direction="O",
            ),
            _row("outside", agent_id="999", agent_name="Outside", queue="UNMAPPED"),
            [
                "not-a-date",
                "",
                "bad",
                "bad",
                "",
                "",
                "",
                "",
                "",
                "I",
                "",
                "",
                "SYNTHETIC_FR",
                "",
                "",
            ],
        ],
    )
    policy = _policy(tmp_path)
    plan = preflight_call_source(
        path,
        source_key="Storm/Call by Call/calls.csv",
        roster=_roster(),
        policy=policy,
    )

    assert (plan.accepted_rows, plan.service_rows, plan.scoped_out_rows, plan.rejected_rows) == (
        4,
        3,
        1,
        1,
    )
    assert plan.unmapped_rows == 1
    assert {finding.issue_code for finding in plan.findings} == {
        "CALL_REJECTED_ROWS",
        "CALL_OUTSIDE_SCOPE_ROWS",
        "CALL_UNMAPPED_AGENT_ROWS",
    }

    store, generation = _publish(tmp_path, (path,), policy)
    with sqlite3.connect(store.path) as connection:
        flags = connection.execute(
            """
            SELECT call_id, agent_eligible, service_eligible, scope_match
            FROM wfm_call_leg WHERE generation_id = ? ORDER BY call_id
            """,
            (generation,),
        ).fetchall()
        interval = connection.execute(
            """
            SELECT offered, answered, abandoned, short_abandoned,
                   abandoned_within_target, answered_within_target,
                   handled_seconds, call_legs
            FROM wfm_service_interval WHERE generation_id = ?
            """,
            (generation,),
        ).fetchone()
    assert flags == [
        ("agent-only", 1, 0, "id"),
        ("answered", 1, 1, "id"),
        ("short", 0, 1, "queue"),
        ("target-abandon", 0, 1, "queue"),
    ]
    assert interval == (3, 1, 2, 1, 1, 1, 60, 3)


def test_overlapping_exports_keep_newest_matured_leg_once(tmp_path: Path) -> None:
    old = tmp_path / "old.csv"
    new = tmp_path / "new.csv"
    _write_calls(old, [_row("same", pcs_status="Pending")])
    _write_calls(new, [_row("same", pcs_status="Complete")])
    os.utime(old, ns=(1_000_000_000, 1_000_000_000))
    os.utime(new, ns=(2_000_000_000, 2_000_000_000))

    store, generation = _publish(tmp_path, (old, new), _policy(tmp_path))
    with sqlite3.connect(store.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM wfm_raw_call_leg WHERE generation_id = ?", (generation,)
        ).fetchone() == (2,)
        assert connection.execute(
            "SELECT source_key, pcs_status FROM wfm_call_leg WHERE generation_id = ?",
            (generation,),
        ).fetchone() == ("Storm/Call by Call/new.csv", "Complete")
        assert connection.execute(
            "SELECT offered FROM wfm_service_interval WHERE generation_id = ?", (generation,)
        ).fetchone() == (1,)


def test_source_mutation_rolls_back_call_publication(tmp_path: Path) -> None:
    path = tmp_path / "calls.csv"
    _write_calls(path, [_row("one")])
    policy = _policy(tmp_path)
    plan = preflight_call_source(
        path,
        source_key="Storm/Call by Call/calls.csv",
        roster=_roster(),
        policy=policy,
    )
    store = RefreshStore(tmp_path / "control.sqlite")
    generation = store.start_generation(catalog_sha256=EMPTY_CATALOG, model_version="calls-v1")
    stage_call_plans(store, generation, (plan,))
    path.write_text(path.read_text(encoding="utf-8-sig") + "\n", encoding="utf-8")

    with pytest.raises(SourceContractError, match="changed before publication"):
        store.activate_generation(
            generation,
            publish=lambda connection, generation_id: publish_call_plans(
                connection,
                generation_id,
                (plan,),
                roster=_roster(),
                policy=policy,
            ),
        )
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT count(*) FROM wfm_raw_call_leg").fetchone() == (0,)


def test_missing_required_header_blocks_call_file(tmp_path: Path) -> None:
    path = tmp_path / "calls.csv"
    _write_calls(path, [])
    text = path.read_text(encoding="utf-8-sig").replace("[Call ID]", "[Wrong]")
    path.write_text(text, encoding="utf-8-sig")

    with pytest.raises(SourceContractError, match="Call ID"):
        preflight_call_source(
            path,
            source_key="Storm/Call by Call/calls.csv",
            roster=_roster(),
            policy=_policy(tmp_path),
        )


def test_invalid_durations_remain_unknown_and_surface_quality(tmp_path: Path) -> None:
    path = tmp_path / "calls.csv"
    _write_calls(path, [_row("bad-duration", wait="-1", talk="not-a-duration")])
    policy = _policy(tmp_path)
    plan = preflight_call_source(
        path,
        source_key="Storm/Call by Call/calls.csv",
        roster=_roster(),
        policy=policy,
    )

    assert plan.degraded_rows == 1
    assert {finding.issue_code for finding in plan.findings} == {"CALL_DEGRADED_ROWS"}
    store, generation = _publish(tmp_path, (path,), policy)
    with sqlite3.connect(store.path) as connection:
        call = connection.execute(
            """
            SELECT queue_wait_seconds, talk_seconds, validation_codes
            FROM wfm_call_leg WHERE generation_id = ?
            """,
            (generation,),
        ).fetchone()
        interval = connection.execute(
            """
            SELECT offered, answered, answered_within_target, abandoned_within_target
            FROM wfm_service_interval WHERE generation_id = ?
            """,
            (generation,),
        ).fetchone()
    assert call == (None, None, '["INVALID_DURATION","MISSING_RESPONSE_CLOCK"]')
    assert interval == (1, 0, 0, 0)


def test_call_publication_crosses_bounded_batch_boundary(tmp_path: Path) -> None:
    path = tmp_path / "calls.csv"
    _write_calls(path, [_row(str(index)) for index in range(5001)])
    store, generation = _publish(tmp_path, (path,), _policy(tmp_path))
    with sqlite3.connect(store.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM wfm_raw_call_leg WHERE generation_id = ?", (generation,)
        ).fetchone() == (5001,)
