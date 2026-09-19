from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from wfmhub2.core.settings import Settings


@dataclass(frozen=True)
class ProbeError:
    type: str
    message: str


@dataclass(frozen=True)
class ProbeCheck:
    name: str
    status: str
    details: dict[str, object] | None = None
    error: ProbeError | None = None


@dataclass(frozen=True)
class DoctorReport:
    status: str
    mode: str
    settings: dict[str, object]
    checks: tuple[ProbeCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _settings_details(settings: Settings) -> dict[str, object]:
    return {
        "home": str(settings.home.resolve()),
        "control_db_path": str(settings.control_db_path.resolve()),
        "ducklake_extension": (
            str(settings.ducklake_extension.resolve())
            if settings.ducklake_extension is not None
            else None
        ),
        "ducklake_catalog_path": str(settings.ducklake_catalog_path.resolve()),
        "ducklake_data_path": str(settings.ducklake_data_path.resolve()),
    }


def _run_check(name: str, operation: Callable[[], dict[str, object]]) -> ProbeCheck:
    try:
        return ProbeCheck(name=name, status="pass", details=operation())
    except Exception as exc:  # The doctor must report every failed gate, not crash at the first.
        return ProbeCheck(
            name=name,
            status="fail",
            error=ProbeError(type=type(exc).__name__, message=str(exc)),
        )


def _probe_portable_paths(settings: Settings) -> dict[str, object]:
    directories = (
        settings.data_dir,
        settings.inbox_dir,
        settings.exports_dir,
        settings.lake_dir,
        settings.ducklake_data_path,
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=".wfmhub2-probe-",
            dir=directory,
            delete=False,
        ) as handle:
            probe_path = Path(handle.name)
            handle.write(b"wfmhub2-stack-probe")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            if probe_path.read_bytes() != b"wfmhub2-stack-probe":
                raise OSError(f"portable path read-back failed: {directory}")
        finally:
            probe_path.unlink(missing_ok=True)

    return {
        "writable": True,
        "directories": [str(path.resolve()) for path in directories],
    }


def _probe_sqlite(settings: Settings) -> dict[str, object]:
    from wfmhub2.storage.sqlite import connect, initialize

    initialize(settings.control_db_path)
    with connect(settings.control_db_path) as conn:
        conn.execute(
            """
            INSERT INTO system_probe(probe_key, probe_value)
            VALUES ('doctor', 'write-read-reopen')
            ON CONFLICT(probe_key) DO UPDATE SET probe_value = excluded.probe_value
            """
        )

    with connect(settings.control_db_path) as reopened:
        row = reopened.execute(
            "SELECT probe_value FROM system_probe WHERE probe_key = 'doctor'"
        ).fetchone()
    if row is None or row[0] != "write-read-reopen":
        raise RuntimeError("SQLite value did not survive connection reopen")

    return {
        "database_path": str(settings.control_db_path.resolve()),
        "journal_mode": "wal",
        "reopen_verified": True,
    }


def _probe_ducklake(settings: Settings, *, require_offline: bool) -> dict[str, object]:
    from wfmhub2.storage.lakehouse import DuckLakeLoadMode, connect, describe

    before = {path.resolve() for path in settings.ducklake_data_path.rglob("*.parquet")}
    load_mode: DuckLakeLoadMode = (
        "explicit_local" if settings.ducklake_extension is not None else "development_repository"
    )

    with connect(settings, require_offline=require_offline) as con:
        con.execute("CALL lake.set_option('parquet_compression', 'zstd')")
        # A tiny DuckLake table can be inlined into catalog metadata. Disable
        # inlining so this is a real managed-Parquet qualification gate.
        con.execute("CALL lake.set_option('data_inlining_row_limit', '0')")
        con.execute("CREATE SCHEMA IF NOT EXISTS lake.wfmhub_system")
        con.execute("DROP TABLE IF EXISTS lake.wfmhub_system.stack_probe")
        con.execute(
            """
            CREATE TABLE lake.wfmhub_system.stack_probe AS
            SELECT i::INTEGER AS probe_id, (i * 2)::INTEGER AS probe_value
            FROM range(100) AS probe(i)
            """
        )
        row = con.execute(
            "SELECT count(*), sum(probe_value) FROM lake.wfmhub_system.stack_probe"
        ).fetchone()
        details = describe(con, settings, load_mode)

    if row is None or row[0] != 100 or row[1] != 9900:
        raise RuntimeError("DuckLake write/read returned unexpected probe values")

    after = {path.resolve() for path in settings.ducklake_data_path.rglob("*.parquet")}
    created = after - before
    if not after:
        raise RuntimeError("DuckLake probe did not create a managed Parquet file")
    if not created:
        raise RuntimeError("DuckLake probe did not create a new managed Parquet file")

    with connect(settings, require_offline=require_offline) as reopened:
        reopened_row = reopened.execute(
            "SELECT count(*), sum(probe_value) FROM lake.wfmhub_system.stack_probe"
        ).fetchone()
    if reopened_row is None or reopened_row[0] != 100 or reopened_row[1] != 9900:
        raise RuntimeError("DuckLake data did not survive catalog reopen")

    return {
        **details,
        "data_inlining_row_limit": 0,
        "parquet_compression": "zstd",
        "parquet_files_created": len(created),
        "reopen_verified": True,
    }


def _probe_polars() -> dict[str, object]:
    import polars as pl

    result = pl.DataFrame({"value": [1, 2, 3]}).select(pl.col("value").sum()).item()
    if result != 6:
        raise RuntimeError("Polars aggregation returned an unexpected value")
    return {"version": pl.__version__, "operation": "sum", "result": result}


def _probe_statsforecast() -> dict[str, object]:
    import numpy as np
    import statsforecast
    from numpy.typing import NDArray
    from statsforecast.models import Naive

    result = cast(
        dict[str, NDArray[np.float64]],
        Naive().forecast(y=np.asarray([1.0, 2.0, 3.0]), h=1),
    )
    forecast = float(result["mean"][0])
    if forecast != 3.0:
        raise RuntimeError("StatsForecast naive forecast returned an unexpected value")
    return {
        "version": statsforecast.__version__,
        "operation": "naive_forecast",
        "result": forecast,
    }


def _probe_xgboost() -> dict[str, object]:
    import xgboost as xgb

    train = xgb.DMatrix([[0.0], [1.0], [2.0]], label=[0.0, 1.0, 2.0])
    model = xgb.train(
        {"max_depth": 1, "objective": "reg:squarederror", "nthread": 1},
        train,
        num_boost_round=1,
    )
    prediction = float(model.predict(xgb.DMatrix([[1.0]]))[0])
    return {
        "version": xgb.__version__,
        "operation": "one_round_regression",
        "prediction": prediction,
    }


def _probe_ortools() -> dict[str, object]:
    import ortools  # pyright: ignore[reportMissingTypeStubs]
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    selected = model.new_bool_var("selected")
    model.add(selected == 1)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE) or solver.value(selected) != 1:
        raise RuntimeError("OR-Tools did not solve the deterministic probe model")
    return {
        "version": ortools.__version__,
        "operation": "cp_sat",
        "solver_status": solver.status_name(status),
    }


def run_doctor(
    settings: Settings,
    *,
    require_offline: bool,
    full: bool = False,
) -> DoctorReport:
    checks = [
        _run_check("portable_paths", lambda: _probe_portable_paths(settings)),
        _run_check("sqlite", lambda: _probe_sqlite(settings)),
        _run_check(
            "ducklake",
            lambda: _probe_ducklake(settings, require_offline=require_offline),
        ),
    ]
    if full:
        checks.extend(
            (
                _run_check("polars", _probe_polars),
                _run_check("statsforecast", _probe_statsforecast),
                _run_check("xgboost", _probe_xgboost),
                _run_check("ortools", _probe_ortools),
            )
        )
    status = "ok" if all(check.status == "pass" for check in checks) else "failed"
    return DoctorReport(
        status=status,
        mode="offline" if require_offline else "development",
        settings=_settings_details(settings),
        checks=tuple(checks),
    )
