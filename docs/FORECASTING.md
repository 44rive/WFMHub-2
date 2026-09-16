# Forecasting Architecture

## Objective

WFMHub forecasting is a governed model-selection system, not a single preferred algorithm.

The engine should make four things visible:

1. forecast vintage — when was this forecast created?
2. model/method — how was it produced?
3. error — how did it perform when actuals arrived?
4. hierarchy — does it reconcile with higher/lower planning levels?

## Data grain

The canonical target is service scope x interval x business date, with enough history retained to evaluate seasonal behavior and forecast vintages.

Typical fields:

```text
forecast_created_at
forecast_target_date
interval_start
service_scope
model_id
forecast_volume
forecast_aht
lower_bound
upper_bound
feature_version
training_window_start
training_window_end
```

## Model families

### Statistical baselines — StatsForecast

Start every service with strong baselines. Depending on history and seasonality these may include seasonal naive, ETS, ARIMA-family or other statistical models.

A complex model must beat the baseline on held-out rolling windows before being selected.

### Feature models — MLForecast + XGBoost

Useful features can include:

- interval-of-day;
- weekday;
- week/month seasonality;
- lags and rolling statistics;
- holidays;
- known campaigns/events;
- product/client/market indicators;
- external variables where governed and available.

Features are versioned. A forecast must be reproducible from its model/feature metadata.

## Validation

Use rolling-origin/time-series cross-validation, never random train/test splitting for interval forecasts.

Track multiple metrics:

```text
Bias
WAPE
MAE
RMSE
MAPE where denominator behavior is acceptable
interval/service-target weighted error where useful
```

Model selection may differ by service and horizon.

## Hierarchical reconciliation

WFM structures are naturally hierarchical:

```text
market
  LOB
    service
      queue
```

Independent forecasts can disagree across levels. `HierarchicalForecast` is used to reconcile them so totals remain coherent.

## Forecast intelligence

The UI should expose more than a single accuracy percentage.

Examples:

- chronic Monday morning under-forecast;
- interval-specific AHT bias;
- model drift;
- service-level bias heatmap;
- forecast-vintage changes;
- hierarchy reconciliation adjustments;
- repeated event/holiday miss patterns.

## Staffing handoff

Forecast output feeds the staffing requirement engine:

```text
volume forecast
      +
AHT forecast
      |
      v
workload
      |
service objective / queueing model
      |
productive FTE requirement
      |
shrinkage
      |
scheduled FTE requirement
```

The staffing layer must retain which forecast version it consumed.
