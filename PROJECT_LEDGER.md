# WFMHub 2 Project Ledger

Last updated: 2026-09-21

This is the durable project handoff. Read it before exploring the repository.
Update it after material work so the next human or AI session starts from known
state instead of repeating discovery.

## Mission and current milestone

Build a trustworthy, portable WFM decision layer, beginning with an RTA product
and expanding only after the governed evidence and operational workflow work.

**Active milestone: Phase 1 — governed RTA vertical slice.** Phase 0.4 is
accepted. The exact hybrid release launched on the managed corporate
workstation and all five browser probes passed: stdlib/SQLite host, Worker
WebAssembly, DuckDB-Wasm/OPFS, Pyodide forecasting, and HiGHS-Wasm. The active
work is now source refresh -> canonical SQLite evidence -> service/attendance
-> staffing gap -> React command centre -> Excel export, followed by parity
with the useful workflows in WFMHub-Portable.

## Repository and branch state

| Ref | Purpose | State |
| --- | --- | --- |
| `origin/main` | Accepted hybrid foundation plus Phase 1 product design | CI, target browser, and target doctor passed; UI implementation awaits blueprint review |
| local `main` at `e943a05` | Pre-update governed contracts and storage work | Dirty/divergent user worktree; preserve and do not use for integration |
| `integration/stack-qualification` at `3927ecd` | Phase 0.2 diagnosis and improved launcher error | Run `35526214507` passed and commit was fast-forwarded to GitHub `main` |
| `integration/python313-policy-compat` | Phase 0.3 isolated 3.13.7 trial | Run `35526661488` passed; prerelease `v0.2.0-phase0.3` published |
| `integration/browser-wasm-hybrid-spike` (current) | Accepted Phase 0.4 foundation and proposed Phase 1 UI baseline | Target accepted; design documented before production UI work |
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
| D-016 | Test CPython 3.13.7 as a separate compatibility release; do not silently replace or call it a policy bypass. | The old portable proves this Python generation can launch on the target, but its pure-Python dependency surface does not prove the new native stack. |
| D-017 | Stop treating the complete native analytics graph as target-portable under the current company policy. | The exact Phase 0.3 doctor passed Python/SQLite/Excel but App Control blocked Pydantic Core, DuckDB, Polars/native loading, PyArrow, NumPy and every dependent forecasting/ML/optimization probe. More ZIP/CMD/version changes cannot authorize those binaries. |
| D-018 | Use a hybrid target profile: stdlib CPython + authoritative SQLite/Excel host, React UI, and optional browser-WASM workers. | It preserves the target-proven boundary while allowing analytical experiments without loading third-party host DLLs. |
| D-019 | OPFS/DuckDB-Wasm is a rebuildable analytical cache, never authoritative storage. | Browser storage can be cleared or evicted; source evidence and SQLite must survive browser/profile changes. |
| D-020 | Pin DuckDB-Wasm 1.32.0, Pyodide 0.29.5, and highs 1.15.3 for the Phase 0.4 gate. | These exact self-hosted builds passed local Worker/WASM/OPFS/model/solver operations; moving versions requires the same gates. |
| D-021 | HiGHS-Wasm and Pyodide models are candidates, not claimed drop-in replacements for OR-Tools/XGBoost/StatsForecast. | Scheduling formulations and forecast quality require independent WFM validation and performance evidence. |
| D-022 | Use stable loopback origin `127.0.0.1:8420` for the browser-WASM profile while retaining a fresh 256-bit token per launch. | OPFS is scoped to origin; an ephemeral port destroys cross-launch cache continuity. Startup fails if the fixed port is occupied. This supersedes D-008 for Phase 0.4 only. |
| D-023 | Accept the hybrid architecture as the target portable foundation and begin the governed RTA slice. | The exact Phase 0.4 release passed all five probes under the real corporate policy. This proves execution feasibility, not forecast quality, optimization semantics, production-data scale, or WFM product parity. |
| D-024 | Evolve the WFMHub-Portable navy/teal/gold visual system for WFMHub 2 instead of introducing an unrelated product theme. | The user requested continuity with the proven product; Phase 1 will improve readability and decision flow while preserving its operational identity. |

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
- The superseded Phase 0.1/0.2 browser architecture needed no WebView runtime.
  Compiled React assets and FastAPI shared one ephemeral `127.0.0.1` origin,
  with a fresh per-launch credential; the CMD console owned shutdown.
