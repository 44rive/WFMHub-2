"""Build-time compatibility and persistence probe for a local DuckLake binary."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import duckdb


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(extension: Path, work_directory: Path) -> dict[str, object]:
    catalog = work_directory / "catalog.ducklake"
    data_path = work_directory / "files"
    data_path.mkdir(parents=True, exist_ok=True)

    extension_sql = _sql_path(extension)
    catalog_sql = _sql_path(catalog)
    data_sql = _sql_path(data_path)

    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute(f"LOAD '{extension_sql}'")
        loaded = connection.execute(
            "SELECT loaded FROM duckdb_extensions() WHERE extension_name = 'ducklake'"
        ).fetchone()
        if loaded != (True,):
            raise RuntimeError(f"DuckLake did not report as loaded: {loaded!r}")

        connection.execute(f"ATTACH 'ducklake:{catalog_sql}' AS phase0 (DATA_PATH '{data_sql}')")
        connection.execute("CALL phase0.set_option('data_inlining_row_limit', '0')")
        connection.execute("CREATE TABLE phase0.main.stack_probe(id INTEGER, value VARCHAR)")
        connection.execute("INSERT INTO phase0.main.stack_probe VALUES (1, 'offline-local')")
    finally:
        connection.close()

    reopened = duckdb.connect(database=":memory:")
    try:
        reopened.execute(f"LOAD '{extension_sql}'")
        reopened.execute(f"ATTACH 'ducklake:{catalog_sql}' AS phase0 (DATA_PATH '{data_sql}')")
        row = reopened.execute("SELECT id, value FROM phase0.main.stack_probe").fetchone()
        if row != (1, "offline-local"):
            raise RuntimeError(f"DuckLake restart/read probe returned {row!r}")
    finally:
        reopened.close()

    parquet_files = list(data_path.rglob("*.parquet"))
    if not parquet_files:
        raise RuntimeError("DuckLake probe wrote no Parquet data file")

    return {
        "duckdb_version": duckdb.__version__,
        "extension_path": str(extension.resolve()),
        "extension_sha256": _sha256(extension),
        "parquet_files": len(parquet_files),
        "restart_read": "pass",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--expected-duckdb", default="1.5.5")
    parser.add_argument("--expected-sha256", default=None)
    parser.add_argument("--work-directory", type=Path, default=None)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args()

    extension = args.extension.resolve()
    if not extension.is_file():
        raise FileNotFoundError(f"DuckLake extension not found: {extension}")
    if duckdb.__version__ != args.expected_duckdb:
        raise RuntimeError(
            f"DuckDB version mismatch: expected {args.expected_duckdb}, found {duckdb.__version__}"
        )
    if args.expected_sha256 and _sha256(extension) != args.expected_sha256.lower():
        raise RuntimeError("DuckLake extension SHA-256 does not match the pinned build artifact")

    if args.work_directory is None:
        with tempfile.TemporaryDirectory(prefix="wfmhub2-ducklake-probe-") as temporary:
            evidence = _probe(extension, Path(temporary))
    else:
        args.work_directory.mkdir(parents=True, exist_ok=True)
        evidence = _probe(extension, args.work_directory.resolve())

    serialized = json.dumps(evidence, indent=2, sort_keys=True)
    print(serialized)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(f"{serialized}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
