# Portable Windows Deployment

## Goal

The supported single-user experience is:

```text
download release ZIP -> Extract All -> run WFMHub.cmd -> work locally
```

Normal use requires no administrator rights, installed Python, Node.js, Rust,
database server, installer, or internet access. WFMHub reads the configured
local source folders directly; there is no upload workflow.

## Why the runtime changed

The Phase 0.1 Tauri + PyInstaller bundle ran correctly in Windows CI but its two
unsigned custom executables were rejected by application-control policy on the
target corporate workstation. The earlier WFMHub-Portable product already
proved a compatible model on that workstation: a CMD launcher invokes the
official CPython embeddable runtime and runs application-local Python code.

WFMHub 2 therefore retains the complete Python/data/forecasting/optimization
stack while replacing only its delivery shell. It no longer requires a Tauri
launcher, PyInstaller sidecar, WebView2 window, installer, or one-file
extraction under `%TEMP%`.

## Release layout

```text
WFMHub-2/
├─ WFMHub.cmd
├─ DOCTOR.cmd
├─ README-FIRST.txt
├─ SHA256SUMS.txt
├─ config/
├─ Feed/
├─ Reports/
└─ _system/
   ├─ runtime/                 official CPython + signed MS runtime DLLs
   ├─ site-packages/           frozen Windows x64 production graph
   ├─ app/wfmhub2/             application code
   ├─ web/                     compiled React assets
   └─ duckdb_extensions/
      └─ ducklake.duckdb_extension
```

`data/control.sqlite`, the DuckLake catalog, and managed Parquet files are
created locally on first use; they are never release payloads. The database,
lake, configuration, feeds, and reports remain local. Program upgrades replace
`_system` and launchers, never durable user state.

## Embedded CPython contract

Release CI downloads the official
`python-3.14.7-embed-amd64.zip` and verifies SHA-256:

```text
d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15
```

The build records its origin and an exact native-file manifest. The runtime
`python314._pth` exposes only the standard library, application package and
application-local `site-packages`. Launchers clear machine Python environment
variables and use isolated mode.

Third-party packages are resolved from the committed lock during the networked
build and installed into the staged runtime. The target workstation never runs
pip. Native wheel contents remain ordinary `.pyd`/`.dll` files in their wheel
layout rather than being embedded in or extracted from a custom executable.
The Microsoft-signed `msvcp140.dll` and `vcomp140.dll` copies from the locked
scikit-learn wheel are signature-checked and placed beside `python.exe` so the
release does not rely on a machine-wide redistributable installation.

## Application launch

`WFMHub.cmd`:

1. resolves the extracted application directory;
2. verifies that `_system/runtime/python.exe` exists;
3. clears `PYTHONHOME` and `PYTHONPATH`;
4. invokes the embedded runtime in isolated mode with explicit home and local
   DuckLake-extension paths;
5. generates a per-launch session token;
6. starts FastAPI/Uvicorn on an available `127.0.0.1` port;
7. serves the compiled React client on the same origin;
8. opens the system browser;
9. remains the visible lifecycle owner until Ctrl+C/window close.

The browser is presentation and job control. Python remains the only owner of
source reads, calculations and analytical writes.

## Full-stack compatibility doctor

`DOCTOR.cmd` starts through a standard-library-only supervisor. It executes
every capability in a fresh child of the same embedded `python.exe`, so one
blocked or crashing native library becomes a named failure and does not hide
the remaining results. It performs real, local operations with:

- isolated runtime paths and cleared machine-Python environment;
- portable paths and SQLite WAL/rollback/backup/quick-check/reopen;
- DuckDB, the explicit offline DuckLake extension and managed Parquet;
- Polars parsing/group transforms;
- PyArrow Zstd-Parquet write/read required by the StatsForecast dependency graph;
- StatsForecast prediction, MLForecast fit/predict and HierarchicalForecast
  bottom-up reconciliation;
- qpsolvers/Clarabel quadratic programming used by the forecast stack;
- XGBoost;
- OR-Tools CP-SAT;
- XlsxWriter/OpenPyXL round-trip;
- the FastAPI/Pydantic application boundary.

All capabilities ship together, but heavy modules are imported only by their
feature or by this explicit doctor. A normal RTA launch must not eagerly load
forecasting, ML, or optimization libraries.

The target corporate workstation is the final application-control gate. If its
policy blocks a bundled `.pyd` or `.dll`, no launcher or archive layout may
circumvent that policy; that binary must be approved or the dependency must be
replaced. The doctor and Windows Code Integrity/AppLocker event logs identify
the exact failing file.

The current locked graph is intentionally complete rather than minimal: about
75 runtime distributions, roughly 795 MiB of extracted dependencies and 13,000
files before the runtime/app/extension. Most third-party PE files are unsigned,
so neither ZIP creation nor GitHub-hosted Windows CI can prove company-policy
acceptance. Normal startup remains lazy; only `DOCTOR.cmd` loads every heavy
capability.

## DuckLake extension

The release contains the reviewed DuckDB/DuckLake `1.5.5` Windows AMD64
extension. Build staging verifies:

```text
compressed:   4a5180e1654cbbc3fd58afe8c70b3f98187d18e8d8e8c9bf386c3d48e9b8a116
decompressed: 4546a5c6d9bc52cc122bc76e521c996e1ac31e71a25e01c531db8d3bb65e2ef0
```

Production always loads the explicit packaged file. It never installs or
downloads an extension at runtime.

## Release qualification

Windows CI must:

1. complete frozen Python and frontend source checks;
2. stage and verify the pinned DuckLake extension;
3. build the React client;
4. assemble the official embedded runtime and complete locked production
   dependency graph;
5. reject missing/unexpected release members and user data;
6. expand the exact final ZIP to a clean directory;
7. launch only its embedded `python.exe`, never the runner's Python;
8. run the full offline doctor with outbound traffic blocked;
9. start the localhost application, verify authenticated API/storage activity,
   and stop it cleanly;
10. publish archive/member hashes and qualification evidence.

GitHub-hosted Windows proves package completeness and offline operation. It
does not replace the final run on the separately managed corporate workstation.

## Build command

From a networked Windows x64 checkout:

```powershell
uv sync --frozen --extra dev --python 3.14.7
corepack pnpm install --frozen-lockfile
./scripts/build_portable.ps1
```

The output is a versioned release ZIP plus its adjacent SHA-256 file. GitHub's
automatic source archive is not runnable and is never an end-user artifact.
