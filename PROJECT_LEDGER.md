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
| D-009 | The packaged engine watches the desktop PID in addition to Tauri retaining the immediate child handle. | PyInstaller one-file mode has a supervisor/child process tree; killing only the supervisor can orphan the API. |
| D-010 | Package only modules/native assets exercised by the engine, with explicit exclusions for unused GUI, test, GPU, and optional analytics layers. | `collect_all()` produced a 596 MB sidecar and bundled unrelated Spark/Dask/test/plotting code. |
| D-011 | End users receive a versioned GitHub Release ZIP, never GitHub's source-code ZIP. | The source archive excludes all ignored native build artifacts and cannot satisfy `unzip -> run`. |

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
- Phase 0 now has generated Python (`uv.lock`), frontend (`pnpm-lock.yaml`), and
  Rust (`src-tauri/Cargo.lock`) lockfiles. A detached clean checkout with no
  staged native artifacts completed the frozen Python 3.14.7 and pnpm installs,
  locked Cargo checks/tests, and all source-quality suites. Windows packaging
  remains a separate platform gate.
- The Python 3.14.7 native-stack probe completed real DuckDB, Polars,
  StatsForecast, XGBoost, OR-Tools, and Excel round-trip operations. The full
  development environment occupied approximately `1.51 GB`, including about
  `302 MB` for Linux NCCL, `180 MB` for Polars runtime, `157 MB` for PyArrow,
  `112 MB` for SciPy, `87 MB` for XGBoost, and `82 MB` for OR-Tools. This
  confirms that heavy analytics/ML dependencies are a material packaging
  concern.
- The reviewed DuckDB/DuckLake 1.5.5 `windows_amd64` artifact is pinned by
  compressed SHA-256 `4a5180e1654cbbc3fd58afe8c70b3f98187d18e8d8e8c9bf386c3d48e9b8a116`
  and decompressed SHA-256
  `4546a5c6d9bc52cc122bc76e521c996e1ac31e71a25e01c531db8d3bb65e2ef0`.
  The binary is build-staged and ignored, never committed.
- The integrated Python 3.14.7 source passes Ruff format/lint, strict Pyright,
  and 17 tests. The frontend passes Biome, TypeScript, 5 Vitest tests, and its
  production build. Rust passes rustfmt, Clippy with warnings denied, and 5 tests.
- A real Linux release-mode Tauri shell launched the Python 3.14 PyInstaller
  engine from a co-located portable directory, rendered authenticated health
  plus SQLite/DuckLake PASS states, reopened the same storage on a second
  launch, exited cleanly, and left no engine supervisor or worker process.
- Read-only portable-home qualification now produces one sanitized actionable
  message in the desktop instead of a traceback or unexplained exit code.
- GitHub Actions run `35456417569` proved all Linux checks and all Windows
  source/native probes, then failed before packaging because
  `build_portable.ps1` used array splatting for named PowerShell parameters.
  No Windows executable or portable asset was produced by that run.
- Corrected run `35458355085` passed Linux again but stopped in the Windows
  frontend check: Windows checkout converted the files to CRLF and PowerShell
  passed literal `web/*.json` and `web/*.ts` paths to Biome. Packaging was not
  reached. Repository line endings and frontend check paths are now explicit.
- Run `35458499945` passed every Linux and Windows source/native check and built
  both release executables, then Tauri unnecessarily entered its MSI bundler
  and failed on an installer-only icon lookup. The portable build now uses
  Tauri's supported `--no-bundle` mode because the verified ZIP is the release
  package; the next run must still prove the extracted ZIP itself.
- Run `35464407642` successfully built and internally verified the 241,752,552
  byte portable ZIP (`2fa0c5c51bd6aab0b17f9335bf04f59ee980ccc4843d8b942edb30856de9e51e`),
  then its desktop smoke timed out after 60 seconds without observing storage
  activity. The desktop stayed alive, but that run did not isolate packaged
  engine cold start from webview/UI execution. CI now gives the untouched
  desktop a realistic one-file cold-start window, then always tests the
  extracted engine with a separate clean home and outbound traffic blocked so
  it can distinguish desktop integration from engine/package behavior.
