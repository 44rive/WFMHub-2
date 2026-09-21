"""Exercise packaged pure-Python RTA refresh with synthetic local sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path

from openpyxl import Workbook

from wfmhub2_compat.rta_refresh import RefreshFailedError, RtaRefreshCoordinator
from wfmhub2_compat.setup import configure_source_root


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portable-root", type=Path, required=True)
    args = parser.parse_args()
    if not (args.portable_root / "SETUP.cmd").is_file():
        raise RuntimeError("portable package is missing SETUP.cmd")

    with tempfile.TemporaryDirectory(prefix="wfmhub2-rta-smoke-") as raw:
        test_root = Path(raw)
        home = test_root / "portable home"
        sources = test_root / "existing WFM Database"
        roster = sources / "FTE/FTE Count.xlsx"
        roster.parent.mkdir(parents=True)
        workbook = Workbook()
        sheet = workbook.active
        if sheet is None:
            raise RuntimeError("workbook has no active sheet")
        sheet.title = "Agent"
        sheet.append(["Client ID", "Status", "Name", "FTE", "End date if leaver"])
        sheet.append(["00123", "Active", "Ada Agent", 1, None])
        workbook.save(roster)
        workbook.close()
        schedule = sources / "Verint/Schedules & Activities/StartEndTimes.txt"
        schedule.parent.mkdir(parents=True)
        with schedule.open("w", encoding="cp1252", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t")
            writer.writerow(
                ["Name", "Data Source IDs", *(f"07/{day:02d}/2026" for day in range(1, 32)), ""]
            )
            writer.writerow(["Ada Agent", "00123", *(["Off"] * 31), ""])

        source_hashes = (_sha256(roster), _sha256(schedule))
        configure_source_root(home, sources)
        coordinator = RtaRefreshCoordinator(home)
        result = coordinator.refresh()
        health = coordinator.source_health()
        if result["status"] != "succeeded" or health["status"] != "ready":
            raise RuntimeError("packaged source refresh did not publish a ready cut")
        if health["sources"]["roster"]["agentCount"] != 1:
            raise RuntimeError("packaged roster fact count was incorrect")
        if health["sources"]["schedule"]["shiftCount"] != 31:
            raise RuntimeError("packaged schedule fact count was incorrect")
        if health["sources"]["schedule"]["minDate"] != "2026-07-01":
            raise RuntimeError("packaged schedule lost the first July date")
        if health["sources"]["schedule"]["maxDate"] != "2026-07-31":
            raise RuntimeError("packaged schedule lost the last July date")
        if str(sources) in json.dumps(health):
            raise RuntimeError("source-health response leaked the local folder path")
        if source_hashes != (_sha256(roster), _sha256(schedule)):
            raise RuntimeError("source refresh modified the input files")

        with schedule.open("w", encoding="cp1252", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t")
            writer.writerow(
                ["Name", "Data Source IDs", *(f"07/{day:02d}/2026" for day in range(1, 32)), ""]
            )
            writer.writerow(["Ada Agent", "00123", "not an interval", *(["Off"] * 30), ""])
        active_id = health["activeGenerationId"]
        try:
            coordinator.refresh()
        except RefreshFailedError as exc:
            if exc.code != "BLOCKING_SOURCE_QUALITY":
                raise RuntimeError(f"unexpected refresh failure: {exc.code}") from exc
        else:
            raise RuntimeError("invalid source was incorrectly published")
        if coordinator.source_health()["activeGenerationId"] != active_id:
            raise RuntimeError("failed refresh replaced the previous active cut")
        print("WFMHUB2_RTA_SOURCE_SMOKE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
