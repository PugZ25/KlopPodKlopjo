# Lyme CatBoost challenger

## Purpose

Phase 13 tests whether a single conservatively configured CatBoost count model
improves out-of-time Lyme forecasts over epidemiological baselines and a
matched weather-aware statistical reference. CatBoost remains a challenger;
the experiment does not promote a model automatically.

## Matched reference

The reference is a weather-aware extension of Phase 9 S3:

```text
seasonality
+ municipality fixed effects
+ past four-week Lyme incidence
+ 21 lagged ERA5-Land weather features
+ fixed previous-year population exposure
```

The reference and CatBoost use the same target, rows, folds, population
selection, weather windows, training-fold weather scaler, and validation
observations. Early 2016 rows lacking four complete weather weeks are excluded
from both fits. All Phase 6 validation rows remain present.

Static municipality area is not included in the matched pair. With a complete
set of municipality fixed effects, a time-invariant area value is exactly
collinear in the statistical design. Including it only in CatBoost would break
the equal-information comparison.

## Feature availability

Both models receive:

- `municipality_code`;
- annual sine and cosine terms derived from `issue_week`;
- past Lyme incidence calculated from exactly `t−4..t−1`, using the same
  conservatively selected population as the model exposure;
- for each of the seven verified weekly ERA5-Land variables, lag 1, lag 2, and
  the previous-four-completed-week aggregation.

This gives 25 CatBoost columns: municipality identity plus 24 numeric columns,
including 21 weather columns. Weather is standardized with mean and population
standard deviation fitted on each training fold only. The identical scaled
numeric values enter the reference GLM and CatBoost.

No current-week or future cases or weather are used. Weather ends before
`issue_week`; no weather is created after the verified ERA5-Land cutoff.

## Population exposure

Both models use:

```text
log(population / 100000)
```

with coefficient fixed at one. Population is not an ordinary feature. The same
previous-year-or-latest-earlier population value is also the denominator of
past incidence.

CatBoost receives the offset through `Pool.baseline`. The matched statistical
reference uses the same exposure in its Poisson GLM.

## CatBoost configuration

One prespecified configuration is fitted: Poisson loss, 200 trees, depth 6,
learning rate 0.05, L2 leaf regularization 3, random seed 0, and one CPU thread.
There is no search, early stopping, validation-driven iteration choice, or
reuse of old hyperparameters.

Municipality has 212 categories and is one-hot encoded under
`one_hot_max_size=255`. Validation municipalities must already occur in
training. Target-derived categorical statistics are not allowed. Validation
labels are never passed to `fit` or prediction pools.

## Development result

Across the eight 2017–2024 rolling-origin validation folds:

| Model | MAE | RMSE | Mean Poisson deviance |
|---|---:|---:|---:|
| Matched weather-aware S3 reference | 1.3202 | 3.2649 | 1.7216 |
| CatBoost weather-aware challenger | 1.1826 | 2.7999 | 1.5160 |

Relative to the matched reference, CatBoost improved pooled MAE by 10.4%, RMSE
by 14.2%, and Poisson deviance by 11.9%. MAE and RMSE improved in 6/8 folds;
Poisson deviance improved in 7/8. The challenger deteriorated on MAE and RMSE
in 2017 and 2018, and on Poisson deviance in 2018. Because no numeric
materiality threshold was prespecified and improvement is not uniform, the
result supports CatBoost as a strong challenger but does not promote it.

These are development results, not 2025 lockbox results.

## Reproduction

```bash
./.venv/bin/python -B -m model_v3.models.catboost_challenger \
  --config model_v3/config/lyme_catboost_challenger.json
```

Outputs under `model_v3/outputs/catboost_challenger/` include predictions for
both matched models, fold and aggregate metrics, fold differences, stability,
reference coefficients, CatBoost feature importance, fit diagnostics, the
realized configuration, and a machine-readable quality summary.

Predictions are expected municipality-level reported Lyme case counts for the
next four weeks. They are not classifications, personal risk, or
low/medium/high categories. The 2025 lockbox is not accessed or evaluated.