- Run `35465501042` isolated the Windows runtime failure. The untouched desktop
  stayed alive and created SQLite plus its DuckLake catalog, while the engine
  disappeared before producing Parquet. The direct packaged engine emitted
  readiness in about 14 seconds and then refused the first health connection.
  Root cause: the parent watchdog used the Unix `os.kill(pid, 0)` existence
  idiom on Windows. That idiom is invalid and potentially destructive under
  CPython's Windows process handling, so owner liveness was lost or misread.
  The watchdog now uses a non-signalling Windows process query and has a
  cross-platform live/missing PID regression test.
- The optimized Linux sidecar is `303,345,488` bytes, down 49.1% from the
  initial `596,396,352`-byte build. Shell + sidecar + DuckLake total about
  `355.1 MB` before installer compression. Observed cold readiness was
  `10.25 s`, total desktop-process idle RSS was about `527 MiB`, packaged full
  doctor was `11.34 s` with about `385 MiB` peak RSS, and median explicit
  DuckLake load was `38.1 ms`. These are evidence, not yet release targets.

## Phase 0 acceptance gates

Status values: `TODO`, `PASS`, `FAIL`, or `BLOCKED`.

| Gate | Status | Required evidence |
| --- | --- | --- |
| Reproducible dependency locks | PASS | Frozen Python 3.14.7, pnpm, and locked Cargo installs/checks passed from a detached clean checkout with no staged native artifacts |
| Python quality | PASS | Ruff, Pyright, and pytest on Python 3.14 |
| Frontend quality | PASS | Biome, TypeScript, 5 Vitest contract tests, and production build pass locally on Node 22/pnpm 12 |
| Rust quality | PASS | rustfmt, Clippy with warnings denied, and Rust tests |
| Core storage probe | PASS | SQLite plus offline local DuckLake load, write, restart, and read |
| Native-library probe | PASS | Linux package executes Polars, DuckDB, StatsForecast, XGBoost, and OR-Tools operations |
| Secure engine launch | PASS | Loopback, per-launch token, restricted origin/host, explicit portable home |
| Desktop lifecycle | PASS | Linux Tauri starts engine, UI reaches authenticated health/storage PASS, graceful close kills both one-file processes |
| Portable persistence | PASS | Writable co-located data survives restart; read-only location shows an actionable failure |
| Offline runtime | TODO | Clean Windows run with network unavailable and no developer runtimes installed |
| Windows package | FAIL | Run `35465501042` proved a Windows-specific parent-watchdog defect after readiness; Win32 process-existence correction pending CI proof |
| Operational budget | PASS | Linux size, cold start, idle memory, full-doctor peak, and extension load recorded above; optimization remains a release concern |

Phase 0 is complete only when all gates pass. A gate may be deliberately removed
only through a recorded decision with evidence.

## Current risks and fallbacks

- If DuckLake cannot load reliably offline or recover safely, use the preserved
  immutable-generation DuckDB/Parquet implementation.
- If Python 3.14/PyInstaller fails on Windows, test and document Python 3.13 as
  the compatibility baseline.
- If heavy analytical libraries make core launch too large or slow, split them
  into optional/lazy capabilities and keep the RTA core minimal.
- The optimized Linux package is still about 303 MB and cold desktop readiness
  is about 10 seconds. Treat optional/lazy analytics and PyInstaller one-folder
  mode as serious follow-up candidates, not cosmetic tuning.
- Linux evidence does not establish Windows DLL discovery, WebView2 behavior,
  firewall assertions, installer layout, or offline clean-machine behavior.
- The first clean Windows packaging attempt failed before PyInstaller because
  of build-script parameter passing. The correction and release-ZIP path require
  a new green Windows run before any preview is published.

