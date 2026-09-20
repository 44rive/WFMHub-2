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

Final Windows qualification run `35508043118` measured the exact extracted
release:

- ZIP: 300,607,038 bytes;
- extracted payload: 852,233,445 bytes across 13,375 files;
- SHA-256: `dee1588bbe7d96fa401c473c4754a5835dd3d571b8629e92712a68f7b4543ad6`;
- hosted-runner archive expansion step: 19 seconds;
- second full 14-capability subprocess doctor: 10.224 seconds;
- normal process-to-ready time: 1.345 seconds;
- post-smoke runtime: 2 processes, 102,010,880 working-set bytes and
  61,902,848 private-memory bytes.

Run `35507582306` produced the same archive bytes and SHA-256, providing a
reproducibility check across independent builds. The smoke ran from a
space/non-ASCII path with outbound traffic blocked, and heavy capability
imports remained outside normal startup.

These are GitHub-hosted Windows runner measurements, not promises for the
managed target workstation. Antivirus extraction overhead and company-policy
compatibility must still be measured by running the exact release there. The
CI budget records:

- exact ZIP and extracted bytes;
- extracted file/native-image counts;
- full subprocess-doctor duration;
- normal cold readiness and idle memory;
- extraction/antivirus-sensitive first-use time.

Heavy forecasting/optimization imports stay out of normal startup even though
every capability ships in the same release.

## Phase 0.4 hybrid-spike baseline

The local deterministic build produced:

- ZIP: 73,143,767 bytes;
- extracted stage: approximately 146 MiB across 84 files;
- SHA-256: `e26be8dcae3a23f24ae1e52fa40b0313cd3bafafeb30a01a133f5a5af0f66abc`;
- DuckDB-Wasm OPFS checkpoint/terminate/reopen: 3.683 seconds;
- Pyodide plus two small forecast-model fits: 26.366 seconds;
- HiGHS-Wasm integer staffing solve: 0.305 seconds.

The five browser probes passed with external hostname resolution mapped away
from the machine, then passed after a full host/browser restart with the same
profile; the OPFS counter advanced from 1 to 2. These Linux/Chromium figures
establish feasibility, not budgets for the managed Windows workstation or
production datasets.

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
- streaming/plain-Python transform time.

Storage/cache:

- SQLite transaction and mart rebuild time;
- database growth and backup time;
- browser-cache publish/rebuild time;
- query scan bytes.

Models:

- Silver rebuild per affected day;
- Gold mart rebuild per affected day/service;
- forecast backtest time;
- Pyodide load/model time and memory;
- HiGHS solve time, gap, feasibility, and optimality status.

API/UI:

- endpoint p50/p95;
- first chart/table render;
- virtual-grid scroll performance;
- client bundle size.

## Regression rule

A change that materially increases refresh/query/solve time should include benchmark evidence and a reason. Performance optimizations must not obscure WFM formulas or weaken correctness checks.
