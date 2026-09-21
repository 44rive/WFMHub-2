# WFMHub 2 generated design references

These images were generated with the built-in image generation tool on
2026-09-20. They translate the WFMHub-Portable design tokens and Phase 1
information architecture into reviewable desktop concepts. They contain only
synthetic names and values and are not executable product screens.

## Saved outputs

- `wfmhub2-command-center.png` — 1586 x 992, SHA-256
  `cc45ba6acdf01c6dde31e12521b24e323c1832dba11ff689d1351ddc302f37a1`
- `wfmhub2-attendance-coverage.png` — 1586 x 992, SHA-256
  `5ea0f47f9d199d7c0659d45cfdc0214ab129686f4268c845969c792fbc69f52a`
- `wfmhub2-risk-decision.png` — 1586 x 992, SHA-256
  `500553f2d2dc415dfc982a49180efee0f4f754e6279be218bac95fe64261ed49`

## Final prompt — RTA Command Center

```text
Use case: ui-mockup. Asset type: high-fidelity desktop web application screen.
Create a shippable 16:10 WFMHub 2 RTA Command Center for a single-user contact
center RTA. Preserve the established compact enterprise theme: navy #0B1F33,
teal #007C83, gold #D6A84B, canvas #EEF3F5, white panels, cool-gray borders,
red #B42318 only for verified breach, amber for review/unknown, and green for
healthy. Use Aptos/Segoe-like typography, compact square panels, and no
gradients, glassmorphism, or dark content canvas.

Use the global shell WFMHUB 2 / RTA WORKBENCH with COMMAND, OPERATE, DECIDE,
REVIEW, GOVERN and COMMAND active. Include data-through status, COMMAND ·
OBSERVE, Overview/Intervals tabs, business-date/service/planning filters,
Export and Refresh evidence actions, and a freshness/evidence strip. Main
content: SERVICE POSITION as a count of separate scopes with no synthetic
portfolio SL, STAFFING GAP, ATTENDANCE, NEXT RISK, a 15-MINUTE OPERATING
POSITION chart, proposal-oriented ACTION QUEUE, SERVICE & STAFFING MATRIX, and
DATA TRUST. Staffing totals must reconcile. Express proposal impact as FTE-gap
change, not unvalidated service-level lift. Use only synthetic scope names and
values. No people/customer data, uploads, cloud concepts, watermark, laptop
frame, or decorative illustration.
```

The generated base was iteratively corrected with this final contract:

```text
Render the primary navigation exactly COMMAND, OPERATE, DECIDE, REVIEW,
GOVERN. Keep COMMAND active. Render WFM white, HUB gold, and 2 light teal.
Separate service scopes and suppress any portfolio SL total. Reconcile the
staffing rows to Required 73.0, Present 69.5, Gap -3.5. Use proposal wording
and deterministic FTE-gap effects only.
```

## Final prompt — Attendance & Coverage

```text
Use case: ui-mockup. Asset type: high-fidelity desktop web application screen.
Create a shippable 16:10 WFMHub 2 Attendance & Coverage workbench for a single
RTA. Use the same navy #0B1F33, teal #007C83, gold #D6A84B, cool-gray canvas,
white panels, semantic red/amber/green/purple, Aptos/Segoe-like typography,
compact spacing, and restrained radii as the old WFMHub theme.

Use the WFMHUB 2 / RTA WORKBENCH shell with COMMAND, OPERATE, DECIDE, REVIEW,
GOVERN and OPERATE active. Include Service & Demand, Staffing & Coverage, and
Attendance tabs; date/LOB/team filters; evidence refresh/export; and a strip
stating Agent Status primary, LILO fallback, unknown stays unknown, read only.
Show KPI cards DUE, PRESENT, EFFECTIVE, PROVEN NO-SHOW, UNKNOWN; a STAFFING
LADDER from Required through Effective and Gap; a CONTACT & EVIDENCE QUEUE
using anonymous IDs; a SCHEDULE VS OBSERVED timeline; an exception table; and
an EVIDENCE INSPECTOR warning not to classify absence without positive
evidence. Label headcount as HC and FTE separately. Missing evidence remains
UNKNOWN, current-shift disconnects remain OFFLINE NOW, and the reconciled
Present 75.0 to Effective 72.5 loss is -2.5 FTE. A zero proven-no-show card is
healthy green, not red. Synthetic IDs and values only. Minimum readable text.
No employee/customer data, uploads, cloud concepts, dark content panels,
decorative imagery, marketing layout, or watermark.
```

## Final prompt — Risk & Decision Workspace

```text
Use case: ui-mockup. Asset type: high-fidelity desktop web application screen.
Create a shippable 16:10 WFMHub 2 Risk & Decision Workspace where one RTA
explains a selected staffing risk, compares feasible interventions, and records
a decision. Use the same WFMHub navy #0B1F33, teal #007C83, gold #D6A84B,
cool-gray/white canvas, semantic status colors, Aptos/Segoe-like typography,
compact density, and restrained geometry.

Use the WFMHUB 2 / RTA WORKBENCH shell with COMMAND, OPERATE, DECIDE, REVIEW,
GOVERN and DECIDE active. Include Action Queue/Decision Log tabs and selected
risk context. WHY THIS RISK EXISTS contains two exact bridges: Baseline
requirement 26.1 + Volume 1.8 + AHT 0.7 = Current requirement 28.6 FTE; and
Scheduled 30.0 - Planned away 1.2 - Attendance loss 2.5 - Execution loss 1.7 =
Effective 24.6 FTE; Effective 24.6 - Required 28.6 = Gap -4.0 FTE. RISK WINDOW
plots staffing gap against zero, not projected service level. Each intervention
shows deterministic FTE-gap change, confidence, cost/trade-off, constraint, and
evidence. Service effect says Not yet validated. Show SELECTED ACTION and RECORD
DECISION with Accept, Defer, Reject, reason, owner, review time, and proposal-only
warning. The experience is human decision support, not autonomous control.
Synthetic data only; no uploads, cloud concepts, marketing layout, or watermark.
```
