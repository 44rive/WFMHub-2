from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from wfmhub2_compat.catalog import load_queue_mapping_snapshot
from wfmhub2_compat.refresh_store import RefreshStore, SourceVersion
from wfmhub2_compat.storage import SCHEMA, initialize_database

EMPTY_CATALOG = hashlib.sha256(b"").hexdigest()


def source(*, digest: str = "a" * 64) -> SourceVersion:
    return SourceVersion(
        source_type="call_by_call",
        source_key="synthetic/calls.csv",
        file_size=28,
        mtime_ns=123456789,
        content_sha256=digest,
        adapter_version="test-v1",
        policy_fingerprint="synthetic-map-v1",
        row_count=2,
    )


def start(store: RefreshStore) -> int:
    return store.start_generation(catalog_sha256=EMPTY_CATALOG, model_version="test-v1")


def test_new_control_database_has_generation_authority(tmp_path: Path) -> None:
    path = tmp_path / "data/control.sqlite"
    store = RefreshStore(path)
    initialize_database(path)

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        indexes = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
        integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
    assert {
        "compatibility_run",
        "wfm_refresh_generation",
        "wfm_active_generation",
        "wfm_source_manifest",
        "wfm_quality_issue",
    } <= tables
    assert journal == "wal"
    assert integrity == "ok"
    assert {
        "ix_wfm_time_off_agent_range",
        "ix_wfm_lilo_agent_date",
        "ix_wfm_status_agent_interval",
    } <= indexes
    assert store.active_generation_id() is None


