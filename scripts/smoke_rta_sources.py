"""Exercise packaged pure-Python RTA refresh with synthetic local sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
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
            writer.writerow(
                [
                    "Ada Agent",
                    "00123",
                    ".ORG | Work 07/01/2026 8:00 AM-07/01/2026 4:00 PM",
                    *(["Off"] * 30),
                    "",
                ]
            )

        status = sources / "Storm/Agent Status/status.csv"
        status.parent.mkdir(parents=True)
        with status.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "[Serial Number]",
                    "[Status]",
                    "[Status Start Date and Time]",
                    "[Agent]",
                    "[Agent ID]",
                    "[Status Duration]",
                    "[Queue]",
                ]
            )
            writer.writerow(
                [
                    "1",
                    "Available",
                    "07/01/2026 08:00",
                    "Ada Agent",
                    "00123",
                    "00:30:00",
                    "Synthetic",
                ]
            )
        lilo = sources / "Storm/LILO/LILO_2026-07-01.csv"
        lilo.parent.mkdir(parents=True)
        with lilo.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["[Agent]", "[Agent ID]", "[First Log-on Time]", "[Last Log-off Time]"])
            writer.writerow(["Ada Agent", "00123", "07/01/2026 08:00", "07/01/2026 16:00"])

        calls = sources / "Storm/Call by Call/calls.csv"
        calls.parent.mkdir(parents=True)
        with calls.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "[Call Date/Time]",
                    "[Call End Date/Time]",
                    "[Call ID]",
                    "[Call Reference Number]",
                    "[Agent ID]",
                    "[Agent]",
                    "[Talk Time]",
                    "[Hold Time]",
                    "[Total Wrap Time]",
                    "[Call Direction]",
                    "[Total Queue Wait Time]",
                    "[Queue]",
                ]
            )
            writer.writerow(
                [
                    "07/01/2026 08:07",
                    "07/01/2026 08:10",
                    "call-1",
                    "ref-1",
                    "00123",
                    "Ada Agent",
                    "00:02:00",
                    "00:00:10",
                    "00:00:20",
                    "I",
                    "00:00:15",
                    "APBN_BRU_RSA_INTERNAT_All_FR",
                ]
            )

        source_hashes = (
            _sha256(roster),
            _sha256(schedule),
            _sha256(status),
            _sha256(lilo),
            _sha256(calls),
        )
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
        if health["sources"]["agentStatus"]["rowCount"] != 1:
            raise RuntimeError("packaged Agent Status fact count was incorrect")
        if health["sources"]["lilo"]["rowCount"] != 1:
            raise RuntimeError("packaged LILO fact count was incorrect")
        if health["sources"]["callByCall"]["canonicalLegCount"] != 1:
            raise RuntimeError("packaged Call-by-Call canonical count was incorrect")
        if health["sources"]["callByCall"]["serviceIntervalCount"] != 1:
            raise RuntimeError("packaged Call-by-Call interval count was incorrect")
        if health["sources"]["attendance"]["agentDayCount"] != 31:
            raise RuntimeError("packaged attendance agent-day count was incorrect")
        if health["sources"]["attendance"]["gapFragmentCount"] != 0:
            raise RuntimeError("packaged attendance gap count was incorrect")
        if health["sources"]["attendance"]["unknownCount"] != 0:
            raise RuntimeError("packaged attendance unexpectedly converted evidence to unknown")
        if str(sources) in json.dumps(health):
            raise RuntimeError("source-health response leaked the local folder path")
        if source_hashes != (
            _sha256(roster),
            _sha256(schedule),
            _sha256(status),
            _sha256(lilo),
            _sha256(calls),
        ):
            raise RuntimeError("source refresh modified the input files")

        repeated = coordinator.refresh()
        if repeated.get("unchanged") is not True:
            raise RuntimeError("unchanged packaged refresh did not take the no-op path")
        if repeated["generationId"] != result["generationId"]:
            raise RuntimeError("unchanged packaged refresh created another generation")

        with schedule.open("w", encoding="cp1252", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t")
            writer.writerow(
                ["Name", "Data Source IDs", *(f"07/{day:02d}/2026" for day in range(1, 32)), ""]
            )
            writer.writerow(
                [
                    "Ada Agent",
                    "00123",
                    ".ORG | Work 07/01/2026 9:00 AM-07/01/2026 5:00 PM",
                    *(["Off"] * 30),
                    "",
                ]
            )
        reused_cut = coordinator.refresh()
        reused_id = reused_cut["generationId"]
        if reused_id == result["generationId"]:
            raise RuntimeError("changed schedule did not create a new generation")
        reused_health = reused_cut["sourceHealth"]
        if reused_health["sources"]["attendance"]["agentDayCount"] != 31:
            raise RuntimeError("reused actuals did not rebuild attendance")
        if reused_health["sources"]["callByCall"]["canonicalLegCount"] != 1:
            raise RuntimeError("reused call rows did not rebuild canonical service")
        if reused_health["sources"]["callByCall"]["serviceIntervalCount"] != 1:
            raise RuntimeError("reused call rows did not rebuild service intervals")
        with sqlite3.connect(coordinator.store.path) as connection:
            owners = connection.execute(
                """
                SELECT source_type, bronze_generation_id FROM wfm_source_manifest
                WHERE generation_id = ?
                  AND source_type IN ('agent_status', 'lilo', 'call_by_call')
                ORDER BY source_type
                """,
                (reused_id,),
            ).fetchall()
            if owners != [
                ("agent_status", result["generationId"]),
                ("call_by_call", result["generationId"]),
                ("lilo", result["generationId"]),
            ]:
                raise RuntimeError("known event Bronze versions were not reused")
            for table in ("wfm_raw_agent_status", "wfm_raw_lilo", "wfm_raw_call_leg"):
                if connection.execute(
                    f"SELECT count(*) FROM {table} WHERE generation_id = ?", (reused_id,)
                ).fetchone() != (0,):
                    raise RuntimeError(f"reused {table} rows were duplicated")
            attendance = connection.execute(
                """
                SELECT status_source_loaded, lilo_source_loaded, lilo_row_present
                FROM wfm_attendance_agent_day
                WHERE generation_id = ? AND business_date = '2026-07-01'
                """,
                (reused_id,),
            ).fetchone()
            if attendance != (1, 1, 1):
                raise RuntimeError("reused Status/LILO evidence did not reach attendance")

        with schedule.open("w", encoding="cp1252", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t")
            writer.writerow(
                ["Name", "Data Source IDs", *(f"07/{day:02d}/2026" for day in range(1, 32)), ""]
            )
            writer.writerow(["Ada Agent", "00123", "not an interval", *(["Off"] * 30), ""])
        active_id = reused_id
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
