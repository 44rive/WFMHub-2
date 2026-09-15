# WFMHub 2.0

**Portable workforce intelligence for real-time analysts and workforce managers.**

WFMHub 2.0 sits above workforce-management source systems and operational extracts. It turns schedules, forecasts, attendance, queue activity, call data, and staffing evidence into one governed decision layer for intraday control, tactical planning, and strategic capacity.

> **North star:** tell the WFM user what is happening, why it is happening, what is likely to happen next, and which action has the best expected impact.

WFMHub is not defined by its technology stack. The **product** is the WFM operating model and decision intelligence. The **stack** is how that product is implemented while remaining fast, portable, auditable, and practical on locked-down Windows machines.

## Project vision

Traditional WFM tools are often strong systems of record but weak day-to-day decision workbenches. Data is scattered across vendor exports, telephony files, schedules, spreadsheets, and local knowledge. RTAs spend time reconciling facts before they can act; workforce managers spend time rebuilding the same staffing, forecasting, and capacity views in Excel.

WFMHub 2.0 is designed as a **vendor-neutral workforce intelligence layer** that preserves source authority while adding a common WFM model, deterministic calculations, risk detection, scenario modelling, optimization, and action learning.

The operating loop is:

```text
Observe  ->  Explain  ->  Predict  ->  Recommend  ->  Decide  ->  Learn
   ^                                                              |
   +--------------------------------------------------------------+
```

The project grows along the same path as a WFM career:

```text
Intraday / RTA
    -> Forecasting & staffing
        -> Scheduling & shrinkage
            -> Capacity & hiring
                -> Workforce strategy
```

See [PROJECT_VISION.md](PROJECT_VISION.md) for the full product definition.

## What WFMHub 2.0 will do

### Intraday / RTA intelligence

The RTA Command Center is the first-class product surface. For each service scope and interval it should answer:

- Are we meeting service now?
- Are we correctly staffed now?
- What explains the gap?
- Where will the next 2–4 hours become risky?
- Which operational intervention is available?
- What happened after the intervention?

Core products include current staffing and service, gap decomposition, attendance evidence, intraday risk horizon, intervention recommendations, and a decision/outcome log.

### Tactical workforce management

WFMHub expands from “what is happening now?” to “why does this keep happening?” through forecast accuracy, bias analysis, independent staffing requirements, schedule quality, shrinkage patterns, PTO/training capacity, and scenario planning.

### Strategic workforce planning

The longer-term layer models headcount, hiring need, attrition, shrinkage, budget, outsourcing, and demand scenarios across weeks and months.

## Product architecture vs technology architecture

These are deliberately separate concepts.

### Product architecture

```text
Source evidence
      |
      v
Governed WFM model
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
Decision log + measured outcomes
      |
      v
Learning and better future recommendations
```

### Technology architecture

```text
                  React + TypeScript UI
                           |
                        FastAPI
                           |
        +------------------+-------------------+
        |                  |                   |
   WFM domain         Intelligence        Optimization
     engine              engine             OR-Tools
        |                  |                   |
        +------------------+-------------------+
                           |
                 +---------+---------+
                 |                   |
              SQLite              DuckDB
           control plane        analytics plane
                 |                   |
                 |             Parquet lake
                 |                   |
                 +---------+---------+
                           |
                  Polars ingestion
                           |
           Verint / Storm / CSV / Excel
```

The stack is explained in detail in [docs/TECH_STACK.md](docs/TECH_STACK.md).

## WFM capability map

| Horizon | Primary question | Planned capabilities |
| --- | --- | --- |
| Intraday | What is happening and what should I do now? | Service, coverage, attendance, 2–4h risk, gap drivers, interventions, decision log |
| Tactical | Why are we repeatedly missing and how do we plan better? | Forecast accuracy, Erlang/staffing, schedule quality, shrinkage, scenarios, PTO/training capacity |
| Strategic | How many people will we need and when? | Capacity plans, hiring, attrition, budget, outsourcing and long-range scenarios |

The domain model and WFM concepts live in [docs/WFM_DOMAIN.md](docs/WFM_DOMAIN.md).

## Core data flow

WFMHub keeps source data reproducible and refreshes incrementally.

```text
Untouched extracts
      |
      v
BRONZE  source-faithful normalized Parquet
      |
      v
SILVER  mapped/scoped canonical WFM facts
      |
      v
GOLD    DuckDB marts and intelligence products
      |
      v
API / UI / Excel handoffs / optimization
```

A refresh is based on **what changed**, not on how much history exists. Unchanged historical periods stay cold. If one day changes, that day and its dependent models are rebuilt; six months of unrelated history are not.

See [docs/REFRESH_ENGINE.md](docs/REFRESH_ENGINE.md).

## Technology stack

| Layer | Technology | Why it exists |
| --- | --- | --- |
| Core | Python 3.13 | WFM rules, orchestration, forecasting, modelling |
| API | FastAPI + Uvicorn | Typed local API boundary for UI and integrations |
| Control database | SQLite | Small transactional state, manifests, decisions, config and audit |
| Analytics database | DuckDB | Fast scans, joins and aggregations over large WFM history |
| Data processing | Polars | High-throughput normalization and complex dataframe transforms |
| Historical storage | Parquet | Compact, columnar, partitionable analytical history |
| Optimization | OR-Tools CP-SAT | Shift, coverage and allocation optimization |
| UI | React + TypeScript + Vite | Maintainable interactive WFM workbench |
| Visualization | Apache ECharts | Dense interval, staffing and forecast visualizations |
| Handoffs | XlsxWriter + OpenPyXL | Governed Excel outputs where business workflows still require them |

