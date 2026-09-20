from pathlib import Path

from wfmhub2.core.settings import Settings
from wfmhub2.doctor import run_doctor


def test_offline_doctor_reports_missing_local_extension_without_network(
    tmp_path: Path,
) -> None:
    settings = Settings(home=tmp_path)
    report = run_doctor(settings, require_offline=True)

    assert report.status == "failed"
    assert report.mode == "offline"
    results = {check.name: check for check in report.checks}
    assert results["portable_paths"].status == "pass"
    assert results["runtime_isolation"].status == "pass"
    assert results["sqlite"].status == "pass"
    assert results["ducklake"].status == "fail"
    assert results["ducklake"].error is not None
    assert results["ducklake"].error.type == "RuntimeError"
    assert "explicit --ducklake-extension" in results["ducklake"].error.message


def test_full_doctor_reports_missing_capabilities_instead_of_crashing(
    tmp_path: Path,
) -> None:
    report = run_doctor(Settings(home=tmp_path), require_offline=True, full=True)

    assert report.status == "failed"
    assert [check.name for check in report.checks] == [
        "portable_paths",
        "runtime_isolation",
        "api_runtime",
        "sqlite",
        "ducklake",
        "polars",
        "pyarrow",
        "statsforecast",
        "mlforecast",
        "hierarchicalforecast",
        "clarabel",
        "xgboost",
        "ortools",
        "excel",
    ]
    assert all(check.status in {"pass", "fail"} for check in report.checks)
