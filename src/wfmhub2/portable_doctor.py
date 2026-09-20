"""Standard-library supervisor for portable compatibility diagnostics.

This module must stay importable when any third-party native module is blocked.
Each capability runs in a fresh child of the same Python executable so a DLL
loader failure or native crash is reported without suppressing later probes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wfmhub2.doctor import DoctorReport, DoctorSettings, ProbeCheck

PROBE_PREFIX = "WFMHUB2_PROBE "
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
DEFAULT_PROBE_TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class PortableSettings:
    home: Path
    ducklake_extension: Path | None = None

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def control_db_path(self) -> Path:
        return self.data_dir / "control.sqlite"

    @property
    def inbox_dir(self) -> Path:
        return self.home / "Feed"

    @property
    def exports_dir(self) -> Path:
        return self.home / "Reports"

    @property
    def lake_dir(self) -> Path:
        return self.data_dir / "lake"

    @property
    def ducklake_catalog_path(self) -> Path:
        return self.lake_dir / "catalog.ducklake"

    @property
    def ducklake_data_path(self) -> Path:
        return self.lake_dir / "files"


def _probe_names(*, full: bool) -> tuple[str, ...]:
    return CORE_PROBE_NAMES + (FULL_PROBE_NAMES if full else ())


def _settings_arguments(settings: DoctorSettings) -> list[str]:
    arguments = ["--home", str(settings.home.resolve())]
    if settings.ducklake_extension is not None:
        arguments.extend(("--ducklake-extension", str(settings.ducklake_extension.resolve())))
    return arguments


def _child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    return environment


def _failure_check(name: str, error_type: str, message: str) -> ProbeCheck:
    from wfmhub2.doctor import ProbeCheck, ProbeError

    return ProbeCheck(
        name=name,
        status="fail",
        error=ProbeError(type=error_type, message=message),
    )


def _decode_probe(name: str, stdout: str) -> ProbeCheck:
    from wfmhub2.doctor import ProbeCheck, ProbeError

    payload_line = next(
        (
            line.removeprefix(PROBE_PREFIX)
            for line in reversed(stdout.splitlines())
            if line.startswith(PROBE_PREFIX)
        ),
        None,
    )
    if payload_line is None:
        return _failure_check(name, "ProbeProtocolError", "child emitted no probe result")
    try:
        decoded: object = json.loads(payload_line)
        if not isinstance(decoded, dict):
            raise TypeError("child result is not an object")
        value = cast(dict[str, object], decoded)
        raw_error = value.get("error")
        if raw_error is None:
            error = None
        elif isinstance(raw_error, dict):
            error_value = cast(dict[str, object], raw_error)
            error = ProbeError(
                type=str(error_value["type"]),
                message=str(error_value["message"]),
            )
        else:
            raise TypeError("child error is not an object")
        raw_details = value.get("details")
        details = cast(dict[str, object], raw_details) if isinstance(raw_details, dict) else None
        return ProbeCheck(
            name=str(value["name"]),
            status=str(value["status"]),
            details=details if isinstance(details, dict) else None,
            error=error,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return _failure_check(name, "ProbeProtocolError", f"invalid child result: {exc}")


def _run_child_probe(
    name: str,
    settings: DoctorSettings,
    *,
    require_offline: bool,
    timeout_seconds: int,
) -> ProbeCheck:
    command = [
        sys.executable,
        "-I",
        "-m",
        "wfmhub2.portable_doctor",
        *_settings_arguments(settings),
        "--probe",
        name,
    ]
    if require_offline:
        command.append("--require-offline")
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_child_environment(),
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return _failure_check(
            name,
            "ProbeTimeout",
            f"probe exceeded {timeout_seconds} seconds",
        )
    check = _decode_probe(name, completed.stdout)
    if (
        completed.returncode != 0
        and check.error is not None
        and check.error.type == "ProbeProtocolError"
    ):
        diagnostic = completed.stderr.strip()
        suffix = f"; stderr: {diagnostic[-1000:]}" if diagnostic else ""
        return _failure_check(
            name,
            "ProbeProcessError",
            (
                f"child exited with code {completed.returncode} before reporting; "
                "check Windows Code Integrity/AppLocker logs for a blocked native file"
                f"{suffix}"
            ),
        )
    if completed.returncode != 0 and check.status == "pass":
        return _failure_check(
            name,
            "ProbeProcessError",
            f"child exited with code {completed.returncode}",
        )
    if completed.returncode != 0 and check.error is not None:
        diagnostic = completed.stderr.strip()
        if diagnostic:
            return _failure_check(
                name,
                check.error.type,
                f"{check.error.message}; child stderr: {diagnostic[-1000:]}",
            )
    return check


def _settings_details(settings: DoctorSettings) -> dict[str, object]:
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


def run_supervised_doctor(
    settings: DoctorSettings,
    *,
    require_offline: bool,
    full: bool,
    timeout_seconds: int = DEFAULT_PROBE_TIMEOUT_SECONDS,
) -> DoctorReport:
    from wfmhub2.doctor import DoctorReport

    checks = tuple(
        _run_child_probe(
            name,
            settings,
            require_offline=require_offline,
            timeout_seconds=timeout_seconds,
        )
        for name in _probe_names(full=full)
    )
    return DoctorReport(
        status="ok" if all(check.status == "pass" for check in checks) else "failed",
        mode="offline" if require_offline else "development",
        settings=_settings_details(settings),
        checks=checks,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wfmhub2-doctor")
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--ducklake-extension", type=Path)
    parser.add_argument("--require-offline", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_PROBE_TIMEOUT_SECONDS)
    parser.add_argument("--probe", choices=CORE_PROBE_NAMES + FULL_PROBE_NAMES)
    return parser


def _print_human_report(report: DoctorReport) -> None:
    print(f"WFMHub 2 doctor: {report.status} ({report.mode})")
    for check in report.checks:
        suffix = ""
        if check.error is not None:
            suffix = f" - {check.error.type}: {check.error.message}"
        print(f"  {check.name}: {check.status}{suffix}")


def _run_one_probe(name: str, settings: PortableSettings, *, require_offline: bool) -> int:
    from wfmhub2.doctor import run_named_probe

    check = run_named_probe(name, settings, require_offline=require_offline)
    print(PROBE_PREFIX + json.dumps(asdict(check), sort_keys=True, separators=(",", ":")))
    return 0 if check.status == "pass" else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = PortableSettings(
        home=args.home.expanduser().resolve(),
        ducklake_extension=(
            args.ducklake_extension.expanduser().resolve()
            if args.ducklake_extension is not None
            else None
        ),
    )
    if args.probe is not None:
        return _run_one_probe(args.probe, settings, require_offline=args.require_offline)

    report = run_supervised_doctor(
        settings,
        require_offline=args.require_offline,
        full=args.full,
        timeout_seconds=args.timeout_seconds,
    )
    if args.json_output:
        print(json.dumps(asdict(report), sort_keys=True, separators=(",", ":")))
    else:
        _print_human_report(report)
    return 0 if report.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
