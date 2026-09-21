# WFMHub 2 generated design references

These images were generated with the built-in image generation tool on
2026-09-20 and 2026-09-21. They translate the WFMHub-Portable design tokens
into reviewable desktop concepts. The original three-screen RTA study has an
earlier five-item nav; the nine-screen full-product pack uses the authoritative
six-workspace shell in [FULL_PRODUCT_UI.md](../FULL_PRODUCT_UI.md). All names
and values are synthetic. None of these are executable product screens or
business-calculation authority.

The approved palette revision replaces bright-blue information accents with
the reference workbook's green `#1F7A53` / pale green `#DDF3E8` and adds
**by Anass ASSRI**. The two green files below are the current shell/RTA visual
anchors. Other original images remain concept studies; production tokens and
credit are defined in the UI blueprints, not inferred from old raster colors.

## Saved outputs

### Phase 1 RTA studies

- `wfmhub2-command-center.png` — 1586 x 992, SHA-256
  `cc45ba6acdf01c6dde31e12521b24e323c1832dba11ff689d1351ddc302f37a1`
- `wfmhub2-attendance-coverage.png` — 1586 x 992, SHA-256
  `5ea0f47f9d199d7c0659d45cfdc0214ab129686f4268c845969c792fbc69f52a`
- `wfmhub2-risk-decision.png` — 1586 x 992, SHA-256
  `500553f2d2dc415dfc982a49180efee0f4f754e6279be218bac95fe64261ed49`
- `wfmhub2-command-center-green.png` — approved palette/credit revision,
  SHA-256 `9981413238c853b6d80b83c4a4316d53eef58f9cc3995c4aac21d2720d0a502a`

### Full-product pack

| Image | SHA-256 |
| --- | --- |
| `wfmhub2-full-command.png` | `462f18c058d755bb54c8af4f12534510de2e2e18ec4cded4419fd83d844fc259` |
| `wfmhub2-forecast-demand.png` | `6a63b78daba7823b6cfe13ee7bfa3df6147265f132a79c582a21d97b871a765b` |
| `wfmhub2-staffing-requirements.png` | `f8c5502501920ff46d77e71a549485b010e6f172923038e188e72a113a803884` |
| `wfmhub2-schedule-quality.png` | `2cf7ac90fcd15c967968511034579cd34e3e670e6f033ba9ece0e8b4948fe0b9` |
| `wfmhub2-shrinkage-absence.png` | `ceefc2e985813a66d426f95a72676474ae1380c3ca84170d6e91d779c23ea2ae` |
| `wfmhub2-scenario-optimization.png` | `ea12339e531f7d38f625947690f7769d8fd6f0e6d9d8b39b64c09c738b1759f8` |
| `wfmhub2-capacity-hiring.png` | `a9bf46f47d2e08711bc937ef17e4f31f2165e86dd8727834860376bfe550f1fc` |
| `wfmhub2-realisations-outcomes.png` | `a6c209aa2dd25adcc7fb3740ae9356cbdcb0c61f8b7979ac85792079a218f423` |
| `wfmhub2-governance-delivery.png` | `a35c2acb81606d9209c83158e69d037f965c97b8d05e9651fd3ff6702c826c5c` |
| `wfmhub2-full-command-green.png` (approved shell revision) | `79d242cde5396c5ce8c0e81bae544ff6e055fd406c286971843ad1db16405015` |

The normalized final prompt set for the full-product pack is in
[FULL_PRODUCT_PROMPTS.md](FULL_PRODUCT_PROMPTS.md). Each generation used the
existing RTA Command Center as a style reference, not as an edit target.

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
