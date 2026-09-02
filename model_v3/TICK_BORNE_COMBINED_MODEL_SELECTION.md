# Combined reported Lyme + KME model-selection freeze

## Frozen task

- Composite: reported Lyme disease cases + reported KME/TBE cases only; not every tick-borne disease.
- Analysis unit: statistical region × issue week.
- Target: exactly t+1..t+8, excluding issue week.
- Output: expected reported combined case count, not personal risk.

## Frozen selected model

Selected candidate: **`glm_past_combined_offset`**.

`log(E[target]) = log(region_population/100000) + intercept + annual_sin + annual_cos + statistical_region_fixed_effect + standardized_past_8w_combined_incidence`

Population is an explicit offset and incidence denominator. The past-case feature uses exactly the eight completed weeks t−8..t−1. Weather was evaluated but is not in the selected model. CatBoost had better pooled MAE but failed the predeclared every-fold stability rule, improving 7/8 folds, so it was not promoted after results were observed.

Final fit: 6651 rows, 15 parameters, converged=true, iterations=6, warnings=0.

Finalization support uses only inputs required by the selected formula. Weather remains in the development ablation but does not exclude final-fit rows. Selected-model exclusions: `{"incomplete_past_case_window": 88, "missing_safe_population": 53}`.

## Development evidence

| Candidate | Pooled MAE | RMSE | Poisson deviance |
|---|---:|---:|---:|
| `baseline_region_historical_rate` | 48.296816 | 81.041646 | 51.35891673117418 |
| `baseline_persistence_8w` | 50.337583 | 90.964383 | INVALID |
| `glm_seasonal_region_offset` | 35.343934 | 59.574161 | 24.076482337607853 |
| `glm_past_combined_offset` | 33.798324 | 59.149941 | 25.669026575372097 |
| `glm_weather_only_offset` | 49.347263 | 82.844845 | 55.275578609120544 |
| `glm_seasonal_region_weather_offset` | 36.955094 | 63.916593 | 27.137291032764914 |
| `glm_combined_weather_offset` | 35.756190 | 63.304863 | 27.98076980896173 |
| `catboost_combined_weather_offset` | 27.799611 | 52.532209 | 16.880995232274294 |

These metrics are rolling-origin development evidence through 2025. No 2026 outcome was used. The composite is strongly dominated by Lyme counts and must not be interpreted as a shared biological disease mechanism.

## Deployment rule

Predictions require the eight most recent completed regional combined case weeks. A prediction is unavailable when any required past week is unavailable; missing weeks are never zero-filled. The first ISO-2026 issue week can be generated from verified late-2025 observations. Later 2026 issues require sequential verified 2026 observations.
