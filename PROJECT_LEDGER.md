# WFMHub 2 Project Ledger

Last updated: 2026-09-19

This is the durable project handoff. Read it before exploring the repository.
Update it after material work so the next human or AI session starts from known
state instead of repeating discovery.

## Mission and current milestone

Build a trustworthy, portable WFM decision layer, beginning with an RTA product
and expanding only after the governed evidence and operational workflow work.

**Active milestone: Phase 0 — stack qualification.** Prove the complete desktop
walking skeleton on a clean Windows environment before adding more WFM features.

## Repository and branch state

| Ref | Purpose | State |
| --- | --- | --- |
| `origin/main` at `ec49670` | 2026 greenfield/Tauri/DuckLake major update | Architecture seed; not release-ready |
| local `main` at `e943a05` | Pre-update governed contracts and storage work | Preserve; four commits ahead of the old baseline, one unstaged time cleanup |
| `integration/stack-qualification` | Authoritative Phase 0 integration branch | Active |
| `integration/stack-backend` | Isolated Python/storage worker branch | Active during Phase 0 |
| `integration/stack-desktop` | Isolated Tauri/frontend worker branch | Active during Phase 0 |
| `integration/stack-foundation` | Isolated locks/CI/tooling worker branch | Active during Phase 0 |

Do not merge the upstream repository replacement directly into the preserved
local `main`. Integrate reviewed logical changes on the qualification branch.

## Settled decisions

| ID | Decision | Reason |
| --- | --- | --- |
| D-001 | Qualify the full stack before WFM feature development. | Dependency resolution does not prove launch, offline behavior, or shutdown. |
| D-002 | Preserve and selectively port prior governed WFM work. | It contains source contracts, exact mappings, KPI evidence, migrations, and tests absent from the major update. |
| D-003 | Do not use one null-heavy universal interval fact. | Demand/service, forecast/requirement, schedule, and attendance have different grains and authorities. |
| D-004 | SQLite is the control plane; DuckLake/Parquet is provisional for analytical history. | DuckLake remains contingent on offline Windows packaging, recovery, correction, and performance evidence. |
| D-005 | Heavy forecasting/ML/optimization libraries must not block core startup. | They increase size and native packaging risk and belong behind explicit capability checks. |
| D-006 | Portable runtime binds to loopback and uses a per-launch token, restricted origins, explicit home, and owned sidecar lifecycle. | Loopback alone is not a sufficient desktop security/lifecycle boundary. |
| D-007 | Import only business contracts/configuration from WFMHub-Portable, never operational or personal data. | Preserve privacy and reproducibility. |
| D-008 | Tauri generates a 256-bit token, passes it to the owned sidecar through `WFMHUB2_SESSION_TOKEN`, and exposes connection details only through a narrow command. | Avoid fixed ports, generic shell access, and token exposure in process arguments or logs. |

## Evidence already collected

- The complete major-update tree, documentation, source, tests, packaging, and
  dependency definitions were reviewed.
- Python 3.14 Windows x64 wheels resolve for the declared Python dependency set.
  This proves availability, not PyInstaller compatibility.
- The major-update baseline has 5 lightweight Python tests passing under the
  available Python 3.12 environment; its declared runtime is Python 3.14.
- Baseline Python Ruff checks fail with 5 findings.
- Baseline frontend Vitest passes, but Biome, TypeScript, and production build
  fail. No lockfiles are committed.
- No bundled DuckLake extension is present, so the documented portable build
  fails its own extension precondition.
- The API currently uses module-global settings rather than the CLI `--home`,
  and no CORS/session-token boundary is implemented.
- An independent Linux probe with DuckDB 1.5.5 successfully loaded an explicit
  local DuckLake extension, wrote a Zstd Parquet-backed table, closed, reopened,
  and read the same 100 rows. DuckLake data inlining had to be disabled to prove
  a physical Parquet write. This is positive technology evidence, not yet an
  application or Windows gate pass.
- The preserved local branch has 30 Python tests passing and frontend
  lint/build passing, but still has format and test typing cleanup outstanding.

## Phase 0 acceptance gates

Status values: `TODO`, `PASS`, `FAIL`, or `BLOCKED`.

