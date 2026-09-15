# WFMHub 2.0 Roadmap

The roadmap follows WFM value rather than framework milestones.

## Foundation — platform contract

- repository/package structure;
- SQLite control-plane schema and migrations;
- DuckDB analytical schemas;
- Bronze/Silver Parquet conventions;
- source manifest and fingerprint engine;
- bounded incremental refresh planner;
- FastAPI application boundary;
- React workbench shell;
- Windows portable build pipeline;
- CI, linting and tests.

## Phase 1 — RTA Command Center

- canonical service/interval model;
- Verint/Storm adapters;
- current service and demand;
- scheduled/present/effective FTE;
- attendance evidence;
- staffing gap decomposition;
- 2–4 hour risk horizon;
- deterministic intervention candidates;
- decision/outcome log;
- core interval charts and risk heatmaps.

**Outcome:** WFMHub becomes a daily operational control tool.

## Phase 2 — Forecast & staffing intelligence

- forecast-vs-actual history;
- bias, WAPE, MAPE/MAE views;
- recurring day/interval patterns;
- independent staffing requirement engine;
- configurable shrinkage uplift;
- staffing requirement comparison to vendor outputs;
- scenario engine for volume/AHT/FTE/shrinkage.

**Outcome:** WFMHub explains recurring performance and supports forward staffing decisions.

## Phase 3 — Schedule intelligence

- canonical schedule/activity model;
- demand-vs-schedule coverage fit;
- over/understaffed FTE-hours;
- lunch/break/activity concentration;
- schedule quality findings;
- PTO/training capacity views;
- skill/service eligibility model.

**Outcome:** WFMHub moves from attendance monitoring to schedule-quality analysis.

## Phase 4 — Optimization

- OR-Tools coverage allocation model;
- shift generation/selection;
- break/lunch placement optimization;
- agent skill and contract constraints;
- preference/rotation constraints;
- intervention allocation optimization;
- explainable solver outputs and trade-offs.

**Outcome:** WFMHub can recommend optimized workforce plans, not only diagnose gaps.

## Phase 5 — Capacity & strategic planning

- long-range demand scenarios;
- productive/scheduled/headcount conversion;
- attrition and hiring classes;
- training/ramp curves;
- budget/outsourcing scenarios;
- monthly/weekly capacity plan;
- executive decision views.

**Outcome:** the same platform supports WFM manager and capacity-planning work.

## Phase 6 — WFM copilot

Only after the governed analytical model is mature:

- natural-language explanations of deterministic facts;
- guided root-cause analysis;
- scenario creation from plain language;
- decision-log summarization;
- recommendation explanation;
- historical intervention retrieval.

The copilot is an interface to governed WFM intelligence, not an alternative calculation engine.
