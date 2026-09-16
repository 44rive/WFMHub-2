# WFMHub 2.0 Roadmap

The roadmap is organized by **WFM capability**, not by framework implementation.

## Foundation — platform and governed data

- Tauri desktop shell + Python sidecar lifecycle;
- SQLite control plane;
- DuckLake/Parquet analytical plane;
- incremental source manifest and refresh planner;
- adapter contract for Verint/Storm/generic CSV/Excel;
- canonical service/interval/agent concepts;
- synthetic fixture library;
- portable Windows CI/release pipeline.

## Intraday / RTA

- RTA Command Center;
- current service and workload;
- required/scheduled/present/effective staffing ladder;
- attendance evidence;
- staffing-gap decomposition;
- 2–4 hour risk horizon;
- intervention candidate engine;
- decision/outcome log;
- intraday timeline and agent drill-down.

## Forecast and staffing

- forecast-vintage storage;
- bias/WAPE/MAE/RMSE;
- weekday/interval error patterns;
- StatsForecast baselines;
- MLForecast/XGBoost models;
- hierarchical forecast reconciliation;
- independent staffing requirement service;
- shrinkage uplift and requirement audit trail.

## Schedule intelligence

- schedule vs requirement coverage fit;
- over/understaffed FTE-hours;
- break/lunch concentration;
- skill mismatch;
- training/PTO displacement;
- schedule-quality findings;
- OR-Tools scheduling prototype.

## Scenario lab

- volume/AHT/shrinkage/FTE deltas;
- absence scenarios;
- cross-skill movement;
- training/PTO scenarios;
- forecast-vintage comparison;
- scenario result persistence and comparison.

## Tactical capacity

- weekly/monthly workload;
- shrinkage and productivity assumptions;
- required headcount;
- PTO/training capacity;
- hiring lead-time model;
- attrition scenarios.

## Strategic workforce planning

- 12–18+ month demand/capacity horizon;
- hiring plans;
- budget/cost assumptions;
- outsource/insource scenarios;
- skill-mix strategy;
- capacity-risk bands.

## Decision learning

Once sufficient governed decision/outcome history exists:

- intervention effectiveness by context;
- expected recovery distributions;
- confidence calibration;
- operational-cost modelling;
- recommendation ranking based on observed outcomes.

AI/LLM explanation may sit on top of these governed products, but it should not become the metric calculation engine.
