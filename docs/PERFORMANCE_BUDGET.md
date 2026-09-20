# Performance Budget

WFMHub should feel like an operational desktop tool, not a batch data warehouse.

## User-facing targets

Initial engineering targets, subject to benchmark refinement:

- application shell visible quickly after launch;
- common warm API/dashboard queries generally < 500 ms;
- interval drill-down queries generally < 1 s;
- normal daily incremental refresh: seconds to tens of seconds at typical desktop WFM scale;
- one-day correction: proportional to that date/service slice, not total history;
- first-time multi-month bootstrap measured separately from daily refresh;
- UI remains responsive while refresh/optimization work runs in the engine.

These are product budgets, not promises independent of source-file size and hardware.

## Retired Phase 0.1 desktop baseline

The 2026-09-19 Linux qualification run recorded:

- Python sidecar: 303,345,488 bytes;
- uncompressed Tauri shell + sidecar + DuckLake: about 355.1 MB;
- cold desktop-to-engine readiness: about 10.25 seconds;
- total idle RSS across the desktop/WebKit/engine tree: about 527 MiB;
- packaged full native-stack doctor: 11.34 seconds, about 385 MiB peak RSS;
- explicit local DuckLake load: 38.1 ms median across five warm-host runs.

These values are historical evidence for the retired executable delivery path;
they are not the baseline for the embedded-CPython release.

## Phase 0.2 embedded-runtime budget

The locked Windows graph is expected to be roughly 795 MiB and 13,000 files
before CPython, application code, web assets, and DuckLake. CI must record:

- exact ZIP and extracted bytes;
- extracted file/native-image counts;
- full subprocess-doctor duration;
- normal cold readiness and idle memory;
- extraction/antivirus-sensitive first-use time.

No target is marked `PASS` until the exact ZIP is measured on Windows. Heavy
forecasting/optimization imports stay out of normal startup even though every
capability ships in the same release.

## Benchmark scales

Synthetic fixtures should cover at least:

```text
small     30 days / low-volume operation
medium    6 months / realistic multi-service history
large     12–24 months / high-volume call and agent-status history
```

## Measure by stage

Ingestion:

- bytes/sec parsed;
- rows/sec normalized;
- hash time;
- source decode time;
- Polars transform time.

Lakehouse:

- Parquet bytes written;
- file count / average file size;
- DuckLake commit time;
- compaction time;
- query scan bytes.

Models:

- Silver rebuild per affected day;
- Gold mart rebuild per affected day/service;
- forecast backtest time;
- OR-Tools solve time and optimality status.

API/UI:

- endpoint p50/p95;
- first chart/table render;
- virtual-grid scroll performance;
- client bundle size.

## Regression rule

A change that materially increases refresh/query/solve time should include benchmark evidence and a reason. Performance optimizations must not obscure WFM formulas or weaken correctness checks.
