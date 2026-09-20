from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, cast


class DoctorSettings(Protocol):
    @property
    def home(self) -> Path: ...

    @property
    def ducklake_extension(self) -> Path | None: ...

    @property
    def data_dir(self) -> Path: ...

    @property
    def control_db_path(self) -> Path: ...

    @property
    def inbox_dir(self) -> Path: ...

    @property
    def exports_dir(self) -> Path: ...

    @property
    def lake_dir(self) -> Path: ...

    @property
    def ducklake_catalog_path(self) -> Path: ...

    @property
    def ducklake_data_path(self) -> Path: ...


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


def _run_check(name: str, operation: Callable[[], dict[str, object]]) -> ProbeCheck:
    try:
        return ProbeCheck(name=name, status="pass", details=operation())
    except Exception as exc:  # The doctor must report every failed gate, not crash at the first.
        return ProbeCheck(
            name=name,
            status="fail",
            error=ProbeError(type=type(exc).__name__, message=str(exc)),
        )


def _probe_portable_paths(settings: DoctorSettings) -> dict[str, object]:
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


def _probe_runtime_isolation() -> dict[str, object]:
    if sys.flags.isolated != 1:
        raise RuntimeError("doctor child is not running in Python isolated mode")
    if os.environ.get("PYTHONHOME") or os.environ.get("PYTHONPATH"):
        raise RuntimeError("machine Python environment variables leaked into the doctor")
    return {
        "executable": str(Path(sys.executable).resolve()),
        "isolated": True,
        "path": tuple(sys.path),
        "python_version": sys.version.split()[0],
    }


def _probe_sqlite(settings: DoctorSettings) -> dict[str, object]:
    from wfmhub2.storage.sqlite import connect, initialize

    initialize(settings.control_db_path)
    with connect(settings.control_db_path) as conn:
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        if journal_mode != "wal":
            raise RuntimeError(f"SQLite journal mode is {journal_mode!r}, expected 'wal'")
        conn.execute(
            """
            INSERT INTO system_probe(probe_key, probe_value)
            VALUES ('doctor', 'write-read-reopen')
            ON CONFLICT(probe_key) DO UPDATE SET probe_value = excluded.probe_value
            """
        )

    try:
        with connect(settings.control_db_path) as conn:
            conn.execute(
                "INSERT INTO system_probe(probe_key, probe_value) VALUES (?, ?)",
                ("doctor-rollback", "must-not-commit"),
            )
            raise RuntimeError("exercise transaction rollback")
    except RuntimeError as exc:
        if str(exc) != "exercise transaction rollback":
            raise

    with connect(settings.control_db_path) as reopened:
        row = reopened.execute(
            "SELECT probe_value FROM system_probe WHERE probe_key = 'doctor'"
        ).fetchone()
        rolled_back = reopened.execute(
            "SELECT probe_value FROM system_probe WHERE probe_key = 'doctor-rollback'"
        ).fetchone()
        quick_check = str(reopened.execute("PRAGMA quick_check").fetchone()[0])
    if row is None or row[0] != "write-read-reopen":
        raise RuntimeError("SQLite value did not survive connection reopen")
    if rolled_back is not None:
        raise RuntimeError("SQLite transaction rollback did not preserve the prior state")
    if quick_check != "ok":
        raise RuntimeError(f"SQLite quick_check failed: {quick_check}")

    with tempfile.TemporaryDirectory(prefix="wfmhub2-sqlite-probe-") as folder:
        backup_path = Path(folder) / "control-backup.sqlite"
        with connect(settings.control_db_path) as source, sqlite3.connect(backup_path) as backup:
            source.backup(backup)
        with sqlite3.connect(backup_path) as backup:
            backup_row = backup.execute(
                "SELECT probe_value FROM system_probe WHERE probe_key = 'doctor'"
            ).fetchone()
            backup_check = str(backup.execute("PRAGMA quick_check").fetchone()[0])
    if backup_row is None or backup_row[0] != "write-read-reopen" or backup_check != "ok":
        raise RuntimeError("SQLite online backup did not pass reopen/quick_check")

    return {
        "database_path": str(settings.control_db_path.resolve()),
        "backup_verified": True,
        "journal_mode": journal_mode,
        "quick_check": quick_check,
        "reopen_verified": True,
        "rollback_verified": True,
    }


