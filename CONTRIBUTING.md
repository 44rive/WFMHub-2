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
uv sync --extra dev
uv run ruff check src tests
uv run pyright
uv run pytest
```

## Frontend setup

```powershell
corepack enable
pnpm install
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
