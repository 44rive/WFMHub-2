# WFMHub 2.0

**Portable workforce intelligence for real-time analysts, planners, and workforce managers.**

WFMHub 2.0 is a vendor-neutral decision layer above workforce-management systems, telephony platforms, schedules, forecasts, and operational extracts. It converts fragmented evidence into one governed model for intraday control, tactical planning, and strategic workforce decisions.

> **North star:** tell the WFM user what is happening, why it is happening, what is likely to happen next, which action has the best expected impact, and whether that action actually worked.

WFMHub is intentionally defined in two layers:

- **The project / product** is the WFM operating model, domain logic, and decision intelligence.
- **The technology stack** is the implementation chosen to make that product fast, portable, explainable, and maintainable.

The technology can evolve without changing the WFM mission.

## Product vision

WFMHub is not trying to clone Verint, NICE, Genesys, or another enterprise WFM suite. Those systems remain valid systems of record and source authority. WFMHub is designed to become an **intelligence and decision layer above them**.

Traditional RTA work often begins with reconciliation: checking schedule, forecast, telephony, attendance, agent status, and spreadsheets before the actual operational decision can even be made. WFMHub's goal is to shorten that distance between evidence and action.

Its operating loop is:

```text
Observe -> Explain -> Predict -> Recommend -> Decide -> Measure -> Learn
   ^                                                               |
   +---------------------------------------------------------------+
```

And its capability path mirrors the growth from RTA to Workforce Manager:

```text
Intraday / RTA
    -> Forecasting & staffing
        -> Scheduling & shrinkage
            -> Capacity & hiring
                -> Workforce strategy
```

See [PROJECT_VISION.md](PROJECT_VISION.md) for the full product definition.

## What WFMHub 2.0 is building

### Intraday / RTA intelligence

The **RTA Command Center** is the first-class operational surface. For every configured service scope and interval it should answer:

- Are we meeting service now?
- Are we staffed correctly now?
- What explains the gap between requirement and effective staffing?
- Where will the next 2–4 hours become risky?
- Which intervention is operationally available?
- What impact should that intervention have?
- What actually happened after the action?

Core products include service/coverage monitoring, attendance evidence, staffing-gap decomposition, near-term risk, intervention recommendations, and a decision/outcome log.

### Tactical WFM intelligence

The tactical layer explains repeated performance patterns and improves planning through:

- forecast accuracy, bias, WAPE and interval-level error analysis;
- independent staffing requirements;
- shrinkage decomposition;
- schedule quality and demand alignment;
- PTO/training capacity;
- scenario modelling;
- hierarchical forecast reconciliation across queue -> service -> LOB -> market.

### Strategic workforce planning

The strategic layer extends the same governed model into:

- long-range demand and workload;
- headcount requirements;
- hiring and attrition scenarios;
- shrinkage and productivity assumptions;
- budget and outsourcing scenarios;
- long-range capacity risk.

## Product architecture vs technology architecture

### Product architecture

```text
Source evidence
      |
      v
Governed WFM domain model
      |
      +--> Intraday intelligence
      |      current state / gaps / risk / interventions
      |
      +--> Tactical intelligence
      |      forecast / staffing / scheduling / shrinkage
      |
      +--> Strategic intelligence
             capacity / hiring / scenarios / workforce strategy
      |
      v
Decision + outcome history
      |
      v
Measured learning and better future recommendations
```

### Technology architecture — September 2026 greenfield baseline

```text
                         WFMHub 2.0 Desktop

┌─────────────────────────────────────────────────────────────────┐
│ Tauri 2                                                        │
│ React 19.3 + TypeScript 7 + Vite 8.1                           │
│ TanStack Query / Router / Table / Virtual                      │
│ Tailwind CSS 4.3 + Apache ECharts 6.1                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │ loopback API
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Python 3.14 engine sidecar                                     │
│ FastAPI + Pydantic                                             │
│                                                                 │
│  WFM domain       Intelligence       Forecasting    Optimization│
│  attendance       risk               StatsForecast  OR-Tools    │
│  service          drivers            MLForecast                 │
│  staffing         interventions      XGBoost                    │
│  scheduling       scenarios          HierarchicalForecast       │
│  capacity         decision learning                              │
└───────────────┬───────────────────────┬─────────────────────────┘
                │                       │
                ▼                       ▼
        SQLite control plane       Polars ingestion
                │                       │
                │                       ▼
                │                 DuckLake 1.0
                │                 Parquet history
                │                       │
                └──────────────┬────────┘
                               ▼
                            DuckDB
                       analytical engine
```

