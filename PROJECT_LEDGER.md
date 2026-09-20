# WFMHub 2 Project Ledger

Last updated: 2026-09-20

This is the durable project handoff. Read it before exploring the repository.
Update it after material work so the next human or AI session starts from known
state instead of repeating discovery.

## Mission and current milestone

Build a trustworthy, portable WFM decision layer, beginning with an RTA product
and expanding only after the governed evidence and operational workflow work.

**Active milestone: Phase 0.2 — official-CPython portable qualification.** Keep
the complete WFM/data/forecasting/optimization stack, replace the blocked
Tauri/PyInstaller delivery shell with the already proven embedded-CPython + CMD
operating model, and prove the exact release ZIP on the target corporate PC.

## Repository and branch state

| Ref | Purpose | State |
| --- | --- | --- |
| `origin/main` at `a16da3e` | Merged initial Phase 0 qualification | Behind the qualified Phase 0.1 preview and current Phase 0.2 work |
| local `main` at `e943a05` | Pre-update governed contracts and storage work | Dirty/divergent user worktree; preserve and do not use for integration |
| `integration/stack-qualification` (current HEAD) | Authoritative integration/release branch | Active; runtime and packaging commits merged |
| `integration/embedded-runtime` at `aeb5ff1` | Browser-served runtime and full doctor worker | Complete and merged as `f888d7f` |
| `integration/embedded-packaging` at `e7b8870` | Embedded CPython release/CI worker | Complete and merged as `7be8032` |
| `WFMHub-Portable` | Proven earlier embedded-CPython product and business-contract source | Read-only reference; never copy user data |

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
| D-006 | Portable runtime binds to loopback and uses a per-launch token, restricted hosts/origins, explicit home, and console-owned lifecycle. | Loopback alone is not a sufficient local security/lifecycle boundary. |
| D-007 | Import only business contracts/configuration from WFMHub-Portable, never operational or personal data. | Preserve privacy and reproducibility. |
| D-008 | The Python process generates a 256-bit per-launch browser credential and binds an ephemeral loopback port. | Avoid fixed ports and prevent unrelated local pages from invoking protected APIs. |
| D-009 | `WFMHub.cmd` remains the visible lifecycle owner; the embedded Python server stops on Ctrl+C/window close. | The supported product must behave like the proven older portable app without a custom launcher process. |
| D-010 | Ship the complete frozen production dependency graph in one ZIP, preserving wheel layouts; lazy-import heavy capabilities during normal use. | The user requested one complete offline product, while ordinary RTA startup must remain bounded and diagnosable. |
| D-011 | End users receive a versioned GitHub Release ZIP, never GitHub's source-code ZIP. | The source archive excludes all ignored native build artifacts and cannot satisfy `unzip -> run`. |
| D-012 | Retire Tauri, Rust, PyInstaller, WebView2, and the custom WFMHub executables from the active build. | Both unsigned custom executables were blocked by target enterprise policy; CMD invoking official embedded CPython is already proven there. |
| D-013 | WFMHub is single-user/local-only: read configured source folders directly and never add an upload or cloud path. | This is the actual operating context and privacy boundary. |
| D-014 | The full doctor must start with only the standard library and isolate native probes in child processes. | One blocked or crashing `.pyd`/`.dll` must produce a named failure rather than prevent diagnosis of the rest of the stack. |
| D-015 | Corporate-PC execution of the exact extracted ZIP is a release gate, not an assumption. | CMD does not bypass WDAC/AppLocker rules applied to bundled native libraries. |

## Evidence already collected

- The target workstation rejects the unsigned Phase 0.1 `WFMHub.exe` /
  PyInstaller engine under enterprise application control even after ordinary
  Windows unblock steps. The problem is policy enforcement, not installation:
  the old executable only launches and extracts its one-file payload.
- The earlier WFMHub-Portable product works on the same workstation using
  `WFMHub.cmd` -> official CPython embeddable `python.exe` -> local Python
  package. It installs nothing, reads local source folders directly, and keeps
  SQLite state beside the product.
- Python 3.14.7's official Windows x64 embeddable archive is available and
  pinned by SHA-256
  `d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15`.
- The frozen Windows production closure is 75 distributions, approximately
  `269.4 MiB` of compressed wheels and `795 MiB` extracted before the Python
  runtime, app, web assets, and DuckLake extension. It contains 378 third-party
  PE files; 371 have no Authenticode certificate table. This makes technical
  packaging feasible but corporate-policy compatibility unproven.
- Windows x64 CPython 3.14 wheels exist in the lock for DuckDB, Pydantic Core,
  Polars, NumPy, SciPy, Pandas, PyArrow, XGBoost, OR-Tools, and the remaining
  production graph. Existing Windows CI already executed the native stack
  under installed Python 3.14; the new gate is execution from the embedded,
  exact extracted release.
- The browser architecture needs no WebView runtime. Compiled React assets and
  FastAPI share one ephemeral `127.0.0.1` origin, with a fresh per-launch
  credential; the CMD console owns shutdown.
