# WFMHub 2.0 — Project Vision

## Mission

Build a portable, vendor-neutral workforce intelligence layer that helps a real-time analyst make better intraday decisions today and grows into the planning, optimization, and capacity toolkit of a workforce manager tomorrow.

WFMHub should combine the rigor of a governed WFM model with the speed of an operational control tower.

## The problem

WFM operations are rarely contained in one system. A typical environment may contain a scheduling/forecasting platform, telephony or contact-routing data, agent-state feeds, Excel rosters, attendance evidence, manual mappings, and local business rules.

The operational problem is not merely lack of data. It is the time required to reconcile that data into a trustworthy explanation and then decide what action to take.

Examples:

- Service is below target, but is the driver demand, attendance, schedule shape, or execution?
- A staffing shortage exists now, but will it recover naturally or get worse over the next two hours?
- Several interventions are available, but which one has the best expected impact and lowest operational cost?
- Forecast error repeats every Monday morning, but is the issue bias, AHT, shrinkage, or schedule fit?
- Headcount looks sufficient monthly, but where do interval-level shortages remain?

WFMHub exists to answer those questions from governed evidence.

## Product promise

For any WFM problem, the product should progressively answer five questions:

1. **What is happening?**
2. **Why is it happening?**
3. **What is likely to happen next?**
4. **What can I do about it?**
5. **Did the action work?**

That creates the operating loop:

```text
Observe -> Explain -> Predict -> Recommend -> Decide -> Measure -> Learn
```

## What WFMHub is

WFMHub is a **workforce intelligence and decision layer**.

It can sit above Verint, NICE, Genesys, Amazon Connect, telephony exports, Excel files, CSV files, custom rosters, or other operational sources. Source systems remain authoritative for the facts they own; WFMHub creates a common analytical and decision model across them.

WFMHub aims to become particularly strong in the space between a traditional WFM suite and the spreadsheets people build around it.

## What WFMHub is not

The project is not initially trying to replace every feature of a mature enterprise WFM suite. It does not need payroll, HR master data, omnichannel routing, or a giant administration platform to be valuable.

It should first become exceptional at WFM intelligence:

- reconciling source evidence;
- measuring service and staffing correctly;
- identifying drivers;
- forecasting risk;
- recommending interventions;
- evaluating forecast and schedule quality;
- modelling staffing and scenarios;
- optimizing workforce choices;
- recording decisions and outcomes.

## Three planning horizons

### 1. Intraday / RTA

Time horizon: now through the next few hours.

Primary user: real-time analyst, team lead, operations manager.

Primary decisions:

- service recovery;
- break/lunch movement;
- activity recovery;
- cross-skill support;
- training/coaching release;
- overtime/VTO recommendations;
- absence and late-start escalation;
- intraday forecast adjustment.

The product should present current state, explain the gap, predict near-term risk, and rank interventions.

### 2. Tactical WFM

Time horizon: tomorrow through roughly 8–12 weeks.

Primary user: forecaster, scheduler, WFM analyst/manager.

Primary decisions:

- forecast adjustment;
- schedule fit;
- PTO/training capacity;
- shrinkage planning;
- staffing requirement;
- overtime or flexible coverage;
- recruitment timing;
- schedule redesign.

The product should identify repeated patterns and quantify the structural causes behind service misses.

### 3. Strategic workforce planning

Time horizon: several months through 12–18+ months.

Primary user: WFM manager, operations leadership, finance/capacity planning.

Primary decisions:

- headcount plan;
- hiring classes;
- attrition assumptions;
- budget;
- outsourcing/insourcing;
- site or language mix;
- seasonal capacity;
- scenario comparisons.

## Core product modules

### RTA Command Center

The operational home screen. It combines service, demand, required FTE, scheduled FTE, present/effective FTE, attendance evidence, and near-term risk by service scope and interval.

### Gap Decomposition

A staffing or service miss should be decomposed into understandable drivers, for example:

```text
Required FTE        18.4
Scheduled FTE       19.0
PTO/Away            -1.0
Absence             -2.0
Late starts         -1.0
Offline/Aux loss    -1.3
Effective FTE       13.7
Gap                 -4.7
```

The decomposition should preserve uncertainty. Unknown evidence remains unknown rather than being silently classified as absence.

### Intraday Risk Horizon

Predict the next 2–4 hours at 15-minute grain and highlight intervals moving from safe to watch, risk, or critical.

Risk drivers may include forecast demand, AHT, schedule, known PTO, break/lunch concentration, current attendance, and carry-over operational conditions.

### Intervention Engine

Generate deterministic recommendations before adding AI-generated recommendations.

Examples:

- return movable offline agents;
- shift breaks/lunches;
- release optional coaching/training;
- request cross-skill support;
- offer overtime;
- consider VTO when materially overstaffed.

Recommendations should include estimated impact, confidence, constraints, and reason.

### Decision & Outcome Log

Record what action was taken, why, expected impact, and observed outcome.

This creates organizational memory and eventually enables intervention-effectiveness analysis.

### Forecast Intelligence

Measure forecast performance with bias, WAPE, MAPE and interval patterns. Identify recurring over/under-forecast conditions by queue, service, day of week, interval and season.

The first goal is not “AI forecasting”; it is visibility into how forecasts behave and why they fail.

### Staffing Requirement Engine

Independently calculate productive and scheduled staffing requirements from demand, AHT, service objectives and shrinkage.

Initial methods can include Erlang C where appropriate, followed by simulation for more complex environments.

### Schedule Intelligence

Evaluate whether the schedule is structurally aligned with demand, not just whether people attended it.

Potential metrics:

- coverage fit;
- demand alignment;
- understaffed/overstaffed FTE-hours;
- lunch/break concentration;
- activity placement;
- skill coverage;
- shift efficiency.

### Scenario Lab

Allow users to ask controlled “what if” questions:

- volume +10%;
- AHT +30 seconds;
- absenteeism 8%;
- lose 3 FTE;
- move 5 agents between services;
- shrinkage rises from 27% to 31%.

Each scenario should quantify staffing, service, capacity and risk consequences.

### Capacity Planning

Extend the same governed data model into hiring and headcount plans across months, including shrinkage, attrition, training/ramp, hiring lead time and service demand.

## Decision intelligence principles

### Facts before recommendations

A recommendation is only as trustworthy as the evidence beneath it. Calculations remain deterministic, testable and traceable to source data.

### Explain before optimize

The product should explain why a gap exists before trying to optimize it. Optimization without explanation is hard to trust operationally.

### Unknown stays unknown

Missing or stale evidence should not be converted into convenient zeros, no-shows or absences.

### The user remains the decision-maker

WFMHub can recommend, rank and explain. Operational policy and human judgment still determine which intervention is appropriate.

### Learning is outcome-based

The decision log connects intervention to measured result. This is the foundation for future recommendation scoring and a WFM copilot.

## Future WFM copilot

Natural-language assistance belongs on top of governed facts, not instead of them.

A future copilot should be able to answer questions such as:

> Why did Service A miss target yesterday?

with a response grounded in deterministic metrics:

- volume variance;
- AHT variance;
- productive staffing variance;
- absence/late-start impact;
- schedule-shape impact;
- specific critical intervals;
- recovery point and likely cause.

The language model explains and navigates the WFM model; it does not invent the model.

## Success criteria

WFMHub succeeds when an RTA can open it and understand the current operational problem faster than by reconciling several spreadsheets, and when a WFM manager can use the same data foundation for forecasting, staffing, scheduling, scenarios and capacity decisions.
