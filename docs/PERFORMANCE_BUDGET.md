# Performance Budget

Performance is a product feature for an RTA tool.

These are initial engineering targets, not guaranteed benchmarks. They will be revised using representative synthetic datasets and real-world scale tests.

## User-facing targets

- UI navigation from already-materialized local data should feel immediate.
- Common dashboard/API queries should generally complete well below one second after warm-up.
- Normal daily refresh should process only new/changed data and normally complete in seconds to tens of seconds at typical desktop WFM scale.
- A correction to one day should not trigger a full historical rebuild.
- A first-time multi-month bootstrap may take materially longer and is treated separately from incremental refresh.

## Engineering targets

Track:

- source bytes/sec parsed;
- rows/sec normalized;
- Parquet compression ratio;
- interval mart rebuild time per affected day;
- common query p50/p95;
- refresh p50/p95;
- database/lake growth per month;
- peak working memory.

## Benchmark datasets

Create synthetic benchmark fixtures at several scales:

```text
small    30 days
medium   6 months
large    12+ months / high-volume call & status history
```

Benchmarks should include call-by-call, agent-status and interval data because their shapes stress the system differently.

## Regression rule

Any change that materially increases refresh/query time should provide a reason, benchmark evidence and, where appropriate, a mitigation plan.