def test_migrates_existing_compatibility_database_without_losing_report(tmp_path: Path) -> None:
    path = tmp_path / "data/control.sqlite"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE compatibility_run (
                id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL,
                overall_status TEXT NOT NULL, report_schema_version INTEGER NOT NULL,
                probe_count INTEGER NOT NULL, passed_count INTEGER NOT NULL,
                failed_count INTEGER NOT NULL, report_path TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO compatibility_run
            (recorded_at, overall_status, report_schema_version, probe_count,
             passed_count, failed_count, report_path)
            VALUES ('synthetic-time', 'pass', 1, 5, 5, 0, 'synthetic-report.json')
            """
        )
    store = RefreshStore(path)
    initialize_database(path)

    with sqlite3.connect(path) as connection:
        old_report = connection.execute(
            "SELECT overall_status, report_path FROM compatibility_run"
        ).fetchone()
        control_rows = connection.execute(
            "SELECT singleton, generation_id FROM wfm_active_generation"
        ).fetchall()
    assert old_report == ("pass", "synthetic-report.json")
    assert control_rows == [(1, None)]
    assert store.active_generation_id() is None


def test_existing_preview_manifest_gains_physical_bronze_owner(tmp_path: Path) -> None:
    path = tmp_path / "data/control.sqlite"
    path.parent.mkdir(parents=True)
    old_schema = SCHEMA.replace(
        "    bronze_generation_id INTEGER REFERENCES wfm_refresh_generation(id),\n", ""
    )
    with sqlite3.connect(path) as connection:
        connection.executescript(old_schema)
        connection.execute(
            """
            INSERT INTO wfm_refresh_generation
            (id, started_at, status, catalog_sha256, model_version)
            VALUES (1, 'synthetic-time', 'succeeded', ?, 'test-v1')
            """,
            (EMPTY_CATALOG,),
        )
        connection.execute(
            """
            INSERT INTO wfm_source_manifest
            (generation_id, source_type, source_key, file_size, mtime_ns,
             content_sha256, adapter_version, policy_fingerprint, row_count, recorded_at)
            VALUES (1, 'call_by_call', 'synthetic/calls.csv', 28, 123456789,
                    ?, 'test-v1', 'synthetic-map-v1', 2, 'synthetic-time')
            """,
            ("a" * 64,),
        )
    initialize_database(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            """
            SELECT bronze_generation_id FROM wfm_source_manifest
            WHERE generation_id = 1 AND source_type = 'call_by_call'
            """
        ).fetchone() == (1,)


def test_reused_bronze_owner_must_be_successful_matching_evidence(tmp_path: Path) -> None:
    store = RefreshStore(tmp_path / "control.sqlite")
    first = start(store)
    store.stage_source(first, source())
    store.activate_generation(first)
    second = start(store)

    store.stage_source(second, source(), bronze_generation_id=first)
    with sqlite3.connect(store.path) as connection:
        assert connection.execute(
            """
            SELECT bronze_generation_id FROM wfm_source_manifest
            WHERE generation_id = ? AND source_type = 'call_by_call'
            """,
            (second,),
        ).fetchone() == (first,)
    with pytest.raises(ValueError, match="matching successful evidence"):
        store.stage_source(second, source(digest="b" * 64), bronze_generation_id=first)


def test_source_manifest_is_idempotent_and_inherited_until_changed(tmp_path: Path) -> None:
    store = RefreshStore(tmp_path / "control.sqlite")
    first = start(store)
    manifest_id = store.stage_source(first, source())
    assert store.stage_source(first, source()) == manifest_id
    with pytest.raises(ValueError, match="different evidence"):
        store.stage_source(first, source(digest="b" * 64))
    store.activate_generation(first)
    assert (
        store.active_source(source_type="call_by_call", source_key="synthetic/calls.csv")
        == source()
    )

    second = start(store)
    store.activate_generation(second)
    assert (
        store.active_source(source_type="call_by_call", source_key="synthetic/calls.csv")
        == source()
    )

    third = start(store)
    store.stage_source(third, source(digest="c" * 64))
    store.activate_generation(third)
    assert store.active_source(
        source_type="call_by_call", source_key="synthetic/calls.csv"
    ) == source(digest="c" * 64)

    fourth = start(store)
    removal_id = store.stage_removed_source(
        fourth, source_type="call_by_call", source_key="synthetic/calls.csv"
    )
    assert (
        store.stage_removed_source(
            fourth, source_type="call_by_call", source_key="synthetic/calls.csv"
        )
        == removal_id
    )
    store.activate_generation(fourth)
    assert store.active_source(source_type="call_by_call", source_key="synthetic/calls.csv") is None
    assert store.restore_previous_generation(expected_active_id=fourth) == third
    assert store.active_source(
        source_type="call_by_call", source_key="synthetic/calls.csv"
    ) == source(digest="c" * 64)


def test_failed_publish_rolls_back_fact_write_and_active_pointer(tmp_path: Path) -> None:
    path = tmp_path / "control.sqlite"
    store = RefreshStore(path)
    first = start(store)
    store.activate_generation(first)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE synthetic_fact (generation_id INTEGER, value TEXT)")

    second = start(store)
    store.stage_source(second, source())

    def broken_publish(connection: sqlite3.Connection, generation_id: int) -> None:
        connection.execute("INSERT INTO synthetic_fact VALUES (?, ?)", (generation_id, "partial"))
        raise RuntimeError("synthetic rebuild failed")

    with pytest.raises(RuntimeError, match="synthetic rebuild failed"):
        store.activate_generation(second, publish=broken_publish)

    with sqlite3.connect(path) as connection:
        facts = connection.execute("SELECT * FROM synthetic_fact").fetchall()
        status = connection.execute(
            "SELECT status FROM wfm_refresh_generation WHERE id = ?", (second,)
        ).fetchone()
    assert facts == []
    assert status == ("running",)
    assert store.active_generation_id() == first
    assert store.active_source(source_type="call_by_call", source_key="synthetic/calls.csv") is None

    store.fail_generation(second, reason="synthetic rebuild failed")
    with pytest.raises(ValueError, match="not running"):
        store.activate_generation(second)
    assert store.active_generation_id() == first


def test_blocking_quality_issue_and_stale_generation_cannot_activate(tmp_path: Path) -> None:
    store = RefreshStore(tmp_path / "control.sqlite")
    blocked = start(store)
    store.record_quality_issue(
        blocked,
        issue_code="MISSING_QUEUE_MAPPING",
        severity="error",
        details="synthetic queue has no exact mapping",
    )
    with pytest.raises(ValueError, match="blocking quality"):
        store.activate_generation(blocked)
    assert store.active_generation_id() is None
    store.fail_generation(blocked, reason="missing mapping")

    first = start(store)
    stale = start(store)
    store.activate_generation(first)
    with pytest.raises(RuntimeError, match="changed since"):
        store.activate_generation(stale)
    assert store.active_generation_id() == first


def test_explicit_rollback_restores_prior_successful_generation(tmp_path: Path) -> None:
    store = RefreshStore(tmp_path / "control.sqlite")
    first = start(store)
    store.stage_source(first, source())
    store.activate_generation(first)
    second = start(store)
    store.stage_source(second, source(digest="b" * 64))
    store.activate_generation(second)

    with pytest.raises(RuntimeError, match="changed"):
        store.restore_previous_generation(expected_active_id=first)
    assert store.active_generation_id() == second
    assert store.restore_previous_generation(expected_active_id=second) == first
    assert store.active_generation_id() == first
    assert (
        store.active_source(source_type="call_by_call", source_key="synthetic/calls.csv")
        == source()
    )


def test_exact_queue_catalog_snapshot_uses_reviewed_old_contract(tmp_path: Path) -> None:
    path = tmp_path / "queue_mapping.csv"
    path.write_text(
        "mapping_type,source_system,source_value,service_scope,designation\n"
        "queue,STORM,SYNTHETIC_FR,Demo FR,Demo\n"
        "scope_rollup,CONFIG,Demo FR,Demo,Demo total\n",
        encoding="utf-8",
    )
    snapshot = load_queue_mapping_snapshot(path)
    assert snapshot.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(snapshot.mappings) == 2
    assert snapshot.mappings[0].source_value == "SYNTHETIC_FR"

    path.write_text(
        path.read_text(encoding="utf-8") + "queue,STORM,SYNTHETIC_FR,Other,Other\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicates"):
        load_queue_mapping_snapshot(path)


def test_queue_catalog_accepts_optional_designation_and_rejects_normalized_duplicates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "queue_mapping.csv"
    path.write_text(
        "mapping_type,source_system,source_value,service_scope,designation\n"
        "queue,STORM,Synthetic-FR,Demo FR,\n",
        encoding="utf-8",
    )
    assert load_queue_mapping_snapshot(path).mappings[0].designation == ""

    path.write_text(
        path.read_text(encoding="utf-8") + "queue,storm,Synthetic FR,Other,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="normalized source key"):
        load_queue_mapping_snapshot(path)


def test_compat_refresh_modules_import_without_third_party_native_stack() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    script = (
        "import sys; "
        f"sys.path.insert(0, {str(source_root)!r}); "
        "import wfmhub2_compat.refresh_store, wfmhub2_compat.catalog; "
        "forbidden={'fastapi','pydantic','duckdb','numpy','polars','pyarrow','ortools'}; "
        "assert not forbidden.intersection(sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
