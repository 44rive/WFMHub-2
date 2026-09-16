from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import duckdb

from wfmhub2.core.settings import Settings


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


def _load_ducklake(con: duckdb.DuckDBPyConnection, extension: Path | None) -> None:
    if extension is not None:
        con.execute(f"LOAD '{_sql_path(extension)}'")
        return
    # Development path. Portable releases provide WFMHUB2_DUCKLAKE_EXTENSION
    # so no network access is required at runtime.
    con.execute("INSTALL ducklake")
    con.execute("LOAD ducklake")


@contextmanager
def connect(settings: Settings) -> Iterator[duckdb.DuckDBPyConnection]:
    settings.ducklake_catalog_path.parent.mkdir(parents=True, exist_ok=True)
    settings.ducklake_data_path.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=":memory:")
    try:
        _load_ducklake(con, settings.ducklake_extension)
        catalog = _sql_path(settings.ducklake_catalog_path)
        data_path = _sql_path(settings.ducklake_data_path)
        con.execute(
            f"ATTACH 'ducklake:{catalog}' AS lake (DATA_PATH '{data_path}')"
        )
        con.execute("USE lake")
        yield con
    finally:
        con.close()


def initialize(settings: Settings) -> None:
    with connect(settings) as con:
        con.execute(LAKE_SCHEMA)
        con.execute("CALL lake.set_option('parquet_compression', 'zstd')")
