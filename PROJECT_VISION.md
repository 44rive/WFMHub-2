# WFMHub 2.0 — Project Vision

## Mission

Build a portable, vendor-neutral workforce intelligence layer that helps an RTA make better intraday decisions today and grows into a serious forecasting, staffing, scheduling, capacity, and workforce-management platform tomorrow.

The system should reduce the time between **evidence** and **decision**.

## The problem

Operational workforce data is usually fragmented across WFM systems, telephony, status exports, schedules, forecasts, attendance files, spreadsheets, and human context. The RTA often spends substantial effort proving what happened before they can decide what to do.

Enterprise WFM suites are valuable systems of record, but they are not always optimized for a local decision workflow that combines every source, exposes every assumption, and records whether an intervention actually worked.

WFMHub addresses that gap.

## North star

For any service scope and planning horizon, WFMHub should answer:

1. **What is happening?**
2. **Why is it happening?**
3. **What is likely to happen next?**
4. **What can we do about it?**
5. **What is the expected impact?**
6. **What decision was taken?**
7. **Did it work?**
8. **What should we learn from the outcome?**

That creates the product loop:

```text
Observe -> Explain -> Predict -> Recommend -> Decide -> Measure -> Learn
```

## Product horizons

### Intraday / RTA

**Now -> next few hours**

Primary questions:

- Are we meeting the service objective?
- Are enough productive people available?
- Is the problem demand, staffing, shrinkage, execution, or data quality?
- Where is the next risk window?
- Which interventions are feasible now?

Products:

- RTA Command Center;
- interval service and staffing ladder;
- gap decomposition;
- attendance evidence and uncertainty;
- 2–4 hour risk horizon;
- intervention queue;
- action log and measured recovery.

### Tactical WFM

**Tomorrow -> roughly 12 weeks**

Primary questions:

- Is the forecast systematically biased?
- How many productive/scheduled FTE are required?
- Where is the schedule structurally misaligned with demand?
- How much PTO/training can be absorbed?
- Which assumptions create the largest risk?

Products:

- forecast accuracy and bias;
- independent staffing requirement engine;
- shrinkage intelligence;
- schedule-quality analysis;
- scenario lab;
- short-range capacity and planning constraints.

### Strategic WFM

**Months -> 18+ months**

Primary questions:

- How much capacity will be required?
- When must recruitment start?
- What happens under attrition, productivity, AHT, demand, or shrinkage scenarios?
- Which workload should be insourced, outsourced, or cross-skilled?

Products:

- long-range forecasts;
- headcount and hiring models;
- attrition and shrinkage scenarios;
- budget/cost capacity views;
- outsourcing and skill-mix scenarios.

## Product principles

### 1. Source evidence remains authoritative

WFMHub enriches and reconciles source systems; it does not fabricate operational facts.

### 2. Unknown stays unknown

Missing login/status/activity evidence must not silently become “absent”, zero, or compliant.

### 3. Explain before predicting

A trustworthy deterministic decomposition is more valuable than an opaque prediction built on weak inputs.

### 4. Prediction must be measurable

Forecast and risk models are evaluated against later outcomes. Model quality is visible, not assumed.

### 5. Recommendations must show their reasoning

An intervention should expose eligibility, estimated FTE/service impact, confidence, constraints, and operational cost.

### 6. Decisions deserve first-class data

Operational decisions and their measured outcomes become part of the WFM dataset. This allows WFMHub to learn which interventions work in which contexts.

### 7. One domain model, many interfaces

The same business engine should support the desktop app, CLI, API, reports, future team server, and automated jobs.

### 8. Portable/offline is a feature

WFMHub should remain usable on a locked-down corporate Windows workstation without requiring local admin, a database server, or internet access.

## What WFMHub is not

WFMHub 2.0 is not initially trying to replace every capability of an enterprise WFM platform. It is not a payroll system, HR system, telephony platform, or employee master-data authority.

Its differentiation is the intelligence layer:

```text
Verint / NICE / Genesys / Storm / CSV / Excel / APIs
                         |
                         v
                    WFMHub 2.0
                         |
       governed WFM model + intelligence + decisions
```

The architecture is intentionally vendor-neutral so additional systems can map into the same service, forecast, schedule, attendance, staffing, and decision concepts.

## Success criteria

WFMHub is succeeding when it makes the user better at WFM rather than merely giving them more dashboards.

Examples:

- an RTA detects a future shortage before service collapses;
- a staffing gap can be decomposed into understandable drivers;
- a planner can reproduce how a staffing requirement was calculated;
- forecast bias is visible by service, weekday, and interval;
- a schedule-quality issue can be quantified in FTE-hours and service risk;
- scenarios reuse the production staffing logic rather than spreadsheet copies;
- interventions have measured outcomes;
- long-range headcount assumptions can be traced back to workload and shrinkage.

That is the product WFMHub 2.0 is being built to become.
