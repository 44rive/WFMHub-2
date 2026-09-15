# WFMHub 2.0 Architecture

This document describes the system architecture. For the business/product direction, read [PROJECT_VISION.md](PROJECT_VISION.md). For the rationale behind individual libraries, read [docs/TECH_STACK.md](docs/TECH_STACK.md).

## Architecture principle

The repository is structured around WFM responsibilities rather than source vendors.

```text
Adapters -> Canonical WFM facts -> Domain services -> Intelligence -> Decisions
```

A vendor change should primarily affect an adapter. A staffing-rule change should affect the staffing domain. A risk-model change should affect intelligence. Those boundaries are deliberate.

## Runtime architecture

```text
                 React / TypeScript UI
                          |
                       FastAPI
                          |
      +-------------------+--------------------+
      |                   |                    |
 WFM domain engine   Intelligence engine   Optimization
      |                   |                 OR-Tools
      +---------+---------+--------------------+
                |
        +-------+--------+
        |                |
      SQLite           DuckDB
   control plane     analytics plane
        |                |
        |          partitioned Parquet
        |                |
        +-------+--------+
                |
         Polars / Python
           ingestion
                |
     Verint / Storm / CSV / Excel
```

## Product layers

### Evidence layer

Untouched source exports remain source evidence. WFMHub records content fingerprints, parser versions and relevant policy/configuration fingerprints.

### Canonical WFM layer

Vendor-specific records are normalized into generic WFM concepts such as interval demand, agent activity, schedule events, attendance evidence and forecast facts.

### Domain layer

Pure WFM business logic belongs here:

- service metrics;
- staffing requirements;
- attendance reconciliation;
- forecasting accuracy;
- scheduling quality;
- capacity models.

### Intelligence layer

The intelligence layer combines domain outputs into higher-order decisions:

- risk horizon;
- gap decomposition;
- intervention candidates;
- recurring patterns;
- scenario results;
- future copilot context.

### Optimization layer

Optimization consumes governed requirements and constraints. It should never become a second source of WFM metric definitions.

## Data architecture

### SQLite — control plane

SQLite owns small, transactional, mutable application state:

- source file manifest and fingerprints;
- active source versions;
- mapping/config metadata;
- refresh runs and errors;
- decision/intervention log;
- scenario definitions;
- audit/application metadata.

### DuckDB — analytics plane

DuckDB owns analytical tables and marts:

- normalized interval facts;
- call and agent-status analytical history;
- forecast/actual comparisons;
- staffing requirement and coverage marts;
- schedule/attendance analytical models;
- forecast accuracy;
- risk features/horizons;
- scenario outputs.

### Parquet — analytical history

The local data lake follows a Bronze/Silver pattern.

**Bronze** is source-faithful normalized data keyed by content hash and parser version.

**Silver** applies governed mappings and scope to create canonical WFM facts.

**Gold** is represented by DuckDB marts/intelligence products optimized for repeated decisions and UI queries.

Example partitioning:

```text
data/lake/bronze/storm_calls/year=2026/month=09/day=15/part-000.parquet
data/lake/silver/interval_demand/year=2026/month=09/day=15/part-000.parquet
```

A mapping change can therefore rebuild Silver/Gold from Bronze without reparsing the original source file.

## Refresh contract

A normal refresh MUST NOT rebuild all history.

1. Discover candidate files.
2. Compare lightweight metadata and parser/policy fingerprints.
3. Hash when required to confirm content identity.
4. Skip unchanged source versions.
5. Parse/normalize changed files only.
6. Determine the affected business-date/interval range.
7. Replace only affected Bronze/Silver partitions.
8. Recompute only dependent DuckDB slices and marts.
9. Activate the new source/model state only after successful completion.
10. Preserve the previous good version when a refresh fails.

The dependency graph operates on bounded date/interval ranges rather than whole-table invalidation wherever possible.

## Domain package layout

```text
src/wfmhub2/
├─ adapters/
│  ├─ verint/
│  └─ storm/
├─ domain/
│  ├─ attendance/
│  ├─ capacity/
│  ├─ forecasting/
│  ├─ scheduling/
│  ├─ service/
│  └─ staffing/
├─ intelligence/
│  ├─ interventions/
│  ├─ risk/
│  └─ scenarios/
├─ optimization/
├─ analytics/
├─ ingestion/
├─ storage/
├─ reports/
└─ api/
```

## API boundary

FastAPI should expose use cases, not database tables. Example future routes:

```text
GET  /api/rta/current
GET  /api/rta/risk
GET  /api/rta/drivers
GET  /api/interventions
POST /api/decisions
GET  /api/forecast/accuracy
POST /api/scenarios
GET  /api/staffing/requirements
```

Route handlers should delegate to application/domain services and return explicit response models.

## Frontend architecture

The UI is a WFM workbench rather than a generic dashboard framework. Reusable concepts should include components such as:

```text
KpiCard
IntervalChart
CoverageChart
ServiceCurve
StaffingGap
RiskHeatmap
InterventionCard
ScenarioControls
DecisionLog
```

The same interval chart model should be reused across RTA, forecast, staffing and scenario views where possible.

## Security posture for portable mode

- bind only to loopback by default;
- do not expose source files directly through static serving;
- validate action requests;
- keep runtime data out of Git/release program files;
- use explicit configuration paths;
- avoid arbitrary SQL from the browser;
- preserve source/decision audit metadata.

## Testing strategy

Tests should map to architecture boundaries:

- parser/adapter fixtures;
- pure domain unit tests;
- intelligence/risk tests;
- storage migration tests;
- incremental refresh tests;
- API contract tests;
- portable startup smoke tests;
- frontend type/build tests.

Synthetic fixtures should represent realistic edge cases without committing operational workforce data.

## Evolution path

The architecture deliberately supports two deployment modes without changing the WFM domain model.

**Portable:** local Python process + SQLite + DuckDB/Parquet + compiled React UI.

**Future team/server:** hosted FastAPI, multi-user application database, analytical storage/compute and optimization workers.

Portable remains a first-class product even if team/server mode is added later.
