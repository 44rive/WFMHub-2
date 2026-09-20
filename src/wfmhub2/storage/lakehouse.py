from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, Protocol, TypedDict

import duckdb


class LakehouseSettings(Protocol):
    @property
    def ducklake_extension(self) -> Path | None: ...

    @property
    def ducklake_catalog_path(self) -> Path: ...

    @property
    def ducklake_data_path(self) -> Path: ...


LAKE_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS silver.service_interval_demand (
    business_date DATE NOT NULL,
    interval_start TIMESTAMP NOT NULL,
    service_scope VARCHAR NOT NULL,
    offered DOUBLE,
    handled DOUBLE,
    handle_seconds DOUBLE,
    source_version VARCHAR,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gold.staffing_interval (
    business_date DATE NOT NULL,
    interval_start TIMESTAMP NOT NULL,
    service_scope VARCHAR NOT NULL,
    required_productive_fte DOUBLE,
    required_scheduled_fte DOUBLE,
    scheduled_fte DOUBLE,
    present_fte DOUBLE,
    effective_fte DOUBLE,
    staffing_gap DOUBLE,
    service_level DOUBLE,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gold.forecast_accuracy (
    business_date DATE NOT NULL,
    interval_start TIMESTAMP NOT NULL,
    service_scope VARCHAR NOT NULL,
    forecast_created_at TIMESTAMP,
    model_id VARCHAR,
    forecast_volume DOUBLE,
    actual_volume DOUBLE,
    absolute_error DOUBLE,
    signed_error DOUBLE,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


DuckLakeLoadMode = Literal["explicit_local", "development_repository"]


class DuckLakeDetails(TypedDict):
    duckdb_version: str
    ducklake_extension_version: str
    ducklake_install_mode: str
    ducklake_installed_from: str
    catalog_type: str
    catalog_path: str
    data_path: str
    load_mode: DuckLakeLoadMode


def _load_ducklake(
    con: duckdb.DuckDBPyConnection,
    extension: Path | None,
    *,
    require_offline: bool,
) -> DuckLakeLoadMode:
    if extension is not None:
        if not extension.is_file():
            raise FileNotFoundError(f"DuckLake extension not found: {extension}")
        # An explicit LOAD is the portable contract. It must never fall back to
        # DuckDB's extension repository when the bundled artifact is invalid.
        con.execute(f"LOAD '{_sql_path(extension)}'")
        return "explicit_local"
    if require_offline:
        raise RuntimeError("offline DuckLake mode requires an explicit --ducklake-extension path")
    # Development-only path. Portable releases always provide the local binary.
    con.execute("INSTALL ducklake")
    con.execute("LOAD ducklake")
    return "development_repository"


def describe(
    con: duckdb.DuckDBPyConnection,
    settings: LakehouseSettings,
    load_mode: DuckLakeLoadMode,
) -> DuckLakeDetails:
    row = con.execute(
        """
        SELECT extension_version, install_mode, installed_from
        FROM duckdb_extensions()
        WHERE extension_name = 'ducklake' AND loaded
        """
    ).fetchone()
    if row is None:
        raise RuntimeError("DuckLake extension did not report a loaded version")
    return {
        "duckdb_version": duckdb.__version__,
        "ducklake_extension_version": str(row[0]),
        "ducklake_install_mode": str(row[1]),
        "ducklake_installed_from": str(row[2]),
        "catalog_type": "duckdb",
        "catalog_path": str(settings.ducklake_catalog_path.resolve()),
        "data_path": str(settings.ducklake_data_path.resolve()),
        "load_mode": load_mode,
    }


@contextmanager
def connect(
    settings: LakehouseSettings,
    *,
    require_offline: bool = False,
) -> Generator[duckdb.DuckDBPyConnection]:
    settings.ducklake_catalog_path.parent.mkdir(parents=True, exist_ok=True)
    settings.ducklake_data_path.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=":memory:")
    try:
        con.execute("SET autoinstall_known_extensions = false")
        con.execute("SET autoload_known_extensions = false")
        _load_ducklake(
            con,
            settings.ducklake_extension,
            require_offline=require_offline,
        )
        catalog = _sql_path(settings.ducklake_catalog_path)
        data_path = _sql_path(settings.ducklake_data_path)
        con.execute(f"ATTACH 'ducklake:{catalog}' AS lake (DATA_PATH '{data_path}')")
        con.execute("USE lake")
        yield con
    finally:
        con.close()


def initialize(settings: LakehouseSettings, *, require_offline: bool = False) -> None:
    with connect(settings, require_offline=require_offline) as con:
        con.execute(LAKE_SCHEMA)
        con.execute("CALL lake.set_option('parquet_compression', 'zstd')")