- GitHub Actions run `35507061319` passed the complete Linux job but stopped in
  Windows source tests before packaging. It exposed two Windows-specific bugs:
  Starlette hands a mounted static application backslash-normalized paths, so an
  unknown `/api/...` route incorrectly received the SPA fallback, and SQLite's
  context manager did not close the temporary backup connection, leaving the
  file locked during cleanup. API prefix normalization and explicit SQLite
  connection closing now have local regression coverage; the corrected Windows
  pipeline remains pending.
- The lines below retain historical qualification evidence for the superseded
  Tauri/PyInstaller Phase 0.1 experiment.
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
- Run `35467361420` passed every Linux and Windows gate, including the Win32
  live/missing PID regression, exact ZIP expansion, cold launch of the extracted
  desktop, frontend-initiated authenticated SQLite/DuckLake/Parquet activity,
  outbound-blocked direct engine probing, and owned-process shutdown. The final
  ZIP is 241,753,224 bytes with SHA-256
  `c3cf1e020f949415efd1205db9bdc4459212b8406bc3e145df9077667614ed2b`.
  Desktop-to-stable storage activity was 17.422 seconds; direct engine readiness
  was 9.872 seconds. The pre-release is `v0.2.0-phase0.1`.
- The optimized Linux sidecar is `303,345,488` bytes, down 49.1% from the
  initial `596,396,352`-byte build. Shell + sidecar + DuckLake total about
  `355.1 MB` before installer compression. Observed cold readiness was
  `10.25 s`, total desktop-process idle RSS was about `527 MiB`, packaged full
  doctor was `11.34 s` with about `385 MiB` peak RSS, and median explicit
  DuckLake load was `38.1 ms`. These are evidence, not yet release targets.

## Phase 0.2 acceptance gates

Status values: `TODO`, `PASS`, `FAIL`, or `BLOCKED`.

| Gate | Status | Required evidence |
| --- | --- | --- |
| Frozen Python/frontend inputs | PASS | Existing `uv.lock` and `pnpm-lock.yaml`; exact versions remain enforced in CI |
| Official embedded CPython provenance | TODO | Download hash, origin manifest, unchanged signed CPython-native manifest, isolated `_pth` |
| Complete dependency payload | TODO | Entire frozen production closure installed without pip/build activity on the target |
| Python/frontend quality | PASS | Local Python 3.14.7: Ruff format/lint, strict Pyright, 21 pytest; frontend: Biome, TypeScript, 6 Vitest, production build |
| Full subprocess doctor | TODO | Every storage, dataframe, forecast, reconciliation, ML, optimization, Excel, API, and web capability executes independently |
| Offline DuckLake | TODO | Explicit bundled extension writes physical Parquet, reopens, and reads with extension auto-install/autoload disabled |
| Browser/API security | TODO | Ephemeral loopback, clean browser bootstrap, authenticated/unauthenticated HTTP tests, strict host/origin boundary |
| Exact ZIP verification | TODO | Deterministic archive, complete member/native hashes, no user data or custom application executable |
| Windows offline/lifecycle | TODO | Expanded ZIP runs with outbound blocked, serves React/API, persists/restarts, and stops cleanly |
| Corporate App Control | BLOCKED | User runs `DOCTOR.cmd` from the exact release ZIP on the managed workstation; every native child probe passes |
| Operational budget | TODO | Record ZIP/extracted size, file count, doctor duration, and normal cold-start/memory measurements |

Phase 0.2 is complete only when all gates pass. A gate may be deliberately removed
only through a recorded decision with evidence.

## Current risks and fallbacks

- **Primary risk:** the complete stack adds 371 unsigned third-party PE files.
  Official `python.exe` being allowed does not imply those `.pyd`/`.dll` files
  are allowed. If the exact doctor fails, identify the blocked capability in
  Windows Code Integrity/AppLocker logs, then remove/replace it or request a
  narrow IT allowlist; do not attempt a policy bypass.
- The release will be large: roughly `795 MiB` of unpacked `site-packages`
  before runtime/app/assets, about 13,000 dependency files, and likely a ZIP in
  the high hundreds of MiB. Extraction/antivirus scanning may dominate first
  use. Measure before pruning because wheel data/native layouts are fragile.
- OR-Tools/HierarchicalForecast need `MSVCP140`; XGBoost/scikit-learn need
  `VCOMP140`. The exact package must prove DLL discovery without assuming a
  machine-wide Visual C++ or OpenMP installation.
- If DuckLake cannot load reliably offline or recover safely, use the preserved
  immutable-generation DuckDB/Parquet implementation.
- If a heavy analytical dependency is policy-blocked, keep its WFM capability
  contract but replace or defer that implementation explicitly; do not let it
  block normal startup through eager imports.
- GitHub-hosted Windows can prove package completeness and ordinary Windows
  runtime behavior. It cannot reproduce the target company's policy.

## Next executable steps

1. Push the Windows portability repair and keep repairing CI until the embedded
   release artifact is green.
2. Record the final archive hash, size, file count, doctor duration, and startup
   evidence in this ledger and rerun the final commit through CI.
3. Merge the qualified branch to `main` and publish the exact green embedded
   portable ZIP plus adjacent SHA-256 as a prerelease.
