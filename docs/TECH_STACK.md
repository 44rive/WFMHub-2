# Technology Stack

The technology stack serves the product vision; it is not the product itself.

## Design constraints

WFMHub 2.0 is designed around several constraints:

- Windows-first portable distribution;
- no administrator rights required;
- no externally installed database server;
- no installed Python required for end users;
- no Node.js required for end users;
- useful while offline;
- large historical analytical workloads;
- deterministic and auditable WFM calculations;
- a path from single-user portable mode to a future team/server mode.

## Python 3.13

Python owns orchestration and the WFM business/domain layer. It is the natural home for forecast evaluation, staffing models, scenario engines, source adapters, optimization orchestration and report generation.

The packaged product will embed CPython so the target machine does not need a Python installation.

## FastAPI

FastAPI provides a typed boundary between the backend and frontend. It should stay thin: API routes call domain/intelligence services rather than containing WFM formulas directly.

In portable mode it binds to loopback (`127.0.0.1`) and serves the local application.

## SQLite — control plane

SQLite stores small, mutable, transactional application state:

- source manifests and fingerprints;
- active source versions;
- mappings/configuration references;
- refresh run history;
- decision/intervention history;
- scenario definitions;
- application metadata and audit.

This data is operationally important even when analytical history is rebuilt.

## DuckDB — analytics plane

DuckDB stores or queries analytical models:

- large call/contact history;
- agent-state history;
- interval facts;
- forecast versus actual marts;
- staffing/coverage marts;
- attendance/schedule analytical outputs;
- scenario outputs;
- intelligence features.

It is optimized for columnar analytical scans, joins and aggregations rather than being used as the primary application state store.

## Why both SQLite and DuckDB?

The split creates a clean failure/rebuild boundary.

```text
SQLite control plane           DuckDB / Parquet analytics
--------------------           --------------------------
manifest                        high-volume facts
mappings                        interval history
refresh state                   analytical marts
decisions                       scenarios
audit                           features
small + mutable                 large + rebuildable
```

A future implementation may prove that some tables can move between the two. The architectural rule is responsibility, not dogma.

## Polars

Polars is the transformation engine for source-normalization tasks that are easier to express as dataframe operations than SQL.

Good examples:

- parsing vendor exports;
- timestamp normalization;
- conditional field derivation;
- pivots/unpivots;
- schema cleanup;
- large joins during normalization;
- lazy scans where only selected columns/rows are required.

Polars is optional per adapter. A clear source-specific Python parser or a DuckDB SQL transformation is preferred when it is simpler.

## Parquet

Parquet is the durable analytical history format for Bronze/Silver lake layers.

Benefits include:

- compact columnar storage;
- column pruning;
- predicate/partition filtering;
- reproducible historical layers;
- direct query support from DuckDB and Polars.

The lake is local in portable mode. “Lake” describes architecture, not cloud infrastructure.

## OR-Tools CP-SAT

OR-Tools provides the optimization engine for future scheduling and allocation problems.

Possible constraints include:

- minimum coverage by interval;
- skills and service eligibility;
- contract hours;
- shift bounds;
- rest rules;
- break placement;
- working-day limits;
- preferences;
- PTO/training;
- weekend rotations.

The solver must consume governed WFM requirements rather than duplicate requirement calculations.

## React + TypeScript + Vite

React provides reusable UI components for a growing WFM workbench. TypeScript makes the API/UI contract explicit and reduces errors as models become more complex.

Vite is used only during development/build. The portable release contains compiled static assets; users do not need Node.js.

## Apache ECharts

WFM views are dense and interval-oriented. ECharts is intended for components such as:

- forecast vs actual curves;
- required/scheduled/present/effective FTE;
- intraday service trend;
- staffing-gap heatmaps;
- scenario overlays;
- forecast-error profiles.

## Excel tooling

XlsxWriter and OpenPyXL remain part of the stack because Excel is still a practical handoff format in WFM operations.

Excel is an output/integration surface, not the calculation authority. Governed calculations should happen in the domain/analytics layers before export.

## Future team/server mode

Portable mode is the first-class target. If WFMHub becomes multi-user, the API/domain boundaries allow a future architecture such as:

```text
React
  |
FastAPI
  |
PostgreSQL control/application state
  +
DuckDB/Parquet analytical processing
  +
OR-Tools optimization workers
```

The domain model should not need a rewrite simply because the deployment topology changes.
