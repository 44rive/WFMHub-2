# Incremental Refresh Engine

## Contract

> **The cost of a normal refresh should scale with changed input and affected dependencies, not with total historical data.**

A six-month history should not make adding today's extract six times slower than adding today's extract to a one-month history.

## Source identity

Every discovered source version is identified by:

```text
logical source type
path / source key
file size
precise mtime
SHA-256 when needed
adapter/parser version
mapping/policy fingerprint
```

The quick path compares cheap metadata first. Hashing is performed when metadata or governing policy indicates the source may need re-evaluation.

## Refresh stages

```text
1. discover input files read-only
2. resolve adapter
3. quick manifest comparison
4. calculate SHA-256 if required
5. skip/reactivate known immutable source version when valid
6. normalize changed version with Polars/plain Python
7. write/replace affected Bronze facts in DuckLake
8. determine affected business-date/service scope
9. rebuild affected Silver canonical facts
10. rebuild affected Gold marts/intelligence
11. commit control-plane manifest + refresh result
12. retain DuckLake snapshot information for reproducibility
```

## Bronze / Silver / Gold invalidation

Not every change requires raw reparsing.

### New source file

```text
raw file -> Bronze -> affected Silver -> affected Gold
```

### Source-file correction

Replace only the source version/date ranges owned by that extract, then rebuild its descendants.

### Mapping/scope change

```text
existing Bronze -> affected Silver -> affected Gold
```

Do not reopen original files merely because a queue mapping changed.

### Business-rule change

Rebuild the specific Silver/Gold models whose rule fingerprint changed.

### Parser change

Only source versions produced by the changed parser contract need to be re-normalized.

## DuckLake snapshots

DuckLake creates snapshots as analytical state changes. WFMHub should capture the relevant snapshot ID/time in refresh metadata when practical.

This enables future reproducibility questions such as:

```text
What did the staffing mart look like at 10:40
when the RTA decided to move two agents?
```

Decision records should eventually retain the analytical snapshot or governed model version used for the decision.

## Partition strategy

Partition analytical tables only where pruning benefit outweighs small-file overhead. Likely candidates include business date/month and possibly service scope for very large datasets.

Do not blindly partition every table by every dimension.

High-frequency events such as call-by-call/status history should be written in reasonably sized files rather than one file per tiny interval.

## Compaction

Repeated corrections can create many small Parquet files. DuckLake maintenance/compaction should be a controlled maintenance operation with explicit performance thresholds.

Normal refresh should not compact all history.

## Atomicity

A refresh must not leave the product in a mixed state.

Control-plane status should distinguish:

```text
planned
running
succeeded
failed
```

A failed analytical write must not mark the source version active/successful in SQLite.

## Full rebuild

A full rebuild remains available for:

- major model/schema migration;
- corruption recovery;
- deliberate benchmark/validation;
- parser/model reset.

It is never the default refresh path.

## Performance instrumentation

Every refresh should eventually emit:

```text
files seen
files hashed
files changed
bytes parsed
rows normalized
business dates affected
DuckLake tables touched
Gold marts rebuilt
elapsed by stage
peak memory if available
snapshot id/time
```

This makes performance regressions measurable rather than anecdotal.