## Why both SQLite and DuckDB?

SQLite is the **control plane**: mappings, manifests, refresh state, decisions, scenarios, audit, and other small mutable application data.

DuckDB is the **analytics plane**: call history, interval facts, schedule/attendance models, forecast comparisons, staffing marts, scenarios, and risk calculations.

Keeping these responsibilities separate lets analytical data be rebuilt or archived without risking the operational history of decisions and configuration.

## Repository structure

```text
WFMHub-2/
├─ src/wfmhub2/
│  ├─ adapters/          vendor/file-specific input contracts
│  ├─ analytics/         analytical pipelines and materializations
│  ├─ api/               FastAPI application and routes
│  ├─ core/              settings and shared platform primitives
│  ├─ domain/            WFM business logic
│  │  ├─ attendance/
│  │  ├─ capacity/
│  │  ├─ forecasting/
│  │  ├─ scheduling/
│  │  ├─ service/
│  │  └─ staffing/
│  ├─ ingestion/         discovery, fingerprints, refresh orchestration
│  ├─ intelligence/      risk, interventions, scenarios, patterns
│  ├─ optimization/      OR-Tools staffing/scheduling models
│  ├─ reports/           Excel/CSV handoffs
│  └─ storage/           SQLite and DuckDB access
├─ web/                  React / TypeScript frontend
├─ config/               example governed configuration
├─ data/                 local runtime data; ignored by Git
├─ docs/                 product and engineering documentation
├─ packaging/            portable Windows launchers
├─ scripts/              build and release tooling
└─ tests/                unit and integration tests
```

The physical code structure follows the **business domains**, not vendor names. Vendor-specific behavior belongs under `adapters/`; staffing logic belongs under `domain/staffing/`; RTA risk belongs under `intelligence/risk/`.

## Portable by design

The target release remains an unzip-and-run Windows application:

```text
WFMHub-2/
├─ WFMHub.cmd
├─ Feed/
├─ Reports/
└─ _system/
   ├─ python/          embedded CPython
   ├─ site-packages/   bundled runtime dependencies
   ├─ app/             Python application
   └─ web/             pre-built React assets
```

End users should need **no administrator rights, no installed Python, no Node.js, no database server, and no internet connection**. Node is a build-time dependency only.

## Refresh philosophy

The performance contract is simple:

> **Refresh cost should scale with changed data, not total history.**

Examples:

- add today -> process today;
- correct yesterday -> replace yesterday and dependent marts;
- replace a July monthly extract -> rebuild July, not the year;
- change a queue mapping -> rebuild mapped layers from Bronze without reparsing original files;
- parser change -> intentionally invalidate only affected source versions;
- full rebuild -> explicit maintenance operation, never the default refresh.

## Decision intelligence

WFMHub should not stop at dashboards. The long-term differentiator is the decision loop.

An intervention record can capture:

```text
10:43  RSA NL
Reason:        TSL below target; staffing gap -3.2 FTE
Decision:      Return two training agents to phones
Expected:      +1.8 productive FTE
Observed:      TSL recovered from 61% to 78% within 30 minutes
```

Over time, that enables WFMHub to learn which interventions tend to work, under which conditions, while keeping the underlying metrics deterministic and auditable.

## Current status

WFMHub 2.0 is at the architecture/bootstrap stage. The repository establishes the target boundaries before vendor-specific production logic is migrated.

Initial foundations include:

- SQLite control-plane schema;
- DuckDB analytical schemas;
- incremental refresh contract;
- adapter interface;
- RTA risk model seed;
- OR-Tools optimization seed;
- FastAPI health/refresh endpoints;
- React workbench shell;
- Windows portable packaging direction;
- Python and frontend CI.

The implementation roadmap is in [docs/ROADMAP.md](docs/ROADMAP.md).

## Development quick start

Python:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
wfmhub2 init
wfmhub2 serve
```

The API binds to `127.0.0.1:8765` by default.

Frontend development:

```powershell
cd web
npm install
npm run dev
```

Runtime layout:

```text
data/
├─ inbox/       untouched inbound extracts
├─ lake/        Bronze/Silver partitioned Parquet history
├─ db/          SQLite + DuckDB databases
└─ exports/     generated Excel/CSV products
```

Runtime data is ignored by Git. Only synthetic fixtures should be committed.

## Engineering principles

- Preserve source evidence; never invent missing operational facts.
- Keep metric definitions deterministic and testable.
- Keep vendor parsing outside the WFM domain model.
- Make every recommendation explainable from governed data.
- Default to incremental refresh and bounded recomputation.
- Prefer simple local operation over infrastructure for infrastructure's sake.
- Keep the portable Windows distribution a first-class product, not an afterthought.

## Documentation

- [Project vision](PROJECT_VISION.md)
- [System architecture](ARCHITECTURE.md)
- [WFM domain model](docs/WFM_DOMAIN.md)
- [Technology stack](docs/TECH_STACK.md)
- [Incremental refresh engine](docs/REFRESH_ENGINE.md)
- [Performance budget](docs/PERFORMANCE_BUDGET.md)
- [Portable deployment](docs/PORTABLE_DEPLOYMENT.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)

---

**WFMHub 2.0 is being built as a workforce-management decision system first and a software stack second.**
