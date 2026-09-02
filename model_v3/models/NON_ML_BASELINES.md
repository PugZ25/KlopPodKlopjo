# Lyme non-ML baselines

## Scope

This stage evaluates five simple count-forecast baselines on the Phase 6 rolling-origin development folds. It uses no machine-learning library, weather data, environmental data, classification metric, calibration, threshold or 2025 lockbox value.

Reproduce from the repository root:

```bash
./.venv/bin/python -B -m model_v3.models.non_ml_baselines \
  --config model_v3/config/lyme_non_ml_baselines.json
```

Inputs:

- canonical weekly Lyme cases;
- canonical calendar ISO week metadata;
- the Phase 5 four-week target path declared by the Phase 6 validation configuration;
- Phase 6 rolling-origin fold definitions and manifest.

Outputs are written beneath `model_v3/outputs/baselines/`.

## Baseline definitions and availability

All forecasts estimate `target_lyme_cases_next_4w`, a municipality-specific count for exactly `t+1..t+4`.

### A. Overall historical count expectation

The prediction is the arithmetic mean of target counts in the fold training split. Every fitted target has `target_window_end < validation_start`. This is a count expectation and does not use population as an arbitrary feature.

### B. Municipality historical count expectation

The prediction is the arithmetic mean of training targets for the validation municipality. If a municipality has no training row, the explicit fallback is baseline A. No information from validation targets is used.

### C. Seasonal historical count expectation

The prediction is the arithmetic mean of training targets sharing the validation issue week's canonical ISO week number. If that ISO week was not observed in training, the fallback is baseline A.

### D. Municipality and seasonal historical count expectation

The prediction is the arithmetic mean for the training `municipality_code × ISO week` cell. The fallback order is municipality expectation, seasonal expectation, then overall expectation. Every component uses the fold training split only.

### E. Previous four completed weeks persistence

For municipality `m` at issue week `t`:

```text
prediction(m, t)
  = lyme_cases(m, t-4)
  + lyme_cases(m, t-3)
  + lyme_cases(m, t-2)
  + lyme_cases(m, t-1)
```

The latest input is `t-1`. The current issue week `t`, centered windows and all future weeks are excluded. Later validation predictions may use earlier observed validation-period case weeks because those weeks are complete by that later issue time. If any required prior municipality-week is absent, the persistence prediction is explicitly missing rather than imputed as zero.

The canonical data do not define reporting-delay semantics beyond their weekly dates. This baseline therefore implements the user-specified completed-week availability rule; any additional real-world reporting delay remains `UNKNOWN`.

## Metrics

- **MAE:** mean absolute count error. It remains directly interpretable in reported cases.
- **RMSE:** root mean squared count error. It is included without a new dependency and gives greater weight to large count errors.
- **Mean Poisson deviance:** reported only when every evaluated pair is mathematically valid. For prediction `mu = 0` and observation `y = 0`, the limiting contribution is zero. A pair with `mu = 0` and `y > 0` is invalid; no epsilon or invented smoothing constant is introduced.

Classification AUC is not calculated because the target is a count.

## Output contracts

- `lyme_non_ml_fold_predictions.csv` contains every validation prediction, its actual count, provenance/fallback, availability dates and row-level Poisson validity.
- `lyme_non_ml_fold_metrics.csv` contains one record per fold and baseline.
- `lyme_non_ml_aggregate_metrics.csv` contains pooled development-fold metrics and unweighted mean fold MAE/RMSE for each baseline.
- `lyme_non_ml_baseline_configuration.json` records the realized fold boundaries, definitions, availability rules, metrics and source hashes.
- `lyme_non_ml_quality_summary.json` records hashes, row counts and leakage checks.

Aggregate development metrics are not a model-selection decision and contain no lockbox performance.
