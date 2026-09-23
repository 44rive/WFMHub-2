# Portable fusion and RTM delivery plan

Status: **proposal for user validation**, 2026-09-23. This document defines
delivery and acceptance; it does not claim that the proposed features exist.

## Decision and outcome

WFMHub 2 is the target codebase. The current WFMHub-Portable stays the daily
production tool until a separately approved cutover. We will first qualify
Hub2's refresh foundation, then bring across only the governed contracts RTM
needs, build RTM once in Hub2, and finish the remaining operational fusion.

There are two distinct outcomes:

| Milestone | What the user has | What it does **not** mean |
| --- | --- | --- |
| First usable RTM release | A target-compatible Hub2 ZIP with a governed, source-backed RTM view and Excel/Flash output computed by the same pure-Python domain service; source freshness, quality and unknown states remain visible. | It is not yet the replacement for every Portable workflow. Portable remains the daily tool during the pilot. |
| Full operational fusion and cutover | The agreed current Portable workflows, configuration, durable state and outputs are available and accepted in Hub2; a verified, reversible data transition makes Hub2 the sole daily writer. | It is not the entire long-range six-workspace vision, nor a promise of AI, predictive accuracy or automated decisions. |

The existing six-workspace shell is retained. Command's functional source
readiness page stays visible; new RTM and Govern pages appear only when they
work. Unimplemented Plan, Capacity, Review and other pages remain hidden
rather than showing placeholder KPIs.

## Starting point and authority

- The active corporate-compatible implementation is `src/wfmhub2_compat/`:
  stdlib host, authoritative SQLite, read-only local source refresh and optional
  browser-WASM capabilities. `src/wfmhub2/` is the earlier native/development
  prototype, not a second supported portable business engine. New RTM formulas
  will have one pure-Python domain path under `src/wfmhub2_compat/domain/`,
  called by both HTTP read models and Excel delivery. Existing compatible
  modules can be moved into that path incrementally with parity tests.
- Hub2 already ingests FTE Count and published StartEndTimes, with optional
  Agent Status, LILO and Call-by-Call evidence. It has attendance agent-days
  and gaps, deduplicated call legs and additive service interval components.
  It does **not** yet have governed headline service ratios, Verint Staff Type
  forecast/requirement, a staffing ladder, an operational RTM page or a Flash
  workbook. Current Command shows source readiness, not operational KPIs.
- The comparison baseline is the **current Portable v1.1.2 plus the user's
  effective configuration**, not the old `v0.36.0` version named in the
  historical Phase 1 refresh decision. Historical ledger evidence remains
  intact; this plan supersedes its baseline for future acceptance.
- Original extracts and the existing Portable database remain untouched.
  Browser OPFS is rebuildable cache, never the source of truth. No real
  workforce data belongs in the repository or a release ZIP.

## Delivery sequence and go/no-go gates

### 1. Prove Preview `.7` refresh on actual use

Record the first real refresh duration, per-source counts and date ranges,
quality totals, active generation, and the unchanged no-op result. Compare the
same governed source cut and effective mappings with Portable v1.1.2. At the
next normal export, measure a changed-source refresh; do not alter an
operational extract merely to manufacture a test. Inject failures only in
synthetic fixtures to prove that the prior validated generation stays active
and the diagnostic is actionable.

**Gate:** explain and resolve material count, date, scope, attendance and
service-evidence differences; demonstrate no-op, changed-source, failure
rollback and acceptable measured time on the managed workstation. Agree a
numeric daily-refresh budget after baseline measurement, not by assumption.

### 2. Finish the refresh foundation

Use immutable source-version reuse already in `.7`, then implement affected
business-date/service ownership for derived attendance and service facts.
Expand overnight and cross-file dependencies conservatively. Preserve the
single atomic active-generation pointer, provenance, quality findings and
read-only source access. Add scale and correction benchmarks, and a tested
upgrade/backup path for Hub2's own SQLite schema.

**Gate:** unchanged sources do not reparse; a correction rebuilds the
affected scope rather than all history; synthetic migration, corruption and
failure tests preserve the last valid cut. Exact extracted Windows ZIP still
passes its host doctor and offline browser gates.

