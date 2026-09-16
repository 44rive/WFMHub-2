# WFMHub 2.0 Architecture

## Architectural objective

WFMHub 2.0 separates four concerns that should never collapse into one large application module:

1. **source ingestion** — understand vendor/file formats;
2. **WFM domain logic** — define what service, staffing, attendance, forecasting, scheduling, and capacity mean;
3. **intelligence/optimization** — explain, predict, recommend, and solve;
4. **transport/presentation** — expose results through API, desktop UI, CLI, and reports.

The product architecture is stable even if implementation libraries change.

## Runtime topology

The portable desktop edition uses two runtime processes:

```text
┌──────────────────────────────┐
│ Tauri 2 desktop process      │
│                              │
│ React/TypeScript webview     │
└──────────────┬───────────────┘
               │ HTTP on 127.0.0.1
               ▼
┌──────────────────────────────┐
│ Python 3.14 engine sidecar   │
│                              │
│ FastAPI                      │
│ WFM domain services          │
│ Intelligence                 │
│ Forecasting                  │
│ OR-Tools optimization        │
│ DuckDB / DuckLake / Polars   │
└──────────────┬───────────────┘
               │
      ┌────────┴─────────┐
      ▼                  ▼
 control.sqlite      DuckLake catalog
                    + Parquet data files
```

The Python engine is the only component allowed to own WFM calculations or analytical writes. The UI never reads database files directly.

## Storage model

### Control plane — SQLite

`data/control.sqlite`

Responsibilities:

- source-file manifests and fingerprints;
- refresh runs and dependency invalidation;
- configuration/mapping versions;
- decision/intervention history;
- scenario definitions;
- audit and application state.

SQLite is intentionally small and transactional.

### Analytical plane — DuckLake + Parquet

`data/lake/catalog.ducklake` is the metadata catalog for the portable edition. `data/lake/files/` holds Parquet files managed by DuckLake.

DuckDB is used as the analytical query/compute engine. DuckLake gives the history layer table/catalog semantics, snapshots, schema evolution, partitioning and managed Parquet files without forcing WFMHub to invent its own lakehouse metadata format.

For the desktop edition, the DuckLake catalog is DuckDB-backed because one Python engine process owns writes. If WFMHub later becomes a multi-client/server application, the DuckLake catalog can move to SQLite or PostgreSQL while preserving table semantics.

## Medallion-style analytical layers

The Bronze/Silver/Gold terminology describes data responsibility rather than separate physical databases.

### Bronze

Source-faithful normalized facts with strong provenance.

Examples:

- `bronze.verint_schedule`
- `bronze.verint_activity`
- `bronze.storm_agent_status`
- `bronze.storm_call`
- `bronze.forecast`

Rules:

- retain source identifiers and source version;
- normalize types/encoding/time zones;
- do not apply business interpretation that belongs to WFM domain policy.

### Silver

Canonical governed WFM facts.

Examples:

- `silver.agent_interval_activity`
- `silver.service_interval_demand`
- `silver.schedule_interval`
- `silver.attendance_evidence`
- `silver.forecast_interval`

Rules:

- vendor-neutral schema;
- governed mappings and scope;
- effective-dated policy;
- preserve null/unknown evidence states.

### Gold

Decision-ready marts/products.

Examples:

- `gold.rta_interval`
- `gold.staffing_interval`
- `gold.forecast_accuracy`
- `gold.schedule_quality`
- `gold.capacity_week`
- `gold.intervention_candidate`

Gold can be rebuilt from governed lower layers.

## Refresh architecture

Normal refresh is dependency-aware and incremental:

```text
Discover files
    |
    v
Metadata check (path, size, precise mtime)
    |
    +-- unchanged metadata + policy -> skip
    |
    v
SHA-256 when needed
    |
    +-- already active source version -> skip/reactivate
    |
    v
Adapter normalization -> Bronze
    |
    v
Determine affected business-date/service ranges
    |
    v
Rebuild only affected Silver dependencies
    |
    v
Rebuild only affected Gold marts/intelligence
    |
    v
Commit refresh manifest + DuckLake snapshot metadata
```

A full historical rebuild is a separate maintenance command.

## Domain architecture

The `domain/` package is not allowed to import FastAPI, React/Tauri concepts, or vendor parser modules.

```text
domain/
  attendance/
  service/
  staffing/
  forecasting/
  scheduling/
  capacity/
```

This keeps the business engine usable from API, CLI, tests, batch jobs, and future server deployments.

## Intelligence architecture

`intelligence/` answers questions that combine multiple domain outputs:

```text
risk/             next 2–4 hour operational risk
interventions/    eligible actions + expected impact
scenarios/        governed what-if analysis
patterns/         repeated structural findings
decisions/        action/outcome learning
```

The first versions should be deterministic and explainable. Statistical/ML models may add probability/confidence but should not replace visible drivers.

## Forecasting architecture

Forecasting is its own domain pipeline:

```text
canonical demand history
        |
        +--> StatsForecast baselines
        +--> MLForecast feature pipeline
                |
                +--> XGBoost models
        |
        v
rolling-origin cross validation
        |
        v
metric comparison / model registry
        |
        v
selected forecast
        |
        v
HierarchicalForecast reconciliation
        |
        v
governed forecast version
```

The engine must retain model/version/training window/feature provenance and forecast creation time so forecast vintages can be compared fairly.

## Optimization architecture

OR-Tools CP-SAT models belong under `optimization/` and consume domain objects rather than raw source rows.

Typical constraints:

- coverage requirement per interval;
- skill eligibility;
- shift duration;
- min/max hours;
- rest rules;
- break/lunch windows;
- training/PTO locks;
- weekend/fairness preferences;
- cross-service movement costs.

Solver output is a proposal. Domain validation remains authoritative.

## Desktop architecture

Tauri is only the native shell. React owns presentation. Python owns the WFM engine.

```text
Tauri
  ├─ package web assets
  ├─ start/stop `wfmhub-engine` sidecar
  ├─ native window lifecycle
  └─ future OS integration

React
  ├─ routes/navigation
  ├─ TanStack Query API state
  ├─ TanStack Table/Virtual dense grids
  ├─ ECharts interval visuals
  └─ Tailwind design system

FastAPI
  ├─ transport validation
  ├─ OpenAPI contract
  └─ calls application/domain services
```

No WFM formula should live inside API route functions or React components.

## Security boundary

The desktop engine binds only to loopback. Production packaging should add a per-launch authentication token passed from Tauri to the sidecar and required on mutating API requests. CORS/origin policy should be restricted to the packaged application and approved development origin.

WFMHub does not require inbound LAN access in portable mode.

## Future team/server edition

The architecture deliberately leaves room for:

```text
React web client
      |
central FastAPI service
      |
PostgreSQL control plane
DuckLake PostgreSQL catalog / object storage
worker processes
SSO / role-based access
```

That is an evolution of deployment topology, not a rewrite of the WFM domain layer.
