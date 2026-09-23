# WFMHub 2.0 Roadmap

The roadmap is organized by **WFM capability**, not by framework implementation.

## Current status

The portable foundation passed its exact managed-workstation Phase 0.4 gate on
2026-09-20. The active delivery is refresh qualification and the first
governed RTM/RTA vertical slice. WFMHub 2's full intraday, tactical and
strategic vision in [`PROJECT_VISION.md`](../PROJECT_VISION.md) remains the
objective. WFMHub-Portable is a reference and donor for governed contracts,
not the scope of Hub2: only the RTM workbook, clean data extracts, PCS and
Bonus are required Portable product carryovers. Browser analytics and
advanced models remain capability-gated rather than prerequisites for core
RTA operation.

The proposed delivery order and acceptance gates are in
[WFMHub 2 vision delivery and Portable carryover plan](PORTABLE_FUSION_RTM_PLAN.md).
Hub2 is the target codebase; current Portable v1.1.2 with the user's effective
configuration is the comparison baseline for shared source behavior and those
four outputs. It remains the daily tool until a separately approved,
reversible **four-product cutover**. First RTM, four-product cutover, and full
WFM vision delivery are different milestones. Neither cutover nor progress on
new WFM capabilities requires parity with every Portable report.

The capability sequence is **Observe/Explain → Predict/requirement →
Recommend/scenario → Decide → Measure → Learn**. The workspaces below are
product areas, not claims that their features already exist. Each later phase
depends on governed inputs, validation and acceptable performance on the
managed workstation; no LLM or autonomous operational action is required.

## Foundation — platform and governed data

- official embedded-CPython runtime + CMD/localhost-browser lifecycle;
- stdlib host + authoritative SQLite analytical/core plane;
- optional DuckDB-Wasm/OPFS rebuildable analytical cache;
- incremental source manifest and refresh planner;
- adapter contract for Verint/Storm/generic CSV/Excel;
- canonical service/interval/agent concepts;
- synthetic fixture library;
- portable Windows CI/release pipeline.

## Intraday / RTA

- first RTM milestone: source-backed service/staffing evidence, primary Excel
  workbook and matching Operate drill-down from one deterministic domain path;
- separate carryover gates: clean data extracts, PCS six-CSV/shared coaching
  workbook, permanent editable Bonus state;
- RTA Command Center;
- current service and workload;
- required/scheduled/present/effective staffing ladder;
- attendance evidence;
- staffing-gap decomposition;
- 2–4 hour risk horizon;
- intervention candidate engine;
- decision/outcome log;
- intraday timeline and agent drill-down.

## Forecast and staffing

- governed forecast vintages and source authority;
- bias/WAPE/MAE/RMSE;
- weekday/interval error patterns;
- explainable pure-Python seasonal baselines;
- optional Pyodide statsmodels/scikit-learn candidates;
- hierarchical reconciliation after target performance qualification;
- independent staffing requirement service;
- shrinkage uplift and requirement audit trail.

## Schedule intelligence

- governed published schedules, skill/eligibility and constraint inputs;
- schedule vs requirement coverage fit;
- over/understaffed FTE-hours;
- break/lunch concentration;
- skill mismatch;
- training/PTO displacement;
- schedule-quality findings;
- HiGHS-Wasm MIP scheduling prototype;
- optional OR-Tools CP-SAT reference in a trusted/server profile.

## Scenario lab

- validated reuse of the production requirement calculation;
- volume/AHT/shrinkage/FTE deltas;
- absence scenarios;
- cross-skill movement;
- training/PTO scenarios;
- forecast-vintage comparison;
- scenario result persistence and comparison.

## Tactical capacity

- governed productivity, cost, PTO/training and hiring lead-time assumptions;
- weekly/monthly workload;
- shrinkage and productivity assumptions;
- required headcount;
- PTO/training capacity;
- hiring lead-time model;
- attrition scenarios.

## Strategic workforce planning

- governed attrition, demand, cost/budget and skill-mix assumptions;
- 12–18+ month demand/capacity horizon;
- hiring plans;
- budget/cost assumptions;
- outsource/insource scenarios;
- skill-mix strategy;
- capacity-risk bands.

## Decision learning

Once sufficient governed decision/outcome history and measured intervention
results exist:

- intervention effectiveness by context;
- expected recovery distributions;
- confidence calibration;
- operational-cost modelling;
- recommendation ranking based on observed outcomes.

No LLM feature or dependency is part of this plan; deterministic forecasting
and optimization remain evidence-gated WFM capabilities. Pyodide,
DuckDB-Wasm and HiGHS-Wasm remain optional, target-qualified tools, not
discarded technology or automatic product promises.
