# Repository instructions

Before starting work, read `PROJECT_LEDGER.md`, `PROJECT_VISION.md`,
`ARCHITECTURE.md`, and the task-relevant document under `docs/`.

## Project ledger

`PROJECT_LEDGER.md` is the durable handoff for humans and AI agents. Update it
in the same commit whenever work changes a decision, milestone status,
validation result, blocker, branch/commit reference, or next executable step.
Keep entries concise and never place credentials, tokens, employee data, or
operational extracts in the ledger.

Do not rediscover settled decisions unless new evidence invalidates them. When
that happens, record the new evidence and supersede the old decision explicitly.

## Non-negotiable engineering behavior

- Preserve source extracts; ingestion is read-only.
- Unknown evidence stays unknown.
- Keep demand/service, forecast/requirement, schedule, and
  attendance/actual-state facts at their natural grains.
- Keep business formulas out of adapters, API routes, Tauri, and React.
- Keep runtime state outside replaceable program files.
- A failed refresh must leave the previous validated analytical state active.
- The portable release must run without installed Python, Node, Rust, a database
  server, administrator rights, or runtime internet access.
- Never commit real employee, customer, schedule, call, database, report, log,
  Parquet, or operational extract data.

## Definition of done

Use the checks declared in `CONTRIBUTING.md` plus the active milestone gates in
`PROJECT_LEDGER.md`. A scaffold, successful dependency resolution, or passing
unit test alone is not evidence that the portable desktop product launches.