The current stack rationale is documented in [docs/TECH_STACK.md](docs/TECH_STACK.md).

## Data architecture

WFMHub 2.0 uses **two storage responsibilities**, not two competing analytical databases.

### SQLite — control plane

SQLite stores small, mutable application state:

```text
configuration
source manifests
refresh runs
mapping versions
scenarios
RTA interventions
decision/outcome history
audit state
user preferences
```

### DuckLake + Parquet — analytical history

DuckLake owns durable analytical datasets and snapshots. Parquet is the physical historical storage format. DuckDB is the engine that queries and transforms those tables.

```text
Untouched source files
        |
        v
Polars adapters / normalization
        |
        v
DuckLake
  bronze  source-faithful normalized facts
  silver  mapped and governed canonical WFM facts
  gold    analytical marts / decision products
        |
        v
DuckDB queries -> FastAPI -> desktop UI / Excel / optimization
```

For the portable single-engine edition, the DuckLake metadata catalog is DuckDB-backed. A future multi-client/server edition can move the catalog to SQLite or PostgreSQL without changing the WFM domain model.

## Refresh philosophy

> **Refresh cost should scale with changed data, not total history.**

Historical partitions remain cold unless their inputs or governing policy changed.

Examples:

| Change | Expected work |
| --- | --- |
| Nothing changed | metadata/fingerprint check only |
| Add today's extracts | ingest today and rebuild affected downstream intervals |
| Correct yesterday | replace yesterday and dependent marts |
| Replace July monthly extract | rebuild July slice, not the year |
| Change queue mapping | rebuild mapped Silver/Gold from Bronze, no raw reparsing |
| Change parser logic | invalidate only source versions produced by that parser |
| Full rebuild | explicit maintenance command, never normal refresh |

DuckLake snapshots also give WFMHub a natural basis for reproducing historical analytical states, such as “what did we know when this staffing decision was made?”

See [docs/REFRESH_ENGINE.md](docs/REFRESH_ENGINE.md).

## Forecasting architecture

Forecasting is a governed model-selection pipeline rather than a single “AI forecast.”

```text
Historical demand
      |
      +--> Seasonal / statistical baselines     StatsForecast
      |
      +--> Feature-based ML models               MLForecast + XGBoost
      |
      +--> calendar / event / exogenous features
      |
      v
Cross-validation + accuracy comparison
      |
      v
Selected forecast by service / horizon
      |
      v
Hierarchical reconciliation
queue -> service -> LOB -> market totals remain coherent
```

The initial objective is not maximum model complexity. It is trustworthy bias/error measurement, reproducible backtesting, and transparent model selection.

## Optimization architecture

OR-Tools CP-SAT is the optimization layer for constraint-heavy WFM problems such as:

- interval coverage;
- shifts and tours;
- skill eligibility;
- break/lunch placement;
- contract hours and rest rules;
- training placement;
- cross-skill allocation;
- preference and fairness constraints.

The optimizer consumes governed domain inputs. Solver code does not own WFM definitions.

## Repository structure

```text
WFMHub-2/
├─ src/wfmhub2/
│  ├─ adapters/          Verint / Storm / CSV / Excel source contracts
│  ├─ analytics/         DuckDB analytical pipelines
│  ├─ api/               FastAPI transport only
│  ├─ core/              settings and shared platform primitives
│  ├─ domain/            vendor-neutral WFM business logic
│  │  ├─ attendance/
│  │  ├─ capacity/
│  │  ├─ forecasting/
│  │  ├─ scheduling/
│  │  ├─ service/
│  │  └─ staffing/
│  ├─ ingestion/         discovery, fingerprints and refresh planning
│  ├─ intelligence/      risk, interventions, patterns and scenarios
│  ├─ optimization/      OR-Tools models
│  ├─ reports/           Excel/CSV business handoffs
│  └─ storage/           SQLite control + DuckLake access
├─ web/                  React / TypeScript workbench
├─ src-tauri/            Tauri desktop shell and Python sidecar bundle
├─ docs/                 product and engineering documentation
├─ config/               example governed configuration
├─ data/                 local runtime state; ignored by Git
├─ packaging/            PyInstaller sidecar specification
├─ scripts/              build/release tooling
└─ tests/                unit, property and integration tests
```

