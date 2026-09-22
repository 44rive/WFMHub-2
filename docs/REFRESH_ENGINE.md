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
6. normalize changed version with streaming/plain Python
7. write/replace affected Bronze facts in the authoritative SQLite transaction
8. determine affected business-date/service scope
9. rebuild affected Silver canonical facts
10. rebuild affected Gold marts/intelligence
11. commit manifest + validated generation atomically
12. optionally refresh the rebuildable browser analytical cache
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

## Generation provenance

Every successful refresh records its source versions, policy fingerprints,
model versions, affected scopes, and activation time. Optional analytical
caches may record their own version, but they are not the authority.

This enables future reproducibility questions such as:

```text
What did the staffing mart look like at 10:40
when the RTA decided to move two agents?
```

Decision records retain the governed generation/model version used for the
decision.

## Optional analytical cache

DuckDB-Wasm may materialize derived tables in OPFS when measured queries need
columnar execution. Partition/cache only where pruning benefit outweighs
complexity. Likely candidates include business date/month and service scope for
large call/status histories.

Do not blindly partition every table by every dimension.

High-frequency events such as call-by-call/status history should be written in reasonably sized files rather than one file per tiny interval.

The current Phase 1 compatibility host streams Agent Status, LILO, and
Call-by-Call into generation-keyed SQLite batches and atomically rebuilds their
canonical facts. The same activation transaction rebuilds the attendance
agent-day read model and exact gap fragments from published schedule, approved
PTO/Away, Agent Status, and LILO evidence.

An exact unchanged candidate set now takes the conservative metadata fast path:
source type/key, size, precise mtime, adapter, policy, model, source root, and
attendance policy must still agree with the active successful generation. The
host then returns a no-op success and reuses that generation without hashing,
parsing, or duplicating facts. Added, removed, moved, policy-drifted, or
ambiguous sources force a governed rebuild.

Changed large files receive one SHA-256 pass and one streaming parse into
generation-keyed Bronze staging. Atomic activation verifies the bound manifest
and file metadata, then builds canonical facts from those staged rows; it does
not reopen the CSV. This replaced the four hash plus two parse passes in
Preview `.5` and shipped in Preview `.6`.

The next source-version change retains a reference to the successful generation
that owns each Status, LILO, or Call by Call Bronze file. An unchanged file with
matching metadata is reused without hashing; changed metadata gets one hash,
then an exact known version can be reactivated after A→B→A without parsing or
copying its rows. Reuse requires the same selected source root, source key,
content SHA-256, adapter, policy, and FTE roster version. A new version uses the
precomputed hash for its one streaming parse. The complete source manifest and
active pointer still publish atomically.

Derived attendance, canonical call legs, and service intervals still rebuild
for the whole cut when any source changes. The source-version change therefore
reduces event-file I/O and Bronze duplication, but it does not yet meet the
full affected-scope cost contract above. Preview `.6` does not contain this
next change.

During a rebuild, `/api/rta/source-health` exposes bounded in-memory stage,
relative source key, elapsed time, and file progress. Unexpected failures keep
their stage and exception class in the safe failure code, print the traceback
to the local console, and atomically write the latest detailed diagnostic to
`data/diagnostics/refresh-failure.txt`. The HTTP response remains path- and
row-scrubbed, and the previous active generation remains authoritative.

Clearing or losing the browser cache must trigger a bounded rebuild from
authoritative SQLite/source evidence, never data loss.

## Atomicity

A refresh must not leave the product in a mixed state.

Control-plane status should distinguish:

```text
planned
running
succeeded
failed
```

A failed canonical/mart write must not mark the source version active. A failed
optional cache refresh does not invalidate the committed SQLite generation.

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
SQLite tables/generations touched
Gold marts rebuilt
browser cache tables refreshed
elapsed by stage
peak memory if available
generation id/time
```

This makes performance regressions measurable rather than anecdotal.
