# Technology Stack — 2026 Target-Compatible Baseline

Baseline revised: **2026-09-20**.

This file records implementation choices, not the WFM product definition.

## Why the baseline changed

The exact Phase 0.3 release proved that official CPython 3.13.7, SQLite, and the
pure-Python Excel stack run on the target corporate workstation. The same run
proved that App Control blocks the native binaries used by Pydantic Core,
DuckDB, Polars, PyArrow, NumPy, XGBoost, OR-Tools, and dependent forecast
libraries.

Packaging those binaries differently cannot authorize them. The active target
profile therefore uses a small proven host and moves optional heavy computation
into Edge WebAssembly workers.

## Portable host — required

### Official CPython 3.13.7 embeddable distribution

- exact official Windows x64 archive, pinned by SHA-256;
- launched directly by `WFMHub.cmd` in isolated mode;
- no installer, administrator rights, machine Python, or runtime extraction;
- only official CPython native files on the host side;
- application code remains ordinary auditable Python.

### Python standard-library HTTP server

`ThreadingHTTPServer` serves the compiled React application and a narrow local
JSON boundary. It replaces FastAPI, Uvicorn, Pydantic, and Pydantic Settings in
the target portable profile because those currently cross the blocked native
boundary.

The server binds to the stable `127.0.0.1:8420` origin, validates Host headers,
uses a per-launch session token, applies browser security headers, and persists
through explicit application/domain services. A stable origin is required for
OPFS continuity between launches.

### SQLite

Python's bundled SQLite is the authoritative portable database for manifests,
governed facts, marts, configuration versions, decisions, scenarios, audit,
and upgrade state. It uses WAL, explicit transactions, integrity checks, and
verified backups.

### OpenPyXL 3.1.5 + XlsxWriter 3.2.5

These exact pure-Python wheels preserve Excel as a first-class WFM handoff.
They already passed the target policy and are stored as intact reviewed wheel
archives in the embedded runtime.

## Browser presentation — required

### React 19.3 + TypeScript 7 + Vite 8

React owns presentation only. TypeScript types the browser boundary, and Vite
produces self-hosted static assets. React Server Components are unnecessary.

### TanStack Query / Router / Table / Virtual

- Query: local API state, polling, and invalidation;
- Router: type-safe filters and routes;
- Table: dense WFM grids;
- Virtual: large interval/agent/schedule surfaces without excessive DOM work.

### Tailwind CSS 4.3 + Apache ECharts 6.1

Tailwind provides the design primitives. ECharts supports interval trends,
forecast/actual comparison, staffing ladders, heatmaps, error distributions,
and risk timelines.

### Biome 2.5 + Vitest 5

Biome formats/lints browser source; Vitest covers pure browser contracts. A
real-browser smoke is required for Worker, WebAssembly, OPFS, and solver gates.

## Browser compute — optional and feature-gated

### DuckDB-Wasm 1.32.0

Pinned because this version has working OPFS persistence while the npm version
that was current during evaluation had a known persistence regression.

Use it for interactive analytical queries and rebuildable derived cache. The
compatibility gate writes, checkpoints, terminates, reopens, and reads the same
OPFS database. OPFS is never the sole source of truth.

### Pyodide 0.29.5

The release self-hosts the Pyodide core and the exact recursively locked wheels
needed for:

- Python 3.13.2;
- NumPy 2.2.5;
- SciPy 1.14.1;
- scikit-learn 1.7.0;
- statsmodels 0.14.4;
- their required pure/Wasm dependencies.

The gate fits a `HistGradientBoostingRegressor` and a statsmodels exponential
smoothing model inside a Worker. This proves execution, not production forecast
quality. Model selection still requires governed backtesting.

### highs 1.15.3

The `highs` npm package is the community `highs-js` WebAssembly binding. It
solves LP, MIP, and convex QP models locally. It is single-threaded and not an
OR-Tools CP-SAT drop-in. The gate solves a small integer staffing allocation;
production scheduling requires a separate formulation/performance milestone.

## Development and trusted profile

The existing native Python graph remains available for development and for a
future IT-managed trusted deployment:

- FastAPI/Pydantic;
- DuckDB/DuckLake/Parquet;
- Polars/PyArrow;
- StatsForecast/MLForecast/HierarchicalForecast;
- XGBoost;
- OR-Tools CP-SAT.

These libraries remain useful reference implementations and server-edition
candidates. They are not loaded or shipped by the target hybrid ZIP.

## Packaging

The Phase 0.4 hybrid ZIP contains:

```text
WFMHub-2/
├─ WFMHub.cmd
├─ DOCTOR.cmd
├─ README-FIRST.txt
├─ Feed/
├─ Reports/
└─ _system/
   ├─ runtime/       official CPython + four pure wheel archives
   ├─ app/           stdlib-only compatibility host
   ├─ web/           compiled React, workers, WASM, Pyodide wheels
   └─ manifests/     origins and exact SHA-256 inventories
```

The build rejects any native host file not present in the official CPython
archive and rejects runtime/user data. GitHub's automatic source archive is not
a runnable release.

## Qualification gates

Source:

- Ruff format/lint;
- strict Pyright;
- pytest;
- Biome;
- TypeScript;
- Vitest;
- production web build.

Host ZIP:

- exact CPython archive/hash;
- no third-party host `.pyd`/`.dll`;
- SQLite WAL/quick-check;
- OpenPyXL/XlsxWriter XLSX round-trip;
- complete browser asset/hash manifest;
- deterministic ZIP inventory and extraction verification.

Browser:

- Worker-hosted base WebAssembly;
- DuckDB-Wasm SQL plus OPFS checkpoint/reopen;
- Pyodide/scikit-learn/statsmodels model fit;
- HiGHS-Wasm integer solve;
- no-network run;
- final execution of the exact extracted ZIP on the managed workstation.

## Explicit non-selections

- AppLocker/WDAC bypasses;
- Tauri, PyInstaller, custom launcher executables, or installers;
- native analytical wheels in the target portable profile;
- OPFS as authoritative storage;
- browser-only `file://` launch without a stable loopback origin;
- runtime CDN/package downloads;
- uploads or cloud storage for operational workforce extracts;
- claims that a forecasting or optimization replacement is equivalent without
  measured WFM validation.
