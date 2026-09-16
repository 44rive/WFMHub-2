# Portable Windows Deployment

## Goal

The end-user experience should remain:

```text
unzip -> run WFMHub.exe -> work
```

Normal use should require no administrator rights, installed Python, Node.js, Rust, database server, or internet access.

## Release layout

Conceptual Windows x64 release:

```text
WFMHub-2/
├─ WFMHub.exe
├─ wfmhub-engine.exe
├─ Feed/
├─ Reports/
├─ data/
│  ├─ control.sqlite
│  └─ lake/
│     ├─ catalog.ducklake
│     └─ files/
└─ _system/
   └─ duckdb_extensions/
      └─ ducklake.duckdb_extension
```

Exact Tauri sidecar file names inside the bundle include the target triple during build.

## Build-time vs runtime dependencies

### Build machine

Requires:

- Python 3.14 / uv;
- Node + pnpm;
- Rust toolchain;
- Tauri prerequisites;
- PyInstaller;
- access to dependency registries for a reproducible release build.

### End-user workstation

Requires only the produced application directory/bundle plus a supported Windows WebView2 runtime. Tauri can be configured with an appropriate WebView2 installation strategy for environments where the evergreen runtime cannot be assumed.

## Python sidecar

PyInstaller produces `wfmhub-engine.exe` containing the Python runtime and application dependencies.

Tauri packages it as an `externalBin` sidecar and starts it on application launch.

The engine binds to `127.0.0.1` only.

## DuckLake extension

DuckLake is a DuckDB extension. Development environments may install it from DuckDB's extension repository, but a portable release must package the matching extension artifact locally.

The engine supports an explicit local extension path via settings/environment and should `LOAD` that file instead of downloading at runtime.

Release CI must verify the extension matches the bundled DuckDB version/platform.

## Frontend

React/Vite output is static build content packaged inside the Tauri application. Node/pnpm do not ship to the user.

## Data location

Portable mode defaults data paths relative to the executable/application home so the folder can be moved as one unit.

WFMHub should detect/warn about unsupported writable locations such as read-only folders. A future installed edition may optionally use a per-user application-data directory.

## Offline smoke test

Release CI should validate on a clean Windows runner:

1. build Python sidecar;
2. bundle DuckLake extension;
3. build React/Tauri application;
4. disable/avoid runtime network dependency;
5. start application/engine;
6. call `/api/health`;
7. initialize SQLite and DuckLake;
8. run a synthetic refresh fixture;
9. run a representative DuckDB query;
10. verify generated Excel handoff;
11. verify shutdown cleans up the sidecar.

## Package size

WFMHub 2.0 will be materially larger than the original portable tool because OR-Tools, XGBoost, forecasting libraries and the Python runtime contain native binaries. That is an acceptable tradeoff if the product remains simple to deploy and operate.

Package size is a secondary metric; startup, refresh speed, reliability and zero-install operation are primary.

## Offline DuckLake extension contract

Release builds bundle the platform-matched DuckLake extension as a Tauri resource at
`duckdb_extensions/ducklake.duckdb_extension`. The Rust shell resolves that resource
path and passes it to the Python sidecar with `--ducklake-extension`, so production
runtime never depends on DuckDB downloading an extension from the internet.

The desktop shell also passes an explicit `--home` path. In the portable edition this
is the directory containing `WFMHub.exe`, keeping `data/`, `Feed/`, and `Reports/`
co-located with the extracted application. An installed/team edition may choose an OS
application-data directory later without changing WFM domain logic.