| Gate | Status | Required evidence |
| --- | --- | --- |
| Reproducible dependency locks | TODO | Frozen Python, pnpm, and Cargo installs from a clean checkout |
| Python quality | TODO | Ruff, Pyright, and pytest on Python 3.14 |
| Frontend quality | PASS | Biome, TypeScript, 5 Vitest contract tests, and production build pass locally on Node 22/pnpm 12 |
| Core storage probe | TODO | SQLite plus offline local DuckLake load, write, restart, and read |
| Native-library probe | TODO | Packaged Polars, DuckDB, forecast, XGBoost, and OR-Tools smoke operations |
| Secure engine launch | TODO | Loopback, per-launch token, restricted origin/host, explicit portable home |
| Desktop lifecycle | TODO | Tauri starts engine, receives readiness, UI reaches health, close kills engine |
| Portable persistence | TODO | Writable co-located data survives restart; read-only location fails clearly |
| Offline runtime | TODO | Clean Windows run with network unavailable and no developer runtimes installed |
| Windows package | TODO | PyInstaller sidecar and Tauri package built from clean runner |
| Operational budget | TODO | Record package size, cold start, idle memory, extension load time |

Phase 0 is complete only when all gates pass. A gate may be deliberately removed
only through a recorded decision with evidence.

## Current risks and fallbacks

- If DuckLake cannot load reliably offline or recover safely, use the preserved
  immutable-generation DuckDB/Parquet implementation.
- If Python 3.14/PyInstaller fails on Windows, test and document Python 3.13 as
  the compatibility baseline.
- If heavy analytical libraries make core launch too large or slow, split them
  into optional/lazy capabilities and keep the RTA core minimal.
- Fixed port `8765` can collide; readiness and connection details must be owned
  by the desktop launcher rather than hard-coded in React.

## Next executable steps

1. Commit this ledger and repository instructions on the integration branch.
2. Produce independent backend, desktop, and foundation qualification commits.
3. Review and integrate those commits onto `integration/stack-qualification`.
4. Run all Linux-available checks locally.
5. Add a Windows clean-runner workflow for the build/launch/offline gates.
6. Record every gate result here before starting the first WFM vertical slice.

## Session log

### 2026-09-19 — Linux backend walking skeleton qualified

- Added an explicit `create_app(settings, token)` API factory; removed divergent
  module-global settings. Health is public, while stack and refresh probes require
  `X-WFMHub-Token`. Trusted hosts, CORS origins, and server binds are loopback-only.
- Production launch tokens now come from the child-only
  `WFMHUB2_SESSION_TOKEN` environment. The CLI override is development-only, and
  readiness, health, doctor output, settings, and errors never contain the token.
- `serve --port 0` now pre-binds an ephemeral socket and emits one parseable
  `WFMHUB2_READY` line after Uvicorn startup with the actual port.
- Added deterministic core and full doctor probes. Offline mode uses explicit
  `LOAD` only; development mode is the only mode allowed to use DuckDB's extension
  repository. The DuckLake probe disables data inlining, requires a new managed
  Zstd Parquet file, then closes/reopens the catalog and verifies the data.
- Linux evidence under CPython 3.12 (supplementary, not the required 3.14 gate):
  Ruff passed, Pyright strict passed, and 14 tests passed. Development and explicit
  offline DuckLake 1.0 probes passed with DuckDB 1.5.5 and extension version
  `d8a1881e`; SQLite and DuckLake both survived reopen.
- The full explicit-offline probe passed real Polars 1.44.2, StatsForecast 2.1.1,
  XGBoost 3.4.1, and OR-Tools 9.15 operations. A live engine launch selected an
  ephemeral port, emitted readiness, served health, accepted the correct token for
  the protected probe, and terminated cleanly.
- These results do **not** close the Windows/Python 3.14/PyInstaller/Tauri gates.
  The tested extension came from the Linux development cache and is not a release
  artifact. Clean Windows offline packaging remains mandatory.
- Integration note: FastAPI 0.141/Starlette's typed test client targets `httpx2`;
  the foundation dependency lock must include it or deliberately pin a compatible
  FastAPI/Starlette/client set. No lockfile was changed on this worker branch.

### 2026-09-19 — Phase 0 opened

- Compared the major update with the preserved governed implementation.
- Chose stack qualification as the blocking milestone.
- Created isolated integration/backend/desktop/foundation worktrees.
- Added the durable ledger contract and initial evidence.
- Proved explicit local-extension DuckLake write/restart/read on Linux using a
  temporary standalone probe; the application-level and Windows gates remain
  open.

### 2026-09-19 — Desktop walking skeleton implemented

- Tauri now generates a per-launch token, passes explicit home/extension paths,
  requests a dynamic loopback port, parses the readiness contract, retains the
  child handle, and kills its owned engine on timeout or desktop exit.
- React receives connection details through `get_engine_connection`; production
  has no browser fallback. Browser development requires an explicit loopback URL
  and token.
- The home page now calls authenticated health and offline stack-probe endpoints
  and displays the SQLite/DuckLake qualification results.
- Local frontend Biome, TypeScript, 5 Vitest tests, and production build pass.
- Rust formatting passes. Linux Rust compilation is blocked by missing GTK/GLib
  development packages; Windows-target checking and full desktop lifecycle
  remain qualification work, not claimed as passing.
