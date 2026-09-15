# Portable Windows Deployment

Portable deployment is a product requirement, not a temporary development shortcut.

## Target experience

A user should be able to unzip WFMHub to a writable local folder and launch it without administrator rights or machine-wide installation.

The target machine should not require:

- Python;
- Node.js;
- SQLite tooling;
- DuckDB tooling;
- OR-Tools installation;
- a database service;
- internet access.

## Release shape

```text
WFMHub-2/
├─ WFMHub.cmd
├─ Feed/
├─ Reports/
└─ _system/
   ├─ python/                embedded CPython
   ├─ site-packages/         offline-installed runtime wheels
   ├─ app/                   wfmhub2 Python package
   ├─ web/                   production React/Vite build
   ├─ config/                shipped defaults/templates
   └─ runtime-requirements.lock
```

Runtime data can live outside `_system` so program upgrades do not replace local history/configuration.

## Startup

The launcher should:

1. resolve its own directory;
2. isolate the bundled Python from machine Python environment variables;
3. initialize/upgrade local storage safely;
4. start the loopback API server;
5. open the local UI;
6. keep logs under the local application folder.

## Frontend packaging

React/TypeScript is compiled during CI/release:

```text
web/src -> npm build -> static HTML/CSS/JS assets
```

Only the static output ships in the portable runtime.

## Native wheels

DuckDB, Polars and OR-Tools include native code. The portable build must therefore download and verify the exact Windows x64 wheels during release preparation and install them into the bundled runtime offline.

The release process should use a locked dependency manifest with hashes and reject unpinned/unverified artifacts.

## Data location

Recommended user-visible layout:

```text
Feed/        source extracts
Reports/     generated workbooks/exports
config/      user-owned configuration
_system/     program/runtime files
```

Databases and Parquet history can live under a dedicated local data directory that the upgrade process preserves.

## Concurrency

Portable mode should have one application owner process. The UI, refresh orchestration and analytical queries should communicate through that process rather than letting unrelated processes compete for database ownership.

## Upgrade principle

A release replaces program files, not user data. Storage migrations should be explicit, versioned, tested and reversible through backups where practical.
