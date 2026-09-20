# WFMHub 2.0 Architecture

## Architectural objective

WFMHub separates four concerns:

1. source adapters understand Verint, Storm, Excel, CSV, and other formats;
2. the domain layer defines governed service, staffing, attendance, forecast,
   schedule, and capacity meaning;
3. intelligence explains, predicts, recommends, and evaluates decisions;
4. transport and presentation expose the same products through the local UI,
   CLI, and reports.

The WFM model is the product. Libraries and deployment profiles may change
without changing source authority or business meaning.

## Target portable topology

The active corporate-workstation profile is deliberately asymmetric:

```text
WFMHub.cmd
    |
    v
Official embedded CPython 3.13.7
  standard-library HTTP server
  local source-folder access
  governed pure-Python WFM services
  SQLite authoritative state
  OpenPyXL / XlsxWriter reports
    |
    | HTTP on stable 127.0.0.1:8420 + per-launch token
    v
Microsoft Edge
  React / TypeScript presentation
  Web Worker: DuckDB-Wasm analytical cache
  Web Worker: Pyodide forecasting experiments
  Web Worker: HiGHS-Wasm MIP experiments
```

The host profile contains no third-party native `.pyd` or `.dll` files. The
only host native images are those in the exact official CPython embeddable ZIP,
which matches the boundary already proven by WFMHub-Portable. WebAssembly is
self-hosted and runs inside Edge rather than as a host DLL.

DuckDB-Wasm, Pyodide, and HiGHS-Wasm are feature-gated accelerators. The RTA
core must still launch and perform deterministic WFM work when any or all of
them are unavailable.

## Authority and storage

### SQLite and source files are authoritative

`data/control.sqlite` and the configured read-only extracts remain the durable
portable source of truth. SQLite uses WAL, full synchronous commits, explicit
transactions, integrity checks, verified backups, and atomic replacement where
files must be published.

SQLite owns:

- source manifests and fingerprints;
- normalized/canonical WFM facts required by the portable core;
- effective-dated mappings and configuration versions;
- refresh runs and quality evidence;
- decisions, interventions, scenarios, and measured outcomes;
- application and upgrade state.

The schema may retain Bronze/Silver/Gold responsibilities without requiring
three physical databases:

- **Bronze** — source-faithful typed evidence and provenance;
- **Silver** — mapped, vendor-neutral WFM facts at their natural grains;
- **Gold** — rebuildable RTA, staffing, forecast, and decision products.

### Browser analytics are rebuildable

DuckDB-Wasm may materialize derived analytical tables in OPFS for fast local
slice-and-dice. It is never the only copy of an operational fact because browser
storage can be cleared, evicted, or isolated by profile/origin changes.

The host can republish canonical data to the browser cache. A cache failure
must not corrupt or invalidate the last committed SQLite state.

### Trusted/server profile remains optional

Native DuckDB/DuckLake/Parquet, Polars, StatsForecast, XGBoost, and OR-Tools
remain valid for development or an IT-managed trusted deployment. They are not
dependencies of the target portable profile under the current application
control policy.

## Data grains and source authority

WFMHub does not collapse unrelated facts into one null-heavy interval table.

- Call-by-Call queue evidence owns service and demand.
- Verint Staff Type evidence owns forecast volume and requirement.
- Published schedules own planned work.
- Agent Status owns observed attendance; LILO is fallback evidence.
- Verint Activities own finalized post-day absence and shrinkage.
- FTE Count owns employee scope, status, FTE, PTO, and Away overlays.

Unknown evidence remains unknown. Client IDs remain text. RSA Belgium service
and capacity scopes retain their governed distinction.

## Refresh architecture

```text
Discover read-only source files
    |
Metadata check -> SHA-256 only when needed
    |
Parse changed source versions
    |
Validate employee, queue, date, and grain contracts
    |
Build affected canonical SQLite facts in a transaction
    |
Rebuild affected deterministic marts
    |
Commit manifest and activate the validated generation
    |
Optionally refresh the rebuildable browser cache
```

A failed refresh leaves the previous validated state active. Full historical
rebuild is an explicit maintenance operation, not the normal daily path.

## Domain and intelligence boundaries

```text
domain/
  attendance/
  service/
  staffing/
  forecasting/
  scheduling/
  capacity/

intelligence/
  risk/
  interventions/
  scenarios/
  patterns/
  decisions/
```

Domain modules must not depend on React, HTTP handlers, or vendor parser
internals. Deterministic decomposition comes before statistical prediction.
Recommendations expose eligibility, assumptions, expected impact, confidence,
constraints, and operational cost.

## Forecasting and optimization

The target profile starts with explainable pure-Python seasonal baselines and
forecast accuracy/bias measurement. Pyodide can add statsmodels and
scikit-learn models after target performance and memory qualification. Those
models must pass rolling-origin evaluation before selection.

HiGHS-Wasm can solve linear and mixed-integer allocation/scheduling models. It
is not a drop-in OR-Tools CP-SAT replacement: every model and constraint must be
reformulated, validated, benchmarked, and explained. Solver output is a
proposal; domain validation remains authoritative.

## Portable security and lifecycle

- `WFMHub.cmd` invokes the pinned official embedded runtime directly.
- The stdlib server binds only to `127.0.0.1:8420`. The stable origin lets the
  rebuildable OPFS cache survive launches; startup fails safely if the port is
  already occupied.
- Each launch creates a 256-bit token delivered in the URL fragment, never the
  HTTP query or server log.
- Protected requests require the token; Host headers are restricted to
  loopback to resist local DNS rebinding.
- Static responses enforce same-origin, cross-origin isolation, CSP, no-frame,
  and no-sniff headers.
- All JavaScript, WebAssembly, Pyodide wheels, and other runtime assets are
  packaged locally. Runtime internet is unnecessary.
- The console remains the visible lifecycle owner and Ctrl+C stops the server.
- The application reads configured local folders directly. It never uploads
  workforce extracts or requires a cloud service.

## Delivery sequence

1. **Complete:** the exact Phase 0.4 hybrid ZIP passed all five probes on the
   target corporate workstation under Edge 153.
2. Port the old product's governed source contracts, SQLite migrations,
   formulas, mappings, upgrades, and synthetic tests.
3. Deliver one RTA vertical slice: refresh -> service/attendance -> staffing
   gap -> command-centre UI -> Excel export.
4. Reach old-product operational parity before declaring WFMHub 2 its
   replacement.
5. Add browser analytics, forecasting, and optimization only behind measured
   capability and business-value gates.

## Future team/server edition

A future centrally managed edition can restore FastAPI, PostgreSQL,
DuckLake/object storage, workers, SSO, and role-based access. That is a new
deployment topology over the same governed domain model, not permission to
weaken the portable product's evidence contracts.