- GitHub Actions run `35507061319` passed the complete Linux job but stopped in
  Windows source tests before packaging. It exposed two Windows-specific bugs:
  Starlette hands a mounted static application backslash-normalized paths, so an
  unknown `/api/...` route incorrectly received the SPA fallback, and SQLite's
  context manager did not close the temporary backup connection, leaving the
  file locked during cleanup. API prefix normalization and explicit SQLite
  connection closing now have local regression coverage; the corrected Windows
  tests passed in the next pipeline.
- Run `35507326233` passed Linux plus every Windows source, DuckLake, and native
  analytical-stack gate, then failed the embedded builder's ZIP inventory
  assertion. The staged and archived inventories were independently sorted as
  Windows `Path` objects (case-insensitive) and ZIP strings (case-sensitive),
  so mixed-case dependency filenames produced a false list-order mismatch. The
  comparison now canonicalizes both sides as strings and reports any real
  missing, unexpected, or duplicate members; ZIP/runtime execution is pending.
- Run `35507582306` passed the complete Linux and Windows pipeline. The exact
  CI-produced ZIP was independently downloaded and its adjacent SHA-256
  verified: 300,607,038 bytes, 13,375 files, 852,233,445 extracted bytes, and
  SHA-256
  `dee1588bbe7d96fa401c473c4754a5835dd3d571b8629e92712a68f7b4543ad6`.
  From a space/non-ASCII path with outbound traffic blocked, all 14 isolated
  probes passed and the app served React, returned health, rejected an
  unauthenticated protected request with 401, completed authenticated storage
  and refresh operations, created Parquet, and shut down cleanly. The final run
  corrected timing scope and added memory evidence before release.
- Final qualification run `35508043118` passed again on commit `a347391`. It
  reproduced the same archive size and SHA-256 byte-for-byte. The measured
  second full doctor took 10.224 seconds, normal server readiness took 1.345
  seconds, and the two-process runtime used 102,010,880 working-set bytes and
  61,902,848 private-memory bytes after the authenticated API/storage smoke.
  GitHub's coarse extraction step took 19 seconds. These are hosted-runner
  baselines; target-PC antivirus and policy behavior remain a separate gate.
- Commit `25ec4b5` passed final tag-candidate run `35508340152`, was
  fast-forwarded to GitHub `main`, and was published as prerelease
  `v0.2.0-phase0.2`. Its release assets are the exact CI-produced portable ZIP
  and adjacent SHA-256; GitHub's automatic source archives remain unsupported.
- The exact `v0.2.0-phase0.2` ZIP failed on the target corporate workstation:
  `python.exe` returned decimal `1073751882` (`0x4000274A`) before emitting any
  supervisor/probe output. This is consistent with an enforced Device Guard /
  App Control block at process or initial-DLL load. The CodeIntegrity event
  3077/3089 blocked-file path is still required to distinguish `python.exe`,
  `python314.dll`, or another initial runtime file.
- The known-working old portable uses official CPython 3.13.7 plus only four
  pure-Python wheels; its runtime contains 30 reviewed CPython native images.
  The Phase 0.2 full stack adds hundreds of native dependency images. Therefore
  the old launcher's success proves the operating model, not approval of an
  arbitrary Python version or the complete new native dependency graph.
- All 75 distributions in the Phase 0.2 Windows production closure resolve to
  CPython 3.13-compatible Windows wheels at the pinned versions. The only
  irrelevant exception reported by the cross-platform audit is Linux-only
  `nvidia-nccl-cu13`. This makes a same-stack 3.13.7 package technically
  feasible; it does not make it corporate-policy compatible.
- The exact `v0.2.0-phase0.3` doctor ran to completion on the target corporate
  workstation. Four checks passed: portable paths, runtime isolation, SQLite,
  and the OpenPyXL/XlsxWriter Excel round-trip. Ten checks failed with explicit
  App Control DLL blocks: the FastAPI/Pydantic boundary (`_pydantic_core`),
  DuckDB/DuckLake (`_duckdb`), Polars/native loading, PyArrow, StatsForecast,
  MLForecast, HierarchicalForecast, Clarabel, XGBoost, and OR-Tools. Several
  downstream failures converge on blocked NumPy `_multiarray_umath`; `_ctypes`
  / its native dependency is another repeated boundary. This is policy
  enforcement, not a corrupt NumPy install.
- The old portable's viable boundary is independently reflected in this test:
  it uses CPython 3.13.7, `sqlite3`, `http.server`, OpenPyXL, XlsxWriter, and
  pure-Python application code. It does not import FastAPI/Pydantic, DuckDB,
  Polars, NumPy, PyArrow, XGBoost, or OR-Tools.
