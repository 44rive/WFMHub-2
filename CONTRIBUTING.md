# Contributing

WFMHub 2.0 is organized around workforce-management domains and a strict separation between source adapters, business logic, intelligence, storage, transport, and presentation.

## Development prerequisites

- Python 3.14.7;
- uv;
- Node compatible with the selected Vite/Tauri toolchain;
- pnpm 12;
- Rust stable for desktop/Tauri development.

## Python setup

```powershell
uv sync --frozen --extra dev --python 3.14.7
uv run --frozen ruff format --check src tests scripts
uv run --frozen ruff check src tests scripts
uv run --frozen pyright
uv run --frozen pytest
uv run --frozen python scripts/probe_native_stack.py
```

## Frontend setup

```powershell
corepack enable
pnpm install --frozen-lockfile
pnpm check:web
pnpm typecheck:web
pnpm test:web
pnpm build:web
```

## Desktop development

The packaged Python sidecar must exist under `src-tauri/binaries/` with the host target-triple suffix before a release build. See `scripts/build_portable.ps1`.

```powershell
pnpm desktop:dev
```

Rust source checks use the committed Cargo lock:

```powershell
$env:TAURI_CONFIG = '{"bundle":{"externalBin":[],"resources":[]}}'
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo clippy --manifest-path src-tauri/Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml --locked
Remove-Item Env:TAURI_CONFIG
```

The test-only Tauri override avoids requiring release-staged native artifacts
for source checks. `scripts/build_portable.ps1` uses the normal configuration
and validates the real sidecar and DuckLake resource.

## Windows stack qualification

On a networked Windows x64 build machine, the portable build command uses all
three committed locks, stages the reviewed DuckLake 1.5.5 artifact, verifies a
local load/write/restart/read, exercises the heavy native dependencies, builds
the PyInstaller sidecar, and builds the Tauri bundle:

```powershell
./scripts/build_portable.ps1
```

To retest an already staged extension without downloading it again:

```powershell
./scripts/build_portable.ps1 -UseStagedDuckLake
```

The build also creates and verifies
`dist/WFMHub-2-v<version>-windows-x64-portable.zip` and its adjacent `.sha256`;
archive/member evidence is written to
`qualification-evidence/portable-archive.json`. The generated ZIP, extension
binary, sidecar, bundles, runtime data, and evidence are build artifacts and
must not be committed.

## Updating dependencies

Normal build and test commands are frozen. A deliberate dependency update must
regenerate and review all affected locks:

```powershell
uv lock --python 3.14.7
pnpm install --lockfile-only --force
cargo generate-lockfile --manifest-path src-tauri/Cargo.toml
```

Do not merge a core runtime/data dependency change until the Windows stack
qualification workflow passes and its package/startup evidence has been
reviewed.

## Where code belongs

- Vendor parsing/mapping: `src/wfmhub2/adapters/`
- Service calculations: `src/wfmhub2/domain/service/`
- Staffing calculations: `src/wfmhub2/domain/staffing/`
- Forecast logic: `src/wfmhub2/domain/forecasting/`
- Attendance logic: `src/wfmhub2/domain/attendance/`
- Schedule logic: `src/wfmhub2/domain/scheduling/`
- Capacity logic: `src/wfmhub2/domain/capacity/`
- Risk/recommendations/scenarios: `src/wfmhub2/intelligence/`
- Solver models: `src/wfmhub2/optimization/`
- SQLite/DuckLake implementation: `src/wfmhub2/storage/`
- HTTP transport: `src/wfmhub2/api/`
- Desktop shell only: `src-tauri/`
- Presentation only: `web/`

Do not put business formulas into FastAPI routes, React components, Tauri/Rust code, or vendor adapters.

## Data policy

Do not commit operational workforce extracts or real employee/customer identifiers. Tests and benchmarks must use synthetic fixtures designed to exercise edge cases.

## Testing expectations

- Domain rule change -> unit/property tests.
- Adapter change -> synthetic parser fixtures.
- Refresh/storage change -> integration tests.
- Forecast change -> backtest/metric tests.
- Optimization change -> feasibility/invariant tests.
- Frontend change -> typecheck/build and relevant component/E2E tests.

## Dependency policy

Use current stable releases unless a preview is intentionally being evaluated behind a branch/feature flag. Do not upgrade core data/runtime dependencies without running portable Windows smoke tests.

## Design principle

Prefer code that makes the WFM rule obvious. Performance matters, but business correctness and traceability come first; optimize measured bottlenecks rather than hiding formulas behind clever infrastructure.