The physical structure follows **business domains**, not source vendors. Verint parsing belongs in `adapters/verint`; staffing rules belong in `domain/staffing`; risk belongs in `intelligence/risk`.

## Portable desktop model

The target Windows release is still portable/offline:

```text
WFMHub-2/
├─ WFMHub.exe                 Tauri desktop shell
├─ wfmhub-engine.exe          bundled Python/FastAPI sidecar
├─ README-FIRST.txt
├─ SHA256SUMS.txt
├─ duckdb_extensions/
│  └─ ducklake.duckdb_extension
├─ Feed/
├─ Reports/
└─ data/
   ├─ control.sqlite
   └─ lake/
      ├─ catalog.ducklake
      └─ files/               Parquet data managed by DuckLake
```

End users should require:

- no administrator rights;
- no installed Python;
- no Node.js;
- no Rust toolchain;
- no database server;
- no internet connection during normal operation.

Node, Rust, uv, and PyInstaller are build-time tools only. The packaged DuckLake extension is loaded locally in offline releases.

End users must download the versioned Windows portable asset from GitHub
Releases, not GitHub's automatically generated source-code ZIP. The source ZIP
does not contain the compiled desktop, sidecar, or DuckLake binaries.

See [docs/PORTABLE_DEPLOYMENT.md](docs/PORTABLE_DEPLOYMENT.md).

## Current baseline versions

These are the greenfield targets selected on **2026-09-16**. Stable releases are preferred over previews.

| Area | Baseline |
| --- | --- |
| Python | 3.14.7 |
| DuckDB | 1.5.5; 2.0 intentionally deferred until stable |
| DuckLake | 1.0 format / current stable extension |
| Polars | 1.44.2; 2.0 RC intentionally not used |
| FastAPI | 0.141.1 |
| OR-Tools | 9.15.6755 |
| React | 19.3.0 |
| TypeScript | 7.0.2 |
| Vite | 8.1 line |
| Tauri | 2.11 line |
| Tailwind CSS | 4.3.3 |
| Apache ECharts | 6.1.0 |
| uv | 0.12.13 |
| Ruff | 0.16 line |
| Biome | 2.5.13 |
| PyInstaller | 6.22.3 |

Versions should be upgraded deliberately with CI and portable-build verification, not automatically because a preview exists.

## Development quick start

Python engine:

```powershell
uv sync --extra dev
uv run wfmhub2 init
uv run wfmhub2 serve
```

Frontend:

```powershell
corepack enable
pnpm install
pnpm dev:web
```

Desktop development requires Rust/Tauri tooling on the **developer machine only**:

```powershell
pnpm desktop:dev
```

Run checks:

```powershell
uv run ruff check src tests
uv run pyright
uv run pytest
pnpm check:web
pnpm typecheck:web
pnpm test:web
```

## Engineering principles

- Preserve source evidence; missing evidence remains unknown until a governed rule says otherwise.
- Keep metric definitions deterministic and testable.
- Keep vendor parsing outside the domain layer.
- Keep FastAPI and React free of WFM formulas.
- Make recommendations explainable from governed data.
- Prefer incremental refresh and bounded recomputation.
- Store analytical history in columnar, partitionable structures rather than one monolithic mutable file.
- Keep the Windows portable/offline edition a first-class product.
- Use statistical/ML complexity only when it improves measured forecast performance.
- Record interventions and outcomes so the system learns from operations, not merely reports them.

## Documentation

- [Project vision](PROJECT_VISION.md)
- [System architecture](ARCHITECTURE.md)
- [WFM domain model](docs/WFM_DOMAIN.md)
- [Technology stack](docs/TECH_STACK.md)
- [Incremental refresh engine](docs/REFRESH_ENGINE.md)
- [Forecasting architecture](docs/FORECASTING.md)
- [Portable deployment](docs/PORTABLE_DEPLOYMENT.md)
- [Performance budget](docs/PERFORMANCE_BUDGET.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)

---

**WFMHub 2.0 is a workforce-management decision system first and a software stack second.**