- The Phase 0.4 hybrid profile contains no third-party host-native images. Its
  only `.exe`, `.dll`, and `.pyd` files are the 30 files from the exact official
  CPython 3.13.7 embeddable archive; Excel dependencies remain four reviewed
  pure-Python wheel archives.
- A real headless Chromium run passed all five Phase 0.4 probes: stdlib host,
  Worker WebAssembly, DuckDB-Wasm 1.32.0 OPFS checkpoint/terminate/reopen,
  Pyodide 0.29.5 with NumPy/scikit-learn/statsmodels model fits, and highs
  1.15.3 integer optimization. DuckDB completed in 4.743 seconds, Pyodide in
  26.089 seconds, and HiGHS in 0.242 seconds on the local development machine.
- The same browser sequence passed from a fresh profile with external hostname
  resolution mapped away from the machine. All browser runtime assets and
  Pyodide wheels were served from the loopback origin.
- A second full host/browser launch reused the same browser profile and stable
  `127.0.0.1:8420` origin. The DuckDB OPFS counter advanced from 1 to 2,
  proving cross-launch persistence; OPFS remains only a rebuildable cache.
- The deterministic Phase 0.4 Windows compatibility ZIP has 84 files,
  73,143,871 bytes, and SHA-256
  `2f1bb4349fcf8f857e28247efd563e18e0805069a823347df08cc5433a1ad765`.
  Its extracted stage is about 146 MiB. Ordinary Windows CI has passed the
  profile; target corporate-policy execution remains pending.
- GitHub Actions run `35536020333` passed the Linux job and the complete new
  Windows hybrid job: exact ZIP assembly/extraction, embedded host doctor, and
  all five Edge probes with outbound DNS blocked. The separate legacy native
  Windows job exposed Windows `SO_REUSEADDR` allowing a live same-port bind;
  the hybrid server now uses `SO_EXCLUSIVEADDRUSE` on Windows and
  `SO_REUSEADDR` elsewhere, with collision/restart regression coverage.
- Corrected GitHub Actions run `35536284746` passed all three jobs, including
  the exact Windows hybrid host/browser smoke and the complete legacy native
  regression suite. Its hybrid artifact was independently downloaded and its
  adjacent checksum verified. The builder now normalizes CMD files to CRLF so
  every platform stages identical member contents. The Windows CI ZIP is the
  canonical release container because DEFLATE output can vary by zlib build.
- Final run `35536783063` also passed all three jobs after launcher
  normalization. Its exact hybrid ZIP and adjacent checksum independently
  verify 73,143,871 bytes and SHA-256
  `2f1bb4349fcf8f857e28247efd563e18e0805069a823347df08cc5433a1ad765`.
- The managed target workstation returned a valid Phase 0.4 report with all
  five exact probes passing under Edge 153. The host responded in 21 ms,
  Worker WebAssembly in 39 ms, DuckDB-Wasm OPFS checkpoint/reopen in 2.251 s,
  Pyodide scikit-learn/statsmodels model fitting in 11.350 s, and HiGHS-Wasm
  integer optimization in 128 ms. `crossOriginIsolated` and `secureContext`
  were both true. This closes the corporate browser-policy compatibility gate.
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
| Official embedded CPython provenance | PASS | Hash-pinned 3.14.7 archive, origin/native manifests, isolated `_pth`, exact-ZIP runtime probe |
| Complete dependency payload | PASS | 75-distribution frozen closure installed at build time; exact ZIP passed all capability probes |
| Python/frontend quality | PASS | Local Python 3.14.7: Ruff format/lint, strict Pyright, 21 pytest; frontend: Biome, TypeScript, 6 Vitest, production build |
| Full subprocess doctor | PASS | Exact extracted ZIP passed all 14 isolated core/heavy probes in run `35507582306` |
| Offline DuckLake | PASS | Bundled extension explicitly loaded with auto-install/autoload disabled; physical Parquet write/reopen passed |
| Browser/API security | PASS | Ephemeral loopback, per-launch token, 401/authenticated HTTP, host/origin tests, same-origin React passed |
| Exact ZIP verification | PASS | 13,375 members/hash-verified; no user data or custom application executable; adjacent SHA-256 independently passed |
| Windows offline/lifecycle | PASS | Outbound-blocked exact ZIP served React/API, persisted storage, and shut down cleanly in run `35507582306` |
| Corporate App Control | FAIL | Exact Phase 0.2 ZIP exited `1073751882` / `0x4000274A` before supervisor output; collect CodeIntegrity 3077/3089 blocked path |
| Operational budget | PASS | 300,607,038-byte ZIP; 852,233,445 bytes/13,375 files extracted; 10.224 s doctor; 1.345 s readiness; 102,010,880-byte working set |

