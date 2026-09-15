# WFM Domain Model

This document describes the business concepts WFMHub models independently of any source vendor.

## Domain boundaries

Vendor formats belong in `adapters/`. The domain layer should speak in generic WFM concepts such as service scope, interval demand, staffing requirement, scheduled activity, attendance evidence and intervention.

A Verint forecast row and a future Genesys forecast row should eventually map into the same canonical forecast concept.

## Core entities

### Service scope

A governed unit of WFM planning and reporting. A service scope may represent a queue, line of business, language, client, market, skill group, or configured rollup.

### Business interval

The primary intraday analytical grain. The default target is 15 minutes, although sources may arrive at different grains.

### Demand

Demand describes incoming workload. Typical measures include offered contacts, handled contacts, AHT and workload seconds.

### Forecast

Expected future demand at service/interval grain, including version, method and source provenance.

### Staffing requirement

The productive staffing required to meet a configured service objective, plus the scheduled staffing required after shrinkage assumptions.

### Schedule

Planned agent activities over time, including productive work and non-productive events such as breaks, lunch, training, meetings or approved absence.

### Attendance evidence

Observed evidence that an agent was available, active, late, absent or otherwise away. Evidence may come from login/logout, agent status, activities or other sources.

Attendance classifications must carry evidence quality and freshness. Missing evidence is not automatically absence.

### Service outcome

Observed customer outcome such as service level, answer time, abandon/lost contacts or routed rate, configured by service profile rather than hard-coded globally.

### Decision / intervention

An operational action proposed or taken in response to a WFM condition, with reason, expected impact and eventual measured outcome.

## Canonical interval model

A useful canonical interval fact can contain:

```text
business_date
interval_start
service_scope
forecast_volume
actual_volume
forecast_aht
actual_aht
required_productive_fte
required_scheduled_fte
scheduled_fte
present_fte
effective_fte
service_level
staffing_gap
```

Not every source supplies every field. The canonical model should preserve null/unknown values rather than force false completeness.

## Staffing ladder

WFMHub should make staffing losses visible as a ladder rather than a single opaque number:

```text
Required scheduled FTE
        |
        v
Scheduled FTE
  - planned away / PTO
        |
        v
Expected available FTE
  - absence / late starts
        |
        v
Present FTE
  - non-productive / execution loss
        |
        v
Effective productive FTE
        |
        v
Staffing gap vs requirement
```

The exact terms may vary by organization, but the decomposition must remain explicit and configurable.

## Intraday risk

Risk is not simply current service level. It combines future interval conditions such as:

- forecast demand and AHT;
- staffing requirement;
- scheduled coverage;
- planned shrinkage;
- known attendance evidence;
- break/lunch/activity concentration;
- current execution trends;
- optional confidence bands.

The initial implementation can be deterministic and rule-based. More sophisticated statistical models can be introduced only after the base signals are trustworthy.

## Forecast accuracy

WFMHub should support multiple accuracy measures because each tells a different story.

Common metrics include:

- **Bias** — systematic over/under forecast;
- **WAPE** — weighted absolute percentage error across a period;
- **MAPE** — useful where denominator behavior is acceptable;
- **MAE/RMSE** — absolute error measures when volume scale matters.

Accuracy should be explorable by service, date, day-of-week and interval.

## Staffing requirements

Requirement calculation is a domain service, not a UI formula.

Initial path:

1. offered demand;
2. AHT/workload;
3. service target;
4. queueing model such as Erlang C where assumptions fit;
5. productive requirement;
6. shrinkage uplift;
7. scheduled requirement.

More complex routing/skill environments may require simulation rather than a single Erlang model.

## Schedule quality

A schedule is not good merely because it matches total daily FTE. WFMHub should evaluate interval alignment.

Possible measures include:

- FTE-hours under requirement;
- FTE-hours over requirement;
- coverage fit percentage;
- service-risk weighted shortage;
- lunch/break concentration;
- activity displacement cost;
- skill mismatch;
- shift efficiency.

## Scenarios

Scenario inputs should be explicit deltas from a governed baseline, for example:

```text
volume_multiplier = 1.10
AHT_delta_seconds = 30
absence_rate = 0.08
additional_fte = -3
shrinkage = 0.31
```

Scenario outputs should reuse the same staffing and service engines as production views. A scenario engine must not become a parallel set of formulas.

## Intervention model

An intervention candidate should eventually include:

```text
intervention_type
service_scope
valid_from / valid_to
eligibility constraints
estimated_fte_impact
estimated_service_impact
confidence
operational_cost
reason/evidence
```

Ranking can evolve toward a score such as:

```text
expected impact x confidence / operational cost
```

but the component values should remain visible rather than hiding decisions behind one opaque score.

## Decision outcome model

A taken intervention records baseline state, expected impact and outcome windows. That enables questions such as:

- Which intervention types usually recover service fastest?
- Which services benefit most from cross-skill support?
- How much productive time is typically recovered by activity control?
- When does moving lunch create downstream risk instead of solving it?

This is the foundation of WFMHub's learning loop.
