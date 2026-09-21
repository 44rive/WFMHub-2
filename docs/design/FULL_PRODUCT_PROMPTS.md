# Full-product image prompt set

Mode: built-in image generation, `ui-mockup`. Generated 2026-09-21. Each
screen was generated separately, using `wfmhub2-command-center.png` as a
visual style reference. Governance and outcomes received small follow-up
edits to reconcile displayed state/filter labels. Shrinkage/absence and
capacity/hiring received follow-up edits to separate evidence completeness
from finalized-hour denominators and align hiring ramp with the January bridge.
The capacity card subtitle was then changed from "Confirmed plan" to
"Scenario assumption" because one cohort is still in planning.

## Shared prompt

```text
Create a high-fidelity, shippable 16:10 desktop WFMHub 2 workbench screen.
Image 1 is a visual style reference only; create a new screen, not an edit.
Faithfully preserve WFMHub-Portable's compact navy #0B1F33 header, white WFM,
gold #D6A84B HUB, light-teal 2, teal #007C83 active controls, cool-gray canvas,
white panels, thin gray rules, tabular numerals, and Aptos/Segoe-like type.
Use workbook green #1F7A53 and pale green #DDF3E8 instead of bright-blue
informational accents. Keep the navy header and teal primary actions. Add
discreet exact credit "by Anass ASSRI" in a footer margin.
Use the six-item nav COMMAND, OPERATE, PLAN, CAPACITY, REVIEW, GOVERN and mark
the active workspace with a gold underline. Include page kicker/title, scoped
filters and actions, an evidence/freshness strip, dense tables, charts, and
inspectable evidence. Minimum 12 px secondary text. Use synthetic names and
numbers only. No operational/person/customer data, uploads, cloud concepts,
autonomous actions, dark content panels, gradients, glassmorphism, marketing
layout, or watermark. Business formulas and classifications must not be
inferred by the UI; panels show governed results and provenance.
```

## Screen briefs

### Cross-horizon Command

```text
Title "WFM Command Center"; COMMAND active. Tabs Portfolio, Intraday,
Tactical, Strategic. Four horizon cards: TODAY 1 of 3 scopes below target;
NEXT 7 DAYS 18.5 FTEh uncovered; NEXT 12 WEEKS 9.8% forecast WAPE;
NEXT 18 MONTHS 34 HC peak gap. Keep units distinct. Add a four-lane horizon
risk map, priority queue spanning now/week/month/quarter, exact-measure
horizon table, and data-trust panel. No combined portfolio service level.
```

### Forecast & Demand Intelligence

```text
Title "Forecast & Demand Intelligence"; PLAN active; Accuracy tab. Select
one service scope, evaluation period, and forecast vintage. Show WAPE 9.8%,
bias -3.2%, MAE 42 contacts, selected Seasonal Naive, and hierarchy adjustment
+1.4% as separate measures. Include selected/baseline forecast vs actual,
rolling-origin model scorecard, weekday-by-interval signed-error heatmap,
vintage movement, training window, feature version, and selection reason.
Do not assume a complex model wins or treat future actuals as zero.
```

### Staffing Requirements

```text
Title "Staffing Requirements"; PLAN active. One selected 15-minute interval:
120 contacts x 420 seconds = 50,400 workload seconds = 56.0 Erlangs;
Erlang C under a versioned 80/20 service objective yields 66.0 productive FTE;
66.0 / (1 - 28.0% shrinkage) = 91.7 scheduled FTE. Show the explicit bridge,
interval requirement chart, assumption/provenance inspector, requirement
register, shrinkage composition 7+6+5+4+6=28%, and calculation checks.
Never conflate contacts, Erlangs, FTE, FTE-hours, or HC.
```

### Schedule Quality

```text
Title "Schedule Quality"; PLAN active; Coverage Fit tab. Use published
schedule and versioned requirement, not attendance. Show coverage fit 82.4%,
18.5 FTEh under, 9.0 FTEh over, six break-concentration intervals, and four
skill-mismatch intervals. Add requirement-vs-schedule chart, weekly signed
coverage heatmap, activity-concentration chart, prioritized findings, and
selected 10:00–10:15 inspector with required 91.7 FTE, published 85.2 FTE,
gap -6.5 FTE. Findings create proposals; schedules are not rewritten.
```