Phase 0.2 is complete only when all gates pass. A gate may be deliberately removed
only through a recorded decision with evidence.

## Phase 0.3 compatibility gates

| Gate | Status | Required evidence |
| --- | --- | --- |
| Frozen CPython 3.13 graph | PASS | Regenerated `uv.lock`; frozen Linux and Windows installs under exactly 3.13.7 in run `35526661488` |
| Official 3.13.7 provenance | PASS | Official archive SHA-256 `f6cca216a359be84797cabb54149ce5e062afb16cc7567eb7fc51cacb2d86b65`; exact native manifest and old-portable `python.exe` hash match |
| Source and frontend quality | PASS | Local CPython 3.13.7: Ruff, strict Pyright, 22 pytest, native-stack probe; frontend: Biome, TypeScript, 6 Vitest, production build |
| Ordinary-Windows exact ZIP | PASS | All 14 doctor probes plus outbound-blocked API/storage/browser lifecycle passed in run `35526661488` |
| Target CPython startup | PASS | Exact Phase 0.3 `DOCTOR.cmd` completed under embedded CPython 3.13.7 |
| Target native capabilities | FAIL | 10 of 14 probes were explicitly stopped by App Control while Python/SQLite/Excel passed |

## Phase 0.4 compatibility gates

| Gate | Status | Evidence |
| --- | --- | --- |
| Exact release and ordinary Windows | PASS | Run `35536783063`; exact embedded host doctor and outbound-blocked five-probe Edge smoke |
| Target stdlib/SQLite host | PASS | Managed-workstation `host_sqlite` probe passed in 21 ms with zero third-party host-native files |
| Target Worker WebAssembly | PASS | Managed-workstation Worker probe returned the expected result in 39 ms |
| Target DuckDB-Wasm/OPFS | PASS | 1.32.0 exception-handling bundle checkpointed, terminated, reopened, and read successfully in 2.251 s |
| Target Pyodide forecasting | PASS | The pinned Pyodide payload returned Python 3.13.2, NumPy 2.2.5, scikit-learn 1.7.0, and statsmodels 0.14.4; both models fit in 11.350 s |
| Target HiGHS-Wasm MIP | PASS | Integer staffing model returned the expected optimal solution/objective in 128 ms |
| Browser security prerequisites | PASS | Edge 153 reported secure context and cross-origin isolation |

## Current risks and fallbacks

- Phase 0.4 proves runtime compatibility, not that the RTA product is built or
  that it is better than WFMHub-Portable in daily use. Product parity remains
  a hard delivery gate.
- OPFS is origin/profile-private and can be cleared or evicted. DuckDB-Wasm is
  only a rebuildable cache; SQLite and source evidence remain authoritative.
- The target probe was fast enough for the spike, but memory use and behavior
  at real WFM data volumes remain unmeasured.
- The user separately confirmed that the exact target doctor passed. The
  browser report still does not cryptographically bind itself to the release
  ZIP or embed the doctor result; a future report schema should include build
  identity and host-doctor status in one artifact.
- The target reported `online: true`; no-network execution is independently
  proven by CI, not by this target run.
- Pyodide/scikit-learn/statsmodels prove model execution, not forecast quality.
  HiGHS proves MIP execution, not that an OR-Tools scheduling formulation can
  be translated with acceptable performance or semantics.
- The blocked full native graph still requires an IT-authored allow policy,
  trusted signing/catalog rules, or managed deployment. It is now a separate
  trusted/server profile, not the target portable fallback.
- Company policy or Edge versions can change. Retain the compatibility report
  and rerun the five probes for future runtime upgrades.

## Next executable steps

1. Review the proposed Phase 1 shell, information architecture, and three
   screen concepts in `docs/UI_BLUEPRINT.md`; then implement the shared design
   tokens, application shell, typed synthetic contracts, and Command Center.
2. Inventory and selectively port the old product's governed source contracts,
   mappings, formulas, SQLite migrations, upgrades, and synthetic tests; never
   copy operational/user data.
3. Deliver the first governed RTA vertical slice: read-only local source
   refresh -> canonical SQLite facts -> service/attendance -> staffing gap ->
   React command centre -> Excel export.
