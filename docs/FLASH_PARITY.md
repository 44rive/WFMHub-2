# Legacy Flash comparison gate

Preview `.9` adds a read-only comparison on Operate for the four shipped Flash
profiles from WFMHub-Portable `v0.36.0` (`758de71`). The profile catalog is
copied from that immutable tag into `config/legacy_flash_profiles.toml`. It is
configuration, not a customer or employee extract.

## What is comparable

Choose the same business date and old Flash tab. The new view filters the
active validated Call-by-Call interval facts to that tab's exact queue
allowlist and `CALL_BY_CALL` source, then sums additive components by hour and
day. RSA Belgium's tab includes queues spanning both RSA BE FR and VL; the
ordinary Operate service/comparison selector shows only one pair and is not a
like-for-like Flash total. The comparison view avoids that false mismatch.

Compare offered/entered, answered/routed, abandoned/lost, answered within
target, abandoned within target, and handled seconds. Keep the source cut,
business date, queue population, and checkpoint consistent. An empty result
means no matching evidence was present, not proven zero demand. Do not compare
service ratios by averaging displayed intervals.

The view does **not** compute the old Flash SLA, routed rate, abandonment
rate, AHT, forecast, staffing, attendance, or action guidance. Those require
their governed metric/profile and source contracts plus real-data parity.
User-reported launch success of Preview `.8` is not numeric parity evidence.

## Data and safety boundary

The authenticated endpoint `/api/rta/flash-parity?date=YYYY-MM-DD&profile=<id>`
returns only bounded aggregate counts, profile names, catalog fingerprint,
and active-generation provenance. It returns no queues, call rows, employee
identifiers, paths, or source files. The source-root fingerprint must still
match the active successful generation. A failed refresh leaves that previous
validated cut active; a changed/missing root suppresses the result.

## Acceptance still needed

On the managed workstation, compare one same-day profile with the old Flash
using the same exports. Record the old/new additive day totals and at least
one hourly row, first-refresh duration, active-generation counts/date ranges,
and quality totals. Send aggregate values only, never source extracts or
employee data. A normal changed-source refresh must also be observed before
date-scoped derived rebuild replaces full-cut rebuild.
