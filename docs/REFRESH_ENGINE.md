# Incremental Refresh Engine

## Goal

Refresh cost should scale with **changed data**, not with total history.

Six months of already-loaded WFM history should not make today's refresh six months expensive.

## Data stages

```text
source extract
    |
    v
fingerprint + manifest
    |
    v
Bronze normalization
    |
    v
Silver WFM mapping/scope
    |
    v
DuckDB Gold marts/intelligence
```

## Source identity

Each loaded source version should be identifiable from at least:

- logical source type;
- source path/name;
- byte size;
- precise modified time;
- SHA-256 content hash;
- parser version;
- relevant policy/config fingerprint;
- discovered min/max business date;
- row count and load status.

Metadata checks can avoid hashing obvious unchanged files; a hash establishes actual content identity when needed.

## Change examples

| Change | Expected rebuild |
| --- | --- |
| No source/config change | none |
| Add today's extract | today's Bronze/Silver + dependent Gold slices |
| Correct yesterday | yesterday's affected partitions and dependent models |
| Replace July monthly file | July range only |
| Queue mapping change | affected Silver/Gold from existing Bronze |
| Metric definition change | affected Gold/intelligence only |
| Parser version change | affected source versions from source evidence |
| Full rebuild command | everything, explicitly requested |

## Dependency windows

Not every model is strictly same-day. The refresh planner needs model metadata describing dependency windows.

Examples:

- current interval staffing: changed interval only;
- daily attendance summary: changed day;
- rolling 28-day forecast accuracy: changed day plus impacted rolling windows;
- weekly pattern model: changed week/peer history;
- monthly capacity aggregate: changed month.

A dependency planner expands the changed source range only as far as required by downstream models.

## Atomicity

A source refresh should not leave the application half-updated.

The orchestration pattern is:

1. stage new source version;
2. build replacement partitions/marts;
3. validate row counts/schema/quality checks;
4. activate the new version;
5. update the manifest/refresh run;
6. retire or retain old versions according to retention policy.

On failure, the previous good state remains active.

## Bronze/Silver reason

Separating source normalization from business mapping is important.

If a queue mapping changes, reopening and reparsing months of original Excel/text exports is wasteful. WFMHub should reuse Bronze data and regenerate the mapped Silver/Gold ranges.

If parser logic changes, Bronze becomes invalid for the affected source/parser version and source evidence must be parsed again.

## Partition strategy

High-volume history should be partitioned at a grain that balances file count and pruning. Daily partitions are a good default for intraday sources; monthly partitions may be appropriate for smaller planning tables.

Partition keys should be business-time concepts such as year/month/day, not arbitrary load IDs.

## Performance instrumentation

Every refresh run should measure at least:

- files discovered;
- unchanged/changed/new files;
- bytes read;
- source parse time;
- rows normalized;
- Parquet write time;
- DuckDB model time;
- affected business range;
- rows replaced/inserted;
- total elapsed time;
- peak memory if practical.

Performance regressions should become observable rather than anecdotal.
