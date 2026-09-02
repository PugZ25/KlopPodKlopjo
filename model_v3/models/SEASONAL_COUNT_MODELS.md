# Lyme seasonal count models

## Scope and reproduction

This Phase 9 stage fits three Poisson generalized linear models to the Phase 5
four-week Lyme count target using exactly the Phase 6 rolling-origin development
folds. It reads the Phase 8 development metrics for comparison. It does not use
weather, environmental data, CatBoost, classification metrics, thresholds,
calibration or 2025 performance.

From the repository root:

```bash
./.venv/bin/python -B -m model_v3.models.seasonal_count_models \
  --config model_v3/config/lyme_seasonal_count_models.json
```

Inputs and outputs are declared in the configuration. Outputs are written under
`model_v3/outputs/seasonal_count_models/`.

## Statistical implementation

The implementation is `statsmodels` Poisson GLM with a log link and an explicit
population exposure. For row `i`:

```text
Y_i ~ Poisson(mu_i)
log(mu_i) = log(population_i) + X_i beta
```

`statsmodels.GLM(..., exposure=population)` adds `log(population)` to the linear
predictor with its coefficient fixed to one. Population is not included as an
ordinary design-matrix feature. Because every outcome has the same four-week
horizon, the intercept represents a four-week count rate per unit population.

The population value is selected with a conservative availability safeguard.
For an issue week in calendar year `Y`, the implementation uses the latest
present canonical SURS `Population - Total - 1 January` observation whose year
is strictly earlier than `Y`. It therefore prefers `Y-1`; if that value is
missing, it falls back to the latest present earlier year. Values from `Y` and
future years are never eligible. At a year-edge issue week, `Y` is the date's
calendar year, not its ISO week-numbering year.

Historical source data do not provide exact population publication timestamps.
This rule is a prespecified conservative leakage-prevention proxy, not a claim
about the actual SURS publication date or delay. It relies on the user-approved
modelling judgment that municipality population generally changes slowly from
year to year. The selected year and lag are written with each prediction, and
the same selected value is used in training, validation, the model exposure and
the S3 incidence denominator.

Fitting uses unregularized iteratively reweighted least squares with the pinned
library defaults made explicit in configuration: `maxiter=100`, `tol=1e-8` and
non-robust covariance. Fold-level diagnostics record convergence, iteration
count, warnings, design rank, parameter count, exposure range and training
target cutoff. No convergence result is silently replaced or smoothed.

## Design matrices

Seasonality uses one annual harmonic derived only from the issue date:

```text
phase = 2*pi*(zero-based day of year)/(days in issue year)
seasonal_sin_annual = sin(phase)
seasonal_cos_annual = cos(phase)
```

This representation is continuous across ordinary, leap-year and ISO-week-53
dates. It requires no future observation. No long-term trend is included: no
trend form was prespecified, and development-fold performance is not used to
select one in this phase.

The realized models are:

```text
S1: target ~ 1 + seasonal_sin_annual + seasonal_cos_annual
             + offset(log(population))

S2: S1 + municipality treatment-coded fixed effects

S3: S2 + past_4w_lyme_incidence_per_100000
```

S2 and S3 use a deterministic treatment-coded municipality structure. In each
fold, the lexicographically first training municipality code is the reference;
the remaining training municipalities receive indicator columns. An unseen
validation municipality would receive an explicit missing prediction rather
than an invented effect.

For S3 at municipality `m` and issue week `t`:

```text
past_4w_lyme_cases(m, t)
  = lyme_cases(m, t-4) + ... + lyme_cases(m, t-1)

past_4w_lyme_incidence_per_100000(m, t)
  = past_4w_lyme_cases(m, t) / selected_prior_population(m, t) * 100000
```

The latest case input is `t-1`. The current week, centered windows and future
weeks are excluded. A missing required past municipality-week makes the S3
feature and corresponding prediction explicitly missing; it is not converted
to zero.

## Prediction and uncertainty

Point predictions are expected four-week case counts generated with the
validation design matrix and that row's explicit population exposure.

Two interval types are saved:

- a 95% model-based confidence interval for the expected mean from the fitted
  GLM covariance;
- a central 95% conditional Poisson count interval using the fitted mean.

The conditional count interval includes Poisson outcome variation but not
coefficient uncertainty. It is therefore not a full parameter-uncertainty
predictive interval. This limitation is recorded in configuration and quality
outputs. If exponentiating a Wald bound produces a non-finite expected-mean
confidence limit, only those mean bounds are written as missing with status
`unavailable_nonfinite_wald_bound`; the finite point prediction and conditional
Poisson count interval are retained. No smoothing constant is introduced.

## Evaluation and outputs

MAE, RMSE and mean Poisson deviance use the same definitions as Phase 8. Every
training row satisfies `target_window_end < validation_start`; every validation
target is contained within its validation period. The combined development
comparison preserves the declared order of the five Phase 8 baselines followed
by S1, S2 and S3. It is not a model-selection decision.

| Output | Purpose |
|---|---|
| `lyme_seasonal_count_fold_predictions.csv` | Row-level development predictions, exposures, availability dates, intervals and Poisson contributions. |
| `lyme_seasonal_count_fold_metrics.csv` | Fold-level S1-S3 metrics. |
| `lyme_seasonal_count_aggregate_metrics.csv` | Pooled and mean-fold S1-S3 metrics. |
| `lyme_development_model_comparison.csv` | Phase 8 baselines and Phase 9 models on the same development folds. |
| `lyme_seasonal_count_fit_diagnostics.csv` | Formula, design rank, convergence, warnings and exposure diagnostics. |
| `lyme_seasonal_count_coefficients.csv` | Fold-level coefficients and standard errors; the fixed population offset is documented separately and is not estimated. |
| `lyme_seasonal_count_model_configuration.json` | Realized policy, formulas, versions, fold manifest and source hashes. |
| `lyme_seasonal_count_quality_summary.json` | Machine-readable row counts and leakage, offset, convergence and lockbox checks. |

No 2025 target, case value, population value or performance metric is used by
this stage.
