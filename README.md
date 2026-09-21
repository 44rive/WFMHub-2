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

The proposed Phase 1 shell, navigation, component skeleton, and three visual
references are in [docs/UI_BLUEPRINT.md](docs/UI_BLUEPRINT.md).

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

### Technology architecture — target-compatible baseline

```text
WFMHub.cmd
    |
    v
Official embedded CPython 3.13.7
  stdlib localhost server
  governed pure-Python WFM services
  authoritative SQLite + Excel/CSV outputs
    |
    | stable 127.0.0.1:8420 origin + per-launch token
    v
Microsoft Edge
  React / TypeScript WFM workbench
  optional DuckDB-Wasm + OPFS analytical cache
  optional Pyodide forecasting worker
  optional HiGHS-Wasm optimization worker
```

This topology follows measured corporate-policy evidence. Native Python
analytics remain available for development or a future IT-managed deployment,
but they are not allowed to block the target portable RTA core. See
[docs/TECH_STACK.md](docs/TECH_STACK.md).

## Data architecture

Configured source extracts and `data/control.sqlite` are authoritative.
SQLite stores manifests, governed facts, marts, mappings, refresh runs,
decisions, scenarios, and audit state. DuckDB-Wasm may keep derived analytical
tables in browser OPFS for speed, but that cache must be rebuildable because
browser storage is not a durable system of record.

Bronze, Silver, and Gold describe responsibilities rather than mandatory
physical databases:

```text
read-only source evidence
        |
        v
Bronze: source-faithful typed rows + provenance
        |
        v
Silver: governed vendor-neutral WFM facts
        |
        v
Gold: RTA / staffing / forecast / decision products
        |
        +--> React workbench
        +--> Excel / CSV
        +--> optional browser analytical cache
```

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

Every activated generation must retain enough provenance to answer “what did
we know when this staffing decision was made?”

See [docs/REFRESH_ENGINE.md](docs/REFRESH_ENGINE.md).

## Forecasting architecture

Forecasting is a governed model-selection pipeline rather than a single “AI forecast.”

```text
Historical demand
      |
      +--> Explainable seasonal baselines        portable Python
      |
      +--> Statistical models                    Pyodide + statsmodels
      |
      +--> Feature-based candidate models        Pyodide + scikit-learn
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

HiGHS-Wasm is the target-profile candidate for linear and mixed-integer WFM
problems such as:

- interval coverage;
- shifts and tours;
- skill eligibility;
- break/lunch placement;
- contract hours and rest rules;
- training placement;
- cross-skill allocation;
- preference and fairness constraints.

The optimizer consumes governed domain inputs. It is not an OR-Tools CP-SAT
drop-in, and solver code never owns WFM definitions. Native OR-Tools remains a
trusted/server-profile option.

## Repository structure

```text
WFMHub-2/
├─ src/wfmhub2/
│  ├─ adapters/          Verint / Storm / CSV / Excel source contracts
│  ├─ analytics/         DuckDB analytical pipelines
│  ├─ api/               trusted/server transport
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
│  ├─ optimization/      solver-independent model contracts
│  ├─ reports/           Excel/CSV business handoffs
│  └─ storage/           SQLite authority + optional analytical adapters
├─ src/wfmhub2_compat/   stdlib-only target host
├─ web/                  React / TypeScript workbench
├─ docs/                 product and engineering documentation
├─ config/               example governed configuration
├─ data/                 local runtime state; ignored by Git
├─ packaging/            reviewed portable-runtime inputs
├─ scripts/              build/release tooling
└─ tests/                unit, property and integration tests
```

The physical structure follows **business domains**, not source vendors. Verint parsing belongs in `adapters/verint`; staffing rules belong in `domain/staffing`; risk belongs in `intelligence/risk`.

## Portable local model

The target Windows release is still portable/offline:

```text
WFMHub-2/
├─ WFMHub.cmd                 primary local launcher
├─ DOCTOR.cmd                 Python/SQLite/Excel host qualification
├─ README-FIRST.txt
├─ SHA256SUMS.txt
├─ Feed/
├─ Reports/
├─ data/                         created locally on first use; not shipped
│  ├─ control.sqlite
└─ _system/
   ├─ runtime/                official CPython + pure Python wheel archives
   ├─ app/                    stdlib-only local host
   ├─ web/                    React, Workers, WASM, Pyodide packages
   └─ manifests/              exact origin and SHA-256 inventories
```

End users should require:

- no administrator rights;
- no installed Python;
- no Node.js;
- no Rust toolchain;
- no database server;
- no internet connection during normal operation.

Node and uv are build-time tools only. The target computer launches the
official embedded `python.exe`; it does not install Python or dependencies.
Every browser and Python asset is self-hosted in the ZIP.

End users must download the versioned Windows portable asset from GitHub
Releases, not GitHub's automatically generated source-code ZIP. The source ZIP
does not contain the embedded runtime, pure Python wheels, compiled web assets,
or WebAssembly packages.

The historical [v0.2.0 Phase 0.1 preview](https://github.com/44rive/WFMHub-2/releases/tag/v0.2.0-phase0.1)
uses the retired executable delivery path and is blocked on the target managed
workstation. The replacement embedded-CPython preview is published only after
its exact ZIP passes Windows CI; it is still stack qualification, not the
finished WFM product.

See [docs/PORTABLE_DEPLOYMENT.md](docs/PORTABLE_DEPLOYMENT.md).

## Current baseline versions

These are the target-compatible baselines selected on **2026-09-20**. Stable
releases are preferred over previews.

| Area | Baseline |
| --- | --- |
| Python | 3.13.7 policy-compatibility baseline |
| Host HTTP | Python 3.13 standard library |
| SQLite | CPython-bundled; authoritative portable store |
| DuckDB-Wasm | 1.32.0; rebuildable OPFS cache |
| Pyodide | 0.29.5 |
| Browser forecasting | scikit-learn 1.7.0 + statsmodels 0.14.4 |
| Browser optimization | highs 1.15.3 |
| React | 19.3.0 |
| TypeScript | 7.0.2 |
| Vite | 8.1 line |
| Tailwind CSS | 4.3.3 |
| Apache ECharts | 6.1.0 |
| uv | 0.12.13 |
| Ruff | 0.16 line |
| Biome | 2.5.13 |

Versions should be upgraded deliberately with CI and portable-build verification, not automatically because a preview exists.

## Development quick start

Python development environment:

```powershell
uv sync --extra dev
uv run pytest
```

Frontend:

```powershell
corepack enable
pnpm install
pnpm dev:web
```

Build the hybrid compatibility release:

```powershell
python scripts/stage_browser_runtime.py
pnpm build:web
python packaging/windows/build_hybrid_spike.py
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
- Keep HTTP handlers and React free of WFM formulas.
- Make recommendations explainable from governed data.
- Prefer incremental refresh and bounded recomputation.
- Keep browser analytical storage rebuildable from authoritative evidence.
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