4. Keep DuckDB-Wasm, Pyodide, and HiGHS optional until each materially improves
   a measured RTA workflow; deterministic host logic remains the fallback.
5. Reach old-portable business parity before declaring WFMHub 2 the operational
   replacement; qualify forecasting and optimization separately afterward.

## Session log

### 2026-09-21 — Target doctor confirmed and Phase 1 UI baseline drafted

- The user confirmed that the exact target doctor passed in addition to the
  previously accepted five-probe browser report. This closes the remaining
  target host-compatibility observation; future reports should bind doctor,
  browser results, and build identity in one artifact.
- Audited the WFMHub-Portable product contract, design tokens, web shell,
  navigation, filters, operational tables, timelines, and evidence patterns.
- Drafted `docs/UI_BLUEPRINT.md`: a desktop-first Phase 1 shell organised as
  Command, Operate, Decide, Review, and Govern, with Plan hidden until it has a
  working product.
- Generated and inspected three synthetic 1586 x 992 design references for the
  RTA Command Center, Attendance & Coverage, and Risk & Decision Workspace.
  They preserve the old navy/teal/gold theme while improving readability and
  making the decision/outcome loop first class.
- A contract-focused review caught and corrected synthetic portfolio service
  aggregation, staffing arithmetic, missing-evidence classifications, active-
  shift early-leave language, and unvalidated service-impact claims before the
  images were accepted as references.
- No production UI or business formula changed. The next implementation step
  starts only after the proposed hierarchy is reviewed.

### 2026-09-20 — Phase 0.4 hybrid browser-WASM spike implemented locally

- Created `integration/browser-wasm-hybrid-spike` from the Phase 0.3 target
  acceptance baseline.
- Added a standalone `wfmhub2_compat` host that imports only the standard
  library, binds the stable loopback origin `127.0.0.1:8420`, validates
  Host/token boundaries, launches Edge explicitly on Windows, serves
  cross-origin-isolated static assets, initializes authoritative SQLite, and
  atomically records strictly validated five-probe browser reports.
- Added independently reported Worker probes for base WebAssembly,
  DuckDB-Wasm/OPFS persistence, Pyodide forecasting, and HiGHS-Wasm MIP.
- Added verified offline Pyodide staging, pure-Python Excel wheel packaging,
  native-file rejection, deterministic archive verification, and an explicit
  compatibility UI that does not claim to be the finished product.
- Independent final review found and drove fixes for browser readiness racing,
  stale nested asset staging, default-browser ambiguity, weak report
  validation, ephemeral-origin OPFS loss, and immediate fixed-port restart.
- GitHub run `35536020333` proved the exact Windows hybrid artifact and all five
  offline Edge capabilities. Its legacy native job then caught Windows' live
  port-reuse semantics; the host now requests exclusive address ownership on
  Windows while retaining immediate-restart behavior.
- Corrected run `35536284746` passed all Linux, hybrid Windows, and legacy
  native Windows gates. The exact CI hybrid ZIP/checksum was downloaded and
  verified before release preparation.
- Final run `35536783063` passed the same complete matrix after cross-platform
  launcher normalization; its canonical Windows artifact is the Phase 0.4
  release payload.
- Local result: 29 pytest, strict Pyright, Ruff, TypeScript, 8 Vitest, Biome,
  production build, two real-browser offline smokes, cross-launch OPFS
  persistence, deterministic member assembly, and ordinary-Windows execution
  all passed. At that checkpoint, only the managed target-policy run remained;
  the next entry records its successful result.

### 2026-09-20 — Phase 0.4 accepted on the managed workstation

- Received a schema-valid report from the exact Phase 0.4 profile on managed
  Windows / Edge 153 with `overallStatus: pass` and every expected probe present
  exactly once.
- The target permits cross-origin-isolated Worker WebAssembly, DuckDB-Wasm
  OPFS checkpoint/reopen, Pyodide scientific models, and HiGHS-Wasm integer
  optimization. The full sequence completed in about 13.8 seconds.
- Phase 0.4 is accepted and Phase 1 begins. No claim is made yet about forecast
  accuracy, production-scale performance, scheduling equivalence, or finished
  WFM usefulness.

### 2026-09-20 — Target Phase 0.3 native-policy boundary proven

- The exact prerelease doctor completed on the corporate workstation under
  embedded CPython 3.13.7. Portable paths, runtime isolation, SQLite, and Excel
  passed, proving the CMD/embedded-Python operating model and the useful local
  core boundary.
