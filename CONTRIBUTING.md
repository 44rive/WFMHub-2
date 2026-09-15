# Contributing

WFMHub 2.0 is organized around workforce-management domains and strict separation between vendor adapters and business logic.

## Development setup

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ruff check src tests
pytest
```

Frontend:

```powershell
cd web
npm install
npm run build
```

## Where code belongs

- Vendor parsing/mapping: `src/wfmhub2/adapters/`
- Service calculations: `src/wfmhub2/domain/service/`
- Staffing calculations: `src/wfmhub2/domain/staffing/`
- Forecast logic: `src/wfmhub2/domain/forecasting/`
- Attendance logic: `src/wfmhub2/domain/attendance/`
- Schedule logic: `src/wfmhub2/domain/scheduling/`
- Risk/recommendations/scenarios: `src/wfmhub2/intelligence/`
- Solver models: `src/wfmhub2/optimization/`
- Storage implementation: `src/wfmhub2/storage/`
- HTTP routes/models: `src/wfmhub2/api/`

Avoid putting business formulas into API routes, frontend code or vendor adapters.

## Data policy

Do not commit operational workforce extracts, employee identifiers or other real production data. Tests should use synthetic fixtures designed to exercise edge cases.

## Testing expectations

A domain-rule change should include unit tests. Adapter changes should include synthetic parser fixtures. Refresh/storage changes should include integration tests. Frontend changes must continue to type-check/build.

## Design principle

Prefer code that makes the WFM rule obvious. Performance matters, but business correctness and traceability come first; optimize measured bottlenecks rather than obscuring formulas prematurely.