## Next executable steps

1. Run the stack-qualification workflow on a clean Windows runner without
   weakening frozen-lock, artifact-hash, authentication, or outbound-network
   assertions.
2. Review uploaded package size, checksum, startup, storage, and native-stack
   evidence; record each acceptance gate result here.
3. Run the final extracted bundle on a clean/offline Windows workstation with
   no developer runtimes and confirm WebView2 behavior.
4. Decide explicit Windows package/startup/memory budgets and whether the core
   engine must split optional forecasting/optimization capabilities.
5. Begin the first WFM vertical slice only after Phase 0 gates pass or a failed
   technology is explicitly replaced through a recorded decision.

## Session log

### 2026-09-19 — Runnable GitHub release path corrected

- Compared the old WFMHub-Portable delivery contract with WFMHub-2. The old
  product published a complete runtime ZIP as a GitHub Release asset and
  explicitly rejected GitHub's source ZIP; WFMHub-2 had no equivalent asset.
- Recorded Windows run `35456417569`: Linux passed, Windows dependency/source,
  DuckLake, and native probes passed, then packaging failed because an argument
  array was incorrectly used for named PowerShell parameter splatting.
- The next run, `35458355085`, exposed a separate cross-platform check defect:
  CRLF checkout plus shell-specific globs made Biome fail before packaging.
  Added a repository line-ending contract and shell-independent explicit paths.
- Run `35458499945` passed all Linux checks and all Windows source, DuckLake,
  native-library, PyInstaller, frontend, and Rust compilation work. It failed
  only after the desktop executable had been built, when the unused MSI bundler
  required installer icon configuration. The release build now skips installer
  bundling and feeds that exact executable into the portable ZIP assembler.
- Run `35464407642` proved that portable ZIP assembly and exact member/hash
  verification work on Windows, then exposed a runtime timeout rather than a
  packaging failure. The next run tests frontend-initiated storage on the clean
  portable root first, then independently tests packaged-engine startup with
  outbound traffic blocked even if the desktop fails; the desktop startup
  watchdog is now 120 seconds instead of 30.
- Run `35465501042` confirmed the packaged engine starts in about 14 seconds but
  exits immediately after readiness because it used an invalid and potentially
  destructive Unix PID-existence idiom on Windows. Replaced that probe with a
  non-signalling Win32 process-handle query and added a regression test that
  runs on both CI platforms.
- Corrected the build invocation and added a versioned, checksummed portable
  ZIP with one `WFMHub-2` root. CI now expands the exact ZIP, launches the actual
  desktop entrypoint, requires authenticated SQLite/DuckLake/Parquet storage
  activity, checks clean sidecar shutdown, completes the authoritative direct
  HTTP probe with outbound traffic blocked, and uploads the ZIP separately.
- This entry records implementation and the prior failure, not a gate pass. A
  GitHub pre-release may be created only after the corrected Windows run passes.

### 2026-09-19 — Clean frozen installs qualified

- Checked out commit `a74b38c` into a detached clean worktree with none of the
  ignored native release artifacts present.
- `uv sync --frozen --extra dev --python 3.14.7`,
  `corepack pnpm install --frozen-lockfile`, and locked Cargo resolution all
  completed from that checkout. Ruff, strict Pyright, 17 Python tests, Biome,
  TypeScript, 5 frontend tests, the production frontend build, rustfmt, Clippy
  with warnings denied, and 5 Rust tests passed.
- Found and corrected a source-only CI override defect: Tauri needs
  `resources: []` to clear the configured release resource map. An empty object
  merges with that map and incorrectly requires a staged DuckLake binary during
  Rust source checks. Release packaging continues to require and validate the
  real binary.
- The reproducible-lock gate is now closed. Windows packaging and a clean
  offline Windows runtime remain the two blocking Phase 0 gates.

### 2026-09-19 — Integrated Linux desktop stack qualified

