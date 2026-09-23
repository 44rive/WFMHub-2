# WFMHub 2 vision delivery and Portable carryover plan

Status: **user-corrected direction; implementation gates remain to be
validated**, 2026-09-23. This document defines delivery and acceptance; it
does not claim that the proposed features exist.

## Decision and outcome

WFMHub 2's full workforce-management vision in
[`PROJECT_VISION.md`](../PROJECT_VISION.md) is the objective. WFMHub-Portable is
a proven donor/reference, not the product to copy wholesale. The user wants
four Portable products carried into Hub2: **the RTM workbook, clean data
extracts, PCS (six CSV feeds into one shared coaching workbook), and the
permanent editable Bonus workflow**. Port the source contracts, formulas,
mappings, tests, and relevant durable state needed to make those four correct;
do not make every other Portable report or workflow a prerequisite for Hub2's
progress or cutover. Current Portable stays the daily production tool until a
separately approved cutover of those four outputs.

There are three distinct outcomes, not one undifferentiated "fusion":

| Milestone | What the user has | What it does **not** mean |
| --- | --- | --- |
| First usable RTM release | A target-compatible Hub2 ZIP with a governed, source-backed RTM view and primary Excel/Flash workbook computed by the same pure-Python domain service; source freshness, quality and unknown states remain visible. | The other three carryover products and longer-horizon WFM capabilities are not implied. Portable remains the daily tool during the pilot. |
| Four-product carryover and cutover | The RTM workbook, clean data extracts, PCS shared coaching workbook/six CSV feed, and persistent editable Bonus are accepted in Hub2. Relevant configuration/history is reconciled; a verified, reversible transition makes Hub2 the sole daily writer for these workflows. | Parity with every Portable report or workflow is not required, and this is not completion of the full WFM vision. |
| WFMHub 2 vision delivery | Governed intraday, tactical, and strategic WFM capabilities grow from observation/explanation through prediction, recommendation, decisions, measurement and learning, with each product validated against its own evidence and performance gates. | A compatible technology probe, mockup, or algorithm alone is not a delivered WFM capability; no LLM feature is part of this plan. |

The six-workspace architecture (Command, Operate, Plan, Capacity, Review,
Govern) remains the product shell. Command's functional source-readiness page
stays visible; new RTM and other pages appear only when their capabilities
work. Unimplemented pages remain hidden rather than showing placeholder KPIs.

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
- The comparison baseline for shared source behavior and the four carried
  outputs is **current Portable v1.1.2 plus the user's effective
  configuration**, not the old `v0.36.0` version named in the historical
  Phase 1 refresh decision. Other Hub2 WFM products get their own governed
  acceptance contracts; they are not forced to imitate Portable.
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

### 3. Port the governed inputs RTM needs

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

### 5. Parallel pilot, then the other three Portable carryover products

Run Portable and Hub2 against the same read-only source folders but separate
SQLite homes. Compare daily RTM results, late/corrected files, refresh time,
Excel/Flash output and user workflow. Keep Portable as daily production until
the user accepts the pilot. Then implement and accept the other three carried
products individually:

- **Clean data extracts:** agree the exact source coverage, columns, grains,
  formats and quality/provenance contract; compare representative same-cut
  Portable outputs and validate privacy-safe, repeatable export behavior.
- **PCS:** preserve its six CSV feeds and **one shared coaching workbook**;
  verify feed mappings, workbook behavior, state and representative outputs.
- **Bonus:** preserve a persistent, editable workflow and relevant state;
  refresh must not overwrite user edits or silently reset history.

The RTM workbook contract, including whether Flash uses one combined workbook
or separate LOB workbooks, needs explicit user acceptance before its shape is
locked. No automatic old-database import is claimed: migrate/reconcile only
the effective configuration and history needed by the four carried products,
with a rehearsed, verified procedure and rebuild-from-source where suitable.
Portable workflows outside those four are not hidden cutover gates; any useful
contracts they contain may still inform Hub2's new WFM capabilities.

**Gate:** all four carried outputs have accepted output, state and usability
behavior (or an explicitly approved change), and daily RTM pilot discrepancies
are resolved.

### 6. Separate, reversible cutover

Only after the pilot and four-product carryover acceptance, stop Portable
writes for those workflows, take verified backups, rehearse and verify the
selected migration/rebuild, then make Hub2 the **one writer** of their
production state. Never point two running products at the same SQLite
database. Retain the prior Portable
installation and backup for rollback; reconcile any Hub2-only writes before
reverting so workbook edits, decisions or Bonus state are not silently lost.
The user signs off on cutover after the exact extracted ZIP passes on the
managed PC. This gate does not require migrating unrelated Portable reports.

**Gate:** record counts, date ranges, effective config, workbook/CSV outputs,
integrity checks, refresh and recovery procedure, and user acceptance. If any
gate fails, Portable remains production and Hub2 remains a pilot.

### 7. Deliver the wider WFMHub 2 vision in validated increments

The four carried products are an operational floor, not a ceiling on Hub2.
Continue the six-workspace product loop in this order, reusing one governed
domain model across UI, reports and future interfaces:

1. **Observe and explain intraday:** complete the service/staffing ladder,
   attendance uncertainty, gap decomposition, agent and interval drill-down,
   and measurable 2–4 hour risk horizon around RTM. Do not call a source-ready
   screen an operational command center.
2. **Forecast, requirement, schedule and capacity:** store forecast vintages;
   measure bias/accuracy; implement independently auditable staffing need,
   shrinkage uplift and schedule-fit analysis; extend to tactical and then
   strategic workload, headcount, hiring, attrition, cost and skill-mix views.
3. **Scenarios and interventions:** run what-if changes through the same
   production requirement logic; expose feasible candidate actions with
   assumptions, constraints, expected impact and uncertainty. Optimization
   output is a proposal, not an automatically authorized decision.
4. **Decisions, outcomes and learning:** record human decisions and subsequent
   outcomes, evaluate forecast/intervention quality, and improve ranking only
   when sufficient governed history supports it.

Every increment needs source authority, natural-grain contracts, deterministic
tests, calibration or backtesting where relevant, and usable target-machine
performance. Self-hosted DuckDB-Wasm, Pyodide and HiGHS-Wasm remain
capability-gated options where they add value; none may block the deterministic
core. The blocked native stack is not a dependency of the corporate portable
profile. No LLM feature is part of this plan.

## User checkpoints and boundaries

The user validates the effective Portable configuration and representative
outputs for the four carried products locally; reviews the RTM metric and
workbook contracts; shares sanitized refresh timing/count/quality results from
the managed workstation; and approves the RTM pilot and four-product cutover
separately. New Hub2 WFM capabilities have their own product/data acceptance
criteria. No operational extracts or employee data need to be sent to the
repository.

Principal risks are changed-source performance at real volume, scope/formula
drift from effective Portable settings, cross-midnight dependency expansion,
locked-down Windows/Edge policy changes, and state migration. Each is a
measured gate above, not an assumption. Browser accelerators remain optional;
forecast quality, optimization benefit and whole-vision completion require
their later validation rather than being implied by the first RTM release.