def _probe_ducklake(settings: DoctorSettings, *, require_offline: bool) -> dict[str, object]:
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

    parsed = pl.DataFrame(
        {
            "queue": ["sales", "sales", "service"],
            "offered": ["10", "12", "7"],
        }
    ).with_columns(pl.col("offered").cast(pl.Int64))
    grouped = parsed.group_by("queue").agg(pl.col("offered").sum()).sort("queue")
    result = dict(zip(grouped["queue"].to_list(), grouped["offered"].to_list(), strict=True))
    if result != {"sales": 22, "service": 7}:
        raise RuntimeError("Polars parse/group transform returned unexpected values")
    return {"version": pl.__version__, "operation": "parse_group_sum", "result": result}


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


def _probe_api_runtime() -> dict[str, object]:
    import fastapi
    import pydantic
    import uvicorn

    class BoundaryProbe(pydantic.BaseModel):
        value: int

    validated = BoundaryProbe.model_validate({"value": "42"})
    if validated.value != 42:
        raise RuntimeError("Pydantic boundary validation returned an unexpected value")
    try:
        BoundaryProbe.model_validate({"value": "not-an-integer"})
    except pydantic.ValidationError:
        rejected_invalid = True
    else:
        raise RuntimeError("Pydantic accepted an invalid boundary value")
    return {
        "fastapi_version": fastapi.__version__,
        "pydantic_version": pydantic.__version__,
        "uvicorn_version": uvicorn.__version__,
        "operation": "pydantic_boundary_validation",
        "rejected_invalid": rejected_invalid,
        "result": validated.value,
    }


def _probe_mlforecast() -> dict[str, object]:
    import mlforecast
    import polars as pl
    from mlforecast import MLForecast
    from sklearn.linear_model import LinearRegression  # pyright: ignore[reportMissingTypeStubs]

    observations = pl.DataFrame(
        {
            "unique_id": ["probe"] * 8,
            "ds": list(range(1, 9)),
            "y": [10.0, 11.0, 13.0, 16.0, 20.0, 25.0, 31.0, 38.0],
        }
    )
    forecast_engine = MLForecast(
        models={"linear": LinearRegression()},
        freq=1,
        lags=[1, 2],
    )
    forecast_engine.fit(observations)  # pyright: ignore[reportArgumentType]
    prediction = cast(
        pl.DataFrame,
        forecast_engine.predict(2),  # pyright: ignore[reportUnknownMemberType]
    )
    if prediction.height != 2:
        raise RuntimeError("MLForecast did not return the expected forecast frame")
    values = cast(list[float], prediction.get_column("linear").to_list())
    if not all(value > 38.0 for value in values):
        raise RuntimeError("MLForecast fit/predict returned unexpected values")
    return {
        "version": mlforecast.__version__,
        "operation": "linear_fit_predict",
        "predictions": values,
    }