- App Control explicitly blocked `_pydantic_core`, `_duckdb`, PyArrow native
  loading, NumPy `_multiarray_umath`, and repeated `_ctypes`-dependent paths.
  Consequently FastAPI plus every DuckDB/Polars/forecasting/ML/optimization
  capability failed. This is not a package corruption or version mismatch.
- Superseded the assumption that the complete native stack can be made target-
  portable through a different shell or CPython version. Further work now
  requires either IT-managed authorization or a pure-Python/SQLite portable
  profile; implementation awaits that scope decision.

### 2026-09-20 — CPython 3.13 policy-compatibility trial started

- Created `integration/python313-policy-compat` from the Phase 0.2 diagnostic
  commit. The experiment preserves the full production dependency graph,
  embedded-runtime isolation, doctor, security boundary, storage model, and
  browser lifecycle; only the Python compatibility line changes.
- Pinned the official CPython 3.13.7 embeddable archive to the exact hash used
  by the old portable, changed build/smoke paths from `python314` to
  `python313`, and regenerated the Python lock for `==3.13.*`.
- Local CPython 3.13.7 now passes Ruff formatting/lint, strict Pyright, all 22
  pytest tests, and real DuckDB/Polars/forecast/XGBoost/OR-Tools/Excel native
  operations. The frontend passes Biome, TypeScript, all 6 Vitest tests, and
  its production build.
- Run `35526661488` passed the complete Linux and Windows pipeline. The exact
  Windows ZIP passed all 14 isolated probes plus the outbound-blocked
  browser/API/SQLite/DuckLake lifecycle and clean shutdown. It is 299,178,314
  bytes, has 13,372 members / 847,656,982 expanded bytes, and SHA-256
  `2aea1d3f08d053ad8ac0741bcd132d09238c540a472fd80480b50e3da7a6a6cb`.
  Embedded `python.exe` has the same
  `d932e5e2f324d57f392e8fd063dcf6d0185be8a664c57c6d24e7762ed02c28ca`
  hash as the known-working old portable.
- Published the exact CI artifact and checksum as prerelease
  `v0.2.0-phase0.3`. This is still a diagnostic compatibility trial: the
  target corporate doctor remains the decisive gate.

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
- Corrected run `35507326233` passed those Windows tests and the installed
  DuckLake/native stack, but the builder rejected identical ZIP and staged
  inventories because Windows `Path` ordering is case-insensitive while ZIP
  string ordering is case-sensitive. Canonical string ordering and actionable
  inventory diagnostics replace that false comparison; another exact package
  run is pending.
- Run `35507582306` passed every gate and produced an independently checksum-
  verified 300,607,038-byte ZIP with 13,375 files and 852,233,445 extracted
  bytes. Every isolated capability and the outbound-blocked browser/API/storage
  lifecycle passed. Before release, the smoke evidence is being tightened
  because its prior readiness timer included doctor/API work and it omitted
  normal-process memory; this does not invalidate runtime behavior but does
  leave the operational-budget evidence incomplete.
- Final run `35508043118` passed the corrected evidence collection and
  reproduced the archive byte-for-byte. The second full doctor was 10.224
  seconds, true process-to-ready time was 1.345 seconds, and the steady
  two-process runtime measured 102,010,880 working-set bytes / 61,902,848
  private bytes after the authenticated API/storage smoke. The hosted runner's
  archive expansion step was 19 seconds. The operational-budget gate now
  passes; only execution under the target company's policy remains blocked.
- Final tag-candidate run `35508340152` passed Linux and the complete Windows
  build/extract/doctor/offline-lifecycle pipeline on commit `25ec4b5`. GitHub
  `main` was fast-forwarded without touching the preserved dirty local `main`,
  and prerelease `v0.2.0-phase0.2` was published with the exact verified ZIP
  plus checksum. The next evidence must come from `DOCTOR.cmd` on the managed
  workstation.
- The target `DOCTOR.cmd` attempt returned `1073751882` (`0x4000274A`) before
  emitting any probe result, so the corporate gate is now `FAIL`, not pending.
  The code is consistent with Device Guard/App Control terminating the initial
  Python image load. Added a targeted launcher explanation pointing to
  CodeIntegrity enforcement event 3077 and signature event 3089. Comparison to
  the still-working old portable shows its approved surface is CPython 3.13.7
  plus pure-Python wheels; a 3.13.7 current-stack experiment is conditional on
  the blocked filename and cannot prove the hundreds of new native libraries.

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
