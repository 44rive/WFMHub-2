from pathlib import Path

import duckdb


SCHEMA = """
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS intel;

CREATE TABLE IF NOT EXISTS core.interval_fact (
    business_date DATE NOT NULL,
    interval_start TIMESTAMP NOT NULL,
    service_scope VARCHAR NOT NULL,
    source_system VARCHAR NOT NULL,
    offered DOUBLE,
    handled DOUBLE,
    handle_seconds DOUBLE,
    scheduled_fte DOUBLE,
    present_fte DOUBLE,
    required_fte DOUBLE,
    service_level DOUBLE,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mart.staffing_interval (
    business_date DATE NOT NULL,
    interval_start TIMESTAMP NOT NULL,
    service_scope VARCHAR NOT NULL,
    required_fte DOUBLE,
    scheduled_fte DOUBLE,
    present_fte DOUBLE,
    effective_fte DOUBLE,
    staffing_gap DOUBLE,
    PRIMARY KEY (business_date, interval_start, service_scope)
);
"""


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as conn:
        conn.execute(SCHEMA)