def _probe_hierarchicalforecast() -> dict[str, object]:
    import hierarchicalforecast  # pyright: ignore[reportMissingTypeStubs]
    import polars as pl
    from hierarchicalforecast.core import (  # pyright: ignore[reportMissingTypeStubs]
        HierarchicalReconciliation,
    )
    from hierarchicalforecast.methods import BottomUp  # pyright: ignore[reportMissingTypeStubs]
    from hierarchicalforecast.utils import (  # pyright: ignore[reportMissingTypeStubs]
        aggregate,  # pyright: ignore[reportUnknownVariableType]
    )

    hierarchy_aggregate = cast(  # pyright: ignore[reportUnknownVariableType]
        Callable[
            [pl.DataFrame, list[list[str]]],
            tuple[pl.DataFrame, pl.DataFrame, dict[str, object]],
        ],
        aggregate,
    )

    bottom_level = pl.DataFrame(
        {
            "region": ["north", "north", "south", "south"],
            "queue": ["a", "b", "a", "b"],
            "ds": [1, 1, 1, 1],
            "y": [1.0, 2.0, 3.0, 4.0],
        }
    )
    aggregated, summing_matrix, tags = hierarchy_aggregate(
        bottom_level,
        [["region"], ["region", "queue"]],
    )
    north_total = aggregated.filter(pl.col("unique_id") == "north").get_column("y").item()
    south_total = aggregated.filter(pl.col("unique_id") == "south").get_column("y").item()
    if (north_total, south_total) != (3.0, 7.0):
        raise RuntimeError("HierarchicalForecast aggregation returned unexpected totals")
    if summing_matrix.height != 6 or summing_matrix.width != 5:
        raise RuntimeError("HierarchicalForecast returned an unexpected summing matrix")
    reconciliation = HierarchicalReconciliation(reconcilers=[BottomUp()])
    reconcile = cast(  # pyright: ignore[reportUnknownVariableType]
        Callable[[pl.DataFrame, dict[str, object], pl.DataFrame], pl.DataFrame],
        reconciliation.reconcile,
    )
    reconciled = reconcile(aggregated.rename({"y": "base"}), tags, summing_matrix)
    reconciled_north = (
        reconciled.filter(pl.col("unique_id") == "north").get_column("base/BottomUp").item()
    )
    if reconciled_north != 3.0:
        raise RuntimeError("HierarchicalForecast reconciliation is not coherent")
    return {
        "version": hierarchicalforecast.__version__,
        "operation": "bottom_up_reconciliation",
        "levels": sorted(tags),
        "reconciled_north": reconciled_north,
        "series": aggregated.height,
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


def _probe_excel() -> dict[str, object]:
    import openpyxl
    import xlsxwriter  # pyright: ignore[reportMissingTypeStubs]

    with tempfile.TemporaryDirectory(prefix="wfmhub2-excel-probe-") as folder:
        workbook_path = Path(folder) / "roundtrip.xlsx"
        with xlsxwriter.Workbook(workbook_path) as writer:
            sheet = writer.add_worksheet("Probe")  # pyright: ignore[reportUnknownMemberType]
            sheet.write_string(0, 0, "wfmhub2")
            sheet.write_number(0, 1, 42)

        reader = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
        try:
            sheet = reader["Probe"]
            marker = sheet["A1"].value
            value = sheet["B1"].value
        finally:
            reader.close()

    if marker != "wfmhub2" or value != 42:
        raise RuntimeError("Excel write/read round-trip returned unexpected values")
    return {
        "openpyxl_version": openpyxl.__version__,
        "xlsxwriter_version": xlsxwriter.__version__,
        "operation": "xlsxwriter_write_openpyxl_read",
        "roundtrip_verified": True,
    }


CORE_PROBE_NAMES = (
    "portable_paths",
    "runtime_isolation",
    "api_runtime",
    "sqlite",
    "ducklake",
)
FULL_PROBE_NAMES = (
    "polars",
    "statsforecast",
    "mlforecast",
    "hierarchicalforecast",
    "xgboost",
    "ortools",
    "excel",
)


def probe_names(*, full: bool) -> tuple[str, ...]:
    return CORE_PROBE_NAMES + (FULL_PROBE_NAMES if full else ())


def run_named_probe(
    name: str,
    settings: DoctorSettings,
    *,
    require_offline: bool,
) -> ProbeCheck:
    operations: dict[str, Callable[[], dict[str, object]]] = {
        "portable_paths": lambda: _probe_portable_paths(settings),
        "runtime_isolation": _probe_runtime_isolation,
        "api_runtime": _probe_api_runtime,
        "sqlite": lambda: _probe_sqlite(settings),
        "ducklake": lambda: _probe_ducklake(settings, require_offline=require_offline),
        "polars": _probe_polars,
        "statsforecast": _probe_statsforecast,
        "mlforecast": _probe_mlforecast,
        "hierarchicalforecast": _probe_hierarchicalforecast,
        "xgboost": _probe_xgboost,
        "ortools": _probe_ortools,
        "excel": _probe_excel,
    }
    try:
        operation = operations[name]
    except KeyError as exc:
        raise ValueError(f"unknown doctor probe: {name}") from exc
    return _run_check(name, operation)


def run_doctor(
    settings: DoctorSettings,
    *,
    require_offline: bool,
    full: bool = False,
) -> DoctorReport:
    # Import only the stdlib supervisor here. Every capability is executed in a
    # fresh child so a native loader crash cannot suppress the remaining checks.
    from wfmhub2.portable_doctor import run_supervised_doctor

    return run_supervised_doctor(
        settings,
        require_offline=require_offline,
        full=full,
    )