### 3. Fuse only the governed inputs RTM needs

Inventory Portable v1.1.2's effective user mappings, service profiles,
allowlists, KPI/Flash formulas, source precedence and synthetic tests. Port
reviewed configuration and rule versions into Hub2 with fingerprints and
traceable scope. Add the Verint Staff Type forecast/requirement contract at
its natural grain. Define service ratios as ratio-of-sums from governed
components, and distinguish service demand, forecast/requirement, schedule
and attendance rather than forcing one universal interval fact.

The user and project must approve the exact RTM metric dictionary, service
scope, time zone, freshness rules and output comparisons before headline
metrics are exposed. Unknown or missing evidence stays unknown.

**Gate:** synthetic edge cases and same-cut Portable comparisons agree for
the approved formulas and mappings, or every difference is documented and
accepted. A missing requirement source cannot silently become zero staffing
need. No business formula is duplicated in React, adapters or workbook code.

### 4. Deliver the first usable RTM vertical slice

Build one versioned, pure-Python RTM calculation/read-model service for
service, requirement, scheduled, present and effective staffing, gap reasons,
attendance evidence and freshness. Expose it through a functional Operate
page with interval and agent drill-down, plus a bounded local Excel/Flash
export from the same calculation result. Show source/model generation and
quality, not merely polished totals. Start read-only; human actions and
measured outcomes require their own governed contract before activation.

**Gate:** UI and workbook match the same immutable generation and approved
Portable reference cases; no false zeros or fabricated service/attendance;
usable query/export times and workbook shape are measured on the managed
machine; exact release ZIP launches offline without admin or installed tools.

### 5. Parallel pilot, then remaining operational fusion

Run Portable and Hub2 against the same read-only source folders but separate
SQLite homes. Compare daily RTM results, late/corrected files, refresh time,
Excel/Flash output and user workflow. Keep Portable as daily production until
the user accepts the pilot. Inventory and migrate the remaining agreed
Portable workflows one by one, with a parity matrix and regression fixtures.

The remaining parity inventory explicitly includes Attendance Review,
Staffing Preparation, Realisations, Final Absenteeism & Shrinkage, governed
exports and on-demand analysis, permanent Bonus, the PCS six-CSV feed and
**one shared coaching workbook**, and CLI/report actions. Each workflow gets
its own output, state and usability gate; none may be silently dropped,
reset or reshaped. A proposed per-LOB **RTM Flash workbook** split is an
**unapproved design decision**; it requires an explicit user choice and output
contract before implementation. No automatic old-database import is claimed:
any history/configuration migration is designed, rehearsed and verified
separately, with a rebuild-from-source path where appropriate.

**Gate:** each agreed workflow has accepted output and state parity (or an
explicitly approved change), and daily RTM pilot discrepancies are resolved.

### 6. Separate, reversible cutover

Only after the pilot and remaining operational parity: stop Portable writes,
take verified backups, rehearse and verify the selected migration/rebuild,
then make Hub2 the **one writer** of its production state. Never point two
running products at the same SQLite database. Retain the prior Portable
installation and backup for rollback; reconcile any Hub2-only writes before
reverting so decisions or Bonus state are not silently lost. The user signs
off on cutover after the exact extracted ZIP passes on the managed PC.

**Gate:** record counts, date ranges, effective config, workbook/CSV outputs,
integrity checks, refresh and recovery procedure, and user acceptance. If any
gate fails, Portable remains production and Hub2 remains a pilot.

## User checkpoints and boundaries

The user validates the effective Portable configuration and representative
RTM/Flash outputs locally; reviews the metric and workbook contracts; shares
sanitized refresh timing/count/quality results from the managed workstation;
and approves the pilot and eventual cutover separately. No operational
extracts or employee data need to be sent to the repository.

Principal risks are changed-source performance at real volume, scope/formula
drift from effective Portable settings, cross-midnight dependency expansion,
locked-down Windows/Edge policy changes, and state migration. Each is a
measured gate above, not an assumption. Optional DuckDB-Wasm, Pyodide and
HiGHS remain optional; no AI, predictive forecast quality, optimization
benefit, cloud sync or whole-suite completion is promised by this plan.
