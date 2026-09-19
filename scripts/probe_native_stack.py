"""Exercise native/heavy dependencies and emit machine-readable size evidence."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import sys
import tempfile
from pathlib import Path

import duckdb
import hierarchicalforecast
import mlforecast
import numpy as np
import openpyxl
import ortools
import polars as pl
import statsforecast
import xgboost
import xlsxwriter
from ortools.sat.python import cp_model
from statsforecast.models import Naive


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _distribution_size(name: str) -> int | None:
    try:
        distribution = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        return None
    return sum(
        distribution.locate_file(file).stat().st_size
        for file in distribution.files or ()
        if distribution.locate_file(file).is_file()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args()

    if duckdb.sql("SELECT sum(i) FROM range(4) values(i)").fetchone() != (6,):
        raise RuntimeError("DuckDB arithmetic probe failed")

    if pl.DataFrame({"value": [1, 2, 3]}).select(pl.col("value").sum()).item() != 6:
        raise RuntimeError("Polars arithmetic probe failed")

    forecast = Naive().forecast(y=np.array([1.0, 2.0, 3.0]), h=2)["mean"]
    if forecast.tolist() != [3.0, 3.0]:
        raise RuntimeError(f"StatsForecast probe failed: {forecast!r}")

    regressor = xgboost.XGBRegressor(n_estimators=2, max_depth=2, n_jobs=1)
    regressor.fit(np.array([[0.0], [1.0], [2.0], [3.0]]), np.array([0.0, 1.0, 2.0, 3.0]))
    prediction = float(regressor.predict(np.array([[1.5]]))[0])
    if not math.isfinite(prediction):
        raise RuntimeError("XGBoost probe returned a non-finite prediction")

    model = cp_model.CpModel()
    value = model.new_int_var(0, 10, "value")
    model.add(value == 7)
    solver = cp_model.CpSolver()
    if solver.solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("OR-Tools probe found no feasible solution")
    if solver.value(value) != 7:
        raise RuntimeError("OR-Tools probe returned the wrong solution")

    with tempfile.TemporaryDirectory(prefix="wfmhub2-report-probe-") as temporary:
        workbook_path = Path(temporary) / "probe.xlsx"
        workbook = xlsxwriter.Workbook(workbook_path)
        worksheet = workbook.add_worksheet("Evidence")
        worksheet.write(0, 0, "WFMHub")
        workbook.close()
        loaded_workbook = openpyxl.load_workbook(workbook_path, read_only=True)
        if loaded_workbook["Evidence"]["A1"].value != "WFMHub":
            raise RuntimeError("Excel round-trip probe failed")
        loaded_workbook.close()

    evidence: dict[str, object] = {
        "python": sys.version.split()[0],
        "environment_bytes": _directory_size(Path(sys.prefix)),
        "heavy_distribution_bytes": {
            name: _distribution_size(name)
            for name in (
                "hierarchicalforecast",
                "mlforecast",
                "numpy",
                "nvidia-nccl-cu13",
                "ortools",
                "pandas",
                "polars-runtime-32",
                "pyarrow",
                "scipy",
                "statsforecast",
                "xgboost",
            )
        },
        "libraries": {
            "duckdb": duckdb.__version__,
            "hierarchicalforecast": hierarchicalforecast.__version__,
            "mlforecast": mlforecast.__version__,
            "ortools": ortools.__version__,
            "polars": pl.__version__,
            "statsforecast": statsforecast.__version__,
            "xgboost": xgboost.__version__,
        },
        "operations": {
            "duckdb": "pass",
            "excel_round_trip": "pass",
            "forecast": "pass",
            "ortools": "pass",
            "polars": "pass",
            "xgboost": "pass",
        },
    }

    serialized = json.dumps(evidence, indent=2, sort_keys=True)
    print(serialized)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(f"{serialized}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