- Fixed the PyInstaller spec's repository-root resolution; the original spec
  looked for `packaging/src/wfmhub2/cli.py` and could not build.
- Added the missing Tauri icon set and made Tauri invoke the Corepack-pinned
  pnpm rather than assuming a global executable. The real release-mode Tauri
  shell now compiles, not merely its Cargo metadata.
- Added portable-first DuckLake resource resolution with installed-bundle
  fallback. Tauri's Linux resource resolver otherwise passed an `/usr/lib`
  path to an unbundled co-located executable and the engine exited before
  readiness.
- Reproduced and fixed a real PyInstaller one-file lifecycle defect: killing
  the supervisor left the Python API worker alive. Tauri now passes its PID and
  the engine exits when its owning desktop disappears. Two launch/close cycles
  exited 0 with no survivors.
- Added a strict `WFMHUB2_ERROR` contract for a non-writable portable folder.
  Tauri accepts only the known sanitized payload and renders an actionable
  message; arbitrary sidecar output is not exposed to the webview.
- Replaced broad `collect_all()` packaging with actual-import analysis, a
  narrow XGBoost native/data inclusion, and explicit unused-layer exclusions.
  The package fell from 596.4 MB to 303.3 MB while the packaged full doctor
  continued to pass every required native operation.
- Fixed both CI Rust source-check steps so Tauri source tests do not require
  release-staged native artifacts; the actual Windows package step still
  validates the real sidecar and resource. Added explicit Linux pkg-config and
  D-Bus development prerequisites.
- All claims in this entry are Linux qualification evidence. Clean Windows CI
  and a no-developer-runtime offline workstation remain blocking Phase 0 gates.

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
- Integration review aligned the backend/Tauri readiness contract to a strict
  port-only JSON payload and aligned allowed development origins with Vite's
  configured `127.0.0.1:5173` endpoint.
- These results do **not** close the Windows/Python 3.14/PyInstaller/Tauri gates.
  The tested extension came from the Linux development cache and is not a release
  artifact. Clean Windows offline packaging remains mandatory.
- Integration replaced the deprecated `httpx` test-client dependency with
  `httpx2`; this restored strict Pyright typing for the FastAPI tests and is
  captured in the regenerated Python lock.

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

### 2026-09-19 — Qualification foundation prepared

- Generated hash/integrity-bearing uv, pnpm, and Cargo locks with uv 0.12.17,
  pnpm 12.4.1, and Rust 1.98.1. Verified frozen Python/pnpm installs and locked
  Cargo metadata/fetch locally; clean-runner validation remains outstanding.
- Added Linux source-quality and Windows portable qualification CI. Windows CI
  stages and compatibility-tests the exact local DuckLake extension, exercises
  the heavy native stack, builds PyInstaller and Tauri outputs, blocks packaged
  engine outbound traffic, checks dynamic readiness/authentication, and records
  hashes, sizes, and cold-start evidence.
- Added fail-closed extension staging and probes. Unknown platform/version
  combinations, hash mismatches, missing artifacts, DuckDB version mismatch,
  failed restart/read, and absent Parquet output all stop packaging. The probe
  passed locally with the matching DuckDB/DuckLake 1.5.5 Linux artifact;
  Windows artifact execution still requires Windows CI.
- Local Python 3.14.7 results: 5 tests pass and the native-stack probe passes.
  Baseline application quality still fails with 2 Ruff-format findings, 5 Ruff
  lint findings, 6 Pyright findings, Biome formatting/import/non-null findings,
  the missing Vite CSS type declaration, and Rustfmt differences in the Tauri
  shell. These belong to the backend and desktop integration commits rather
  than the tooling-only foundation commit.
- Windows extension compatibility, PyInstaller/Tauri packaging, authenticated
  sidecar readiness, desktop lifecycle, and offline clean-machine execution
  remain unproven until the workflow runs after backend/desktop integration.
