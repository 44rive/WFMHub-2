from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wfmhub2_compat.storage import initialize_database

REQUIRED_BROWSER_ASSETS = (
    "index.html",
    "vendor/pyodide/pyodide.mjs",
    "vendor/pyodide/pyodide.asm.wasm",
    "vendor/pyodide/python_stdlib.zip",
    "vendor/pyodide/pyodide-lock.json",
    "vendor/pyodide/PYODIDE_ASSETS.sha256",
)


def _excel_probe() -> dict[str, object]:
    import openpyxl

    xlsxwriter: Any = __import__("xlsxwriter")

    with tempfile.TemporaryDirectory(prefix="wfmhub2-compat-excel-") as raw:
        path = Path(raw) / "probe.xlsx"
        workbook = xlsxwriter.Workbook(path)
        worksheet = workbook.add_worksheet("Probe")
        worksheet.write(0, 0, "WFMHub")
        worksheet.write_number(0, 1, 42)
        workbook.close()
        with zipfile.ZipFile(path) as archive:
            if "xl/workbook.xml" not in archive.namelist():
                raise RuntimeError("generated XLSX is missing xl/workbook.xml")
        loaded = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            value = loaded["Probe"]["B1"].value
        finally:
            loaded.close()
        if value != 42:
            raise RuntimeError(f"Excel round-trip returned {value!r}")
    return {
        "openpyxl": openpyxl.__version__,
        "xlsxwriter": xlsxwriter.__version__,
    }


def run(home: Path) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def check(name: str, operation: Callable[[], dict[str, object]]) -> None:
        try:
            details = operation()
            checks.append({"name": name, "status": "pass", "details": details})
        except Exception as exc:
            checks.append(
                {
                    "name": name,
                    "status": "fail",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            )

    def paths() -> dict[str, object]:
        expected_app = (home / "_system" / "app").resolve()
        resolved_paths = [Path(value).resolve() for value in sys.path if value]
        if expected_app not in resolved_paths:
            raise RuntimeError("embedded runtime does not expose only the packaged app path")
        if os.environ.get("PYTHONHOME") or os.environ.get("PYTHONPATH"):
            raise RuntimeError("machine Python environment leaked into the portable runtime")
        return {"python": sys.version.split()[0], "isolated": sys.flags.isolated == 1}

    def sqlite_probe() -> dict[str, object]:
        path = home / "data" / "control.sqlite"
        initialize_database(path)
        with sqlite3.connect(path) as connection:
            journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
            quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        if str(journal).lower() != "wal" or quick_check != "ok":
            raise RuntimeError(f"unexpected SQLite state: journal={journal}, check={quick_check}")
        return {"sqlite": sqlite3.sqlite_version, "journalMode": journal}

    def browser_assets() -> dict[str, object]:
        web = home / "_system" / "web"
        missing = [name for name in REQUIRED_BROWSER_ASSETS if not (web / name).is_file()]
        if missing:
            raise FileNotFoundError(f"missing browser assets: {missing}")
        return {"requiredAssets": len(REQUIRED_BROWSER_ASSETS)}

    check("portable_paths", paths)
    check("sqlite", sqlite_probe)
    check("excel", _excel_probe)
    check("browser_assets", browser_assets)
    return {
        "status": "pass" if all(item["status"] == "pass" for item in checks) else "fail",
        "mode": "host",
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run(args.home.resolve())
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print(f"WFMHub 2 hybrid host doctor: {report['status']}")
        for item in report["checks"]:  # type: ignore[union-attr]
            print(f"  {item['name']}: {item['status']}")
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
