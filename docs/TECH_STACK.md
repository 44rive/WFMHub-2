# Technology Stack — 2026 Greenfield Baseline

This document describes **implementation choices**. It is intentionally separate from the WFM product vision.

Baseline date: **2026-09-16**.

## Desktop and frontend

### Tauri 2.11 line

Tauri is the Windows desktop shell. It provides a native app/window while using the system webview rather than bundling a full Chromium runtime. It can package the Python engine as an external sidecar.

Why:

- real desktop UX instead of an exposed browser tab;
- small shell footprint;
- sidecar support fits a bundled Python API engine;
- end users do not need Rust, Node, or Python installed.

Tauri 3 previews are intentionally not used.

### React 19.3

React is the UI component model. WFMHub uses it as a client-side application; React Server Components are unnecessary for the portable local architecture.

### TypeScript 7

All frontend application code is typed. API client types should eventually be generated from FastAPI/OpenAPI rather than hand-maintained.

### Vite 8.1 / Rolldown

Vite is the development/build system. Vite 8 uses Rolldown as its unified Rust-based bundler.

### TanStack Query / Router / Table / Virtual

These solve four different WFM UI problems:

- **Query** — API caching, refresh, mutation invalidation and polling;
- **Router** — type-safe route/search state such as service/date/interval;
- **Table** — complex agent, forecast and planning grids;
- **Virtual** — avoid rendering tens of thousands of schedule/interval DOM cells.

### Tailwind CSS 4.3

Tailwind provides the low-level design system. WFMHub should still own its visual identity and component patterns rather than look like a generic template.

### Apache ECharts 6.1

Used for dense WFM visualizations: forecast vs actual, requirement vs scheduled/present/effective FTE, service curves, heatmaps, error distributions and risk timelines.

### Biome 2.5

Frontend formatter/linter. It replaces a larger ESLint/Prettier plugin stack for this repository.

## Python engine

### Python 3.14.7

Python is the WFM/domain language. Use normal CPython for the production baseline; free-threaded Python is interesting but unnecessary because DuckDB, Polars, XGBoost and OR-Tools already perform heavy work in optimized native code.

### FastAPI 0.141 + Pydantic 2.13

FastAPI is a transport boundary, not the business layer. It provides typed local endpoints and OpenAPI for the React client.

Pydantic validates API/application boundary objects. Domain calculations should remain ordinary typed Python where possible.

### uv 0.12 line

Development dependency/resolution workflow:

```text
uv sync
uv run pytest
uv run wfmhub2
```

The repository should commit `uv.lock` after dependency resolution is run in a networked development environment.

`uv.lock`, the workspace `pnpm-lock.yaml`, and `src-tauri/Cargo.lock` are release
inputs. CI and portable builds use frozen/locked modes; dependency updates are
explicit changes rather than side effects of building.

### Ruff 0.16 line

Python formatter/linter/import/code-modernization tool.

### Pyright

Type-checking authority initially. `ty` may be evaluated in parallel as it matures, but the project should not make a beta checker its only correctness gate yet.

## Data architecture

### SQLite — control plane

Use Python's SQLite support for manifests, configuration versions, decisions, scenarios, refresh history and audit/application state.

This is intentionally separate from the analytical lake.

### DuckDB 1.5.5 — analytical engine

DuckDB performs scans, joins, aggregations and feature/table transformations over DuckLake/Parquet. DuckDB 2.0 is planned but not yet stable at the baseline date, so the repo targets the current 1.5 stable line.

### DuckLake 1.0 — analytical table/catalog layer

DuckLake manages table metadata, snapshots, schema evolution, partitions and Parquet files.

Portable edition:

```text
data/lake/catalog.ducklake    DuckDB-backed DuckLake catalog
data/lake/files/              managed Parquet data
```

Why not hand-manage folders only:

- snapshots/commit history;
- schema/table metadata;
- managed partition information;
- updates/deletes and maintenance semantics;
- easier reproducibility of analytical state.

For a future multi-client/server deployment, the DuckLake catalog can move to SQLite or PostgreSQL.

### Polars 1.44

Polars is the ingestion/dataframe transformation engine when transformations are easier to express as columnar expressions than SQL.

Use Polars for:

- messy source normalization;
- parsing/conditional column logic;
- pivots/explodes/string/date transforms;
- vectorized preprocessing.

Use DuckDB SQL for:

- relational joins;
- analytical aggregation;
- materialized marts;
- ad-hoc exploration over large history.

Do not force every transformation into Polars merely because it is available.

### Parquet

Parquet is the durable analytical file format underneath DuckLake. It provides columnar compression, predicate/column pruning and partition-friendly historical storage.

## Forecasting

### StatsForecast 2.1

Statistical/seasonal baselines, ETS/ARIMA-family models, and efficient cross-validation.

### MLForecast 1.1

Feature engineering for lag/calendar/exogenous-feature machine-learning forecasts.

### XGBoost 3.4

Main gradient-boosted tree option for feature-driven demand forecasting.

### HierarchicalForecast 1.5

Reconciles forecasts across WFM hierarchies so queue/service/LOB/market totals remain coherent.

Forecast quality determines model selection. The stack does not assume ML beats a seasonal baseline.

## Optimization

### OR-Tools 9.15

CP-SAT is used for scheduling and allocation constraints. WFMHub should not invent a custom constraint solver.

## Reporting

### XlsxWriter + OpenPyXL

Excel remains a first-class business handoff even when the desktop UI improves. The report layer should export governed metrics rather than reimplement calculations in workbooks.

## Packaging

### PyInstaller 6.22

Packages the Python 3.14 engine and native dependencies into `wfmhub-engine.exe`.

### Tauri bundler

Packages the desktop shell, compiled React assets and Python sidecar.

### Offline DuckDB extensions

Release builds should bundle the exact DuckLake extension binary matching the DuckDB/runtime platform and load it from disk. Normal operation must not depend on downloading extensions from the internet.

## Testing

Python:

- pytest;
- Hypothesis for domain/property invariants;
- integration tests for SQLite/DuckLake/refresh behavior.

Frontend:

- Vitest 5;
- Playwright 1.63 for end-to-end flows where appropriate.

Portable release:

- Windows clean-runner smoke test;
- engine boot;
- DuckLake extension load;
- desktop launch;
- API health;
- synthetic refresh;
- no-network execution test.

## What is intentionally not selected

- DuckDB 2.0 preview — wait for stable and benchmark migration.
- Polars 2.0 RC — wait for stable.
- Tauri 3 alpha — unnecessary risk for the desktop baseline.
- free-threaded CPython — not needed for the current native-heavy workload.
- React Server Components — no server-rendering requirement.
- a remote database server — conflicts with portable/offline goals.
- a custom optimization algorithm — OR-Tools already solves the constraint layer.