4. Run `DOCTOR.cmd` from that exact ZIP on the target corporate workstation.
   This is the go/no-go point for the full all-at-once stack.
5. After the target gate passes, begin the first RTA vertical slice using the
   governed contracts preserved from the old portable repo.

## Session log

### 2026-09-20 — First embedded Windows CI repair

- Pushed the integrated embedded-runtime migration after merging current
  `origin/main`; Linux passed in run `35507061319`.
- Windows run `35507061319` stopped before packaging with 2 of 21 tests failed.
  The SPA's API exclusion assumed POSIX separators, and two raw `sqlite3`
  backup connections stayed open because their transaction context managers do
  not close them. Windows consequently served the browser shell for a missing
  API route and could not remove the temporary SQLite backup.
- Normalized the mounted route before the API-prefix check, added a regression
  using Starlette's Windows path representation, and explicitly closed both
  SQLite backup connections. Local Python 3.14.7 Ruff, strict Pyright, and all
  21 tests pass; frontend Biome, TypeScript, 6 Vitest tests, and production
  build also pass. Corrected Windows package evidence is still pending.

### 2026-09-20 — Embedded-CPython portable migration implemented locally

- Re-inspected the old WFMHub-Portable launch/build/runtime contract and the
  complete WFMHub-2 source, structure, dependency locks, Windows wheels, and
  current CI/release evidence.
- Confirmed that the blocked Phase 0.1 executables do not install software; the
  Tauri shell launches a PyInstaller one-file engine which extracts and loads
  many unsigned native files. Running through CMD would not evade enterprise
  application control.
- Chose the proven portable model: official, hash-pinned CPython 3.14.7
  embeddable runtime, CMD lifecycle, same-origin FastAPI + compiled React in the
  system browser, explicit local DuckLake extension, co-located local state,
  and no upload/cloud/multi-user workflow.
- Kept every requested Python WFM capability in one frozen release while
  requiring heavy imports to remain lazy during normal startup.
- Completed a dependency/native-policy audit: 75 packages, about 795 MiB
  extracted and 378 third-party PE images, of which 371 have no Authenticode
  certificate table. Therefore technical feasibility is positive, but target
  policy compatibility remains honestly unproven until the exact ZIP doctor
  passes there.
- Implemented a same-origin browser runtime with ephemeral loopback port,
  256-bit launch token, compiled React serving, offline storage initialization,
  and CMD-owned clean shutdown. A local real server smoke returned health,
  rejected an unauthenticated protected request with 401, planned an empty
  read-only Feed refresh, served the React entrypoint, and stopped cleanly.
- Implemented a standard-library-only doctor supervisor. Fourteen capabilities
  execute in separate `-I` children: runtime isolation, local paths, Pydantic /
  API imports, SQLite WAL/rollback/backup/quick-check/reopen, DuckLake physical
  Parquet/reopen, Polars, PyArrow Parquet, StatsForecast, MLForecast fit/predict,
  HierarchicalForecast reconciliation, Clarabel QP, XGBoost, OR-Tools, and Excel
  round-trip. All passed locally under Python 3.14.7.
- Implemented the Windows builder around hash-pinned official CPython 3.14.7,
  frozen production wheels, compiled React, pinned DuckLake, locked-wheel
  Microsoft runtime DLLs, deterministic ZIP/member/native manifests, and an
  exact extracted-package smoke with outbound blocking and space/non-ASCII
  paths. Windows execution is still pending.
- Removed active Tauri/Rust/PyInstaller sources, scripts, dependencies, and lock
  entries. Git/tag history retains the Phase 0.1 evidence.
- Final local gates pass: Ruff format/lint, strict Pyright, 21 pytest tests,
  the native-stack probe, Biome, TypeScript, 6 Vitest tests, and the production
  React build.
- Work remains on `integration/stack-qualification`; the dirty local `main` and
  dirty old portable repo remain untouched.

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
- Run `35467361420` passed end to end. The exact extracted ZIP launched the
  desktop and sidecar, produced SQLite/DuckLake/Parquet activity in 17.422
  seconds, passed authenticated offline engine probing with outbound traffic
  blocked, and cleaned up its owned process tree. Local download verification
  independently confirmed the outer checksum, five-member archive layout, and
  all hashes in `SHA256SUMS.txt`.
- Published GitHub pre-release `v0.2.0-phase0.1` from green commit `26dba65`:
  <https://github.com/44rive/WFMHub-2/releases/tag/v0.2.0-phase0.1>. This closes
  the Windows package gate, not the separate clean-workstation offline gate and
  not Phase 0 as a whole.
- Corrected the build invocation and added a versioned, checksummed portable
  ZIP with one `WFMHub-2` root. CI now expands the exact ZIP, launches the actual
  desktop entrypoint, requires authenticated SQLite/DuckLake/Parquet storage
  activity, checks clean sidecar shutdown, completes the authoritative direct
  HTTP probe with outbound traffic blocked, and uploads the ZIP separately.
- The GitHub Release asset is the only supported downloadable preview. GitHub's
  automatically generated source archives are not runnable portable packages.

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