### Shrinkage & Absence Intelligence

```text
Title "Shrinkage & Absence Intelligence"; REVIEW active; Final Absence tab.
State that Verint Activities plus published schedule own finalized absence;
Agent Status/LILO remain provisional and unknown stays unknown. Show a
component bridge of 8,000 finalized scheduled hours less breaks 480, meetings
320, training 240, PTO 400, final absence 288, other governed 80 = shrinkage
1,808 hours (22.6%) and productive 6,192 hours (77.4%). Include planned vs
finalized trend, category/source/rule table, evidence completeness, and an
anonymous exception queue. Keep incomplete evidence outside finalized
denominators; never convert missing or unmapped activity to absence or zero.
```

### Scenario & Optimization Lab

```text
Title "Scenario & Optimization Lab"; PLAN active. Explicit baseline and
deltas: volume +10%, AHT +30 sec, absence 8%, additional FTE -3, shrinkage
31%, cross-skill availability. Baseline 440.0 required - 421.5 available gives
-18.5 FTEh gap. Scenario 490.0 required and 390.0 available gives -100.0
FTEh gap. Three proposals recover 20+12+10=42 FTEh, leaving -58 FTEh.
Show coverage comparison, proposal register, constraints, solver version/status
and trade-offs. Label "Optimal for stated model" but warn that this is not
operational approval. Source schedules remain unchanged; no service-level
impact claim.
```

### Capacity & Hiring Plan

```text
Title "Capacity & Hiring Plan"; CAPACITY active; Strategic Plan tab. Show
24-month required vs available productive HC with uncertainty band and hiring
start-by marker. Exact headcount bridge: current 310 HC - attrition 32 HC +
planned productive starts 20 HC = projected supply 298 HC; January requirement
332 HC; additional productive starts needed 34 HC. Include cohort hiring/ramp
table, assumptions for attrition 7.2%, recruitment 16 weeks, ramp 8 weeks,
productivity 0.92 FTE/HC, shrinkage 29%, skill/location exposure, and capacity
risk queue. Mark assumptions as planning inputs, not HR/payroll facts. Do not
double-count cross-skilled staff or equate HC and FTE.
```

### Realisations & Decision Outcomes

```text
Title "Realisations & Decision Outcomes"; REVIEW active; Decision Outcomes
tab; filter All decisions. Show 12 recorded, eight measured, three pending,
one insufficient-evidence decision. Compare forecast/actual offered contacts,
required/effective FTE, and target/actual service in separate aligned charts.
Selected D-042 expected +2.0 FTE, observed +1.5 FTE, volume rose 8%; observed
service change is not proof of causality. Include outcome register, descriptive
variance drivers, original and later evidence generations, and follow-up.
```

### Data Governance & Delivery

```text
Title "Data Governance & Delivery"; GOVERN active; Data Readiness tab.
Display four of seven READY sources, two PARTIAL, one STALE, mapping coverage
99.2%, 12 rejected rows, active generation #184, and verified backup PASS.
Show source authority/freshness table, quality backlog, source-to-Gold lineage,
read-only effective catalog versions, refresh history, and reports/archive.
Failed run #181 was not activated and left #180 active; later #183 was
superseded by #184. Sources are read-only, missing mappings stay visible, and
reports are replaceable outputs rather than authoritative data.
```

These prompts define visual intent only. The image outputs may contain
illustrative rounding or typography artifacts; the effective domain catalogs,
source contracts, and tests—not raster labels—govern implementation.

The approved palette/credit revision used built-in image edits of the
cross-horizon Command and Phase 1 RTA Command references. Their edit prompt
kept business values and layout fixed, changed bright-blue information accents
to workbook green, corrected the six-workspace navigation, and added the exact
credit. The remaining original raster concepts are pre-revision studies;
production code follows the updated token contract above.
