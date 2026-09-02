# Combined reported Lyme + KME regional model

## Interpretation

The project label **tick-borne diseases** in this experiment means one composite surveillance count: reported Lyme disease cases plus reported KME/TBE cases. It does not cover every tick-borne disease, does not estimate personal risk, and should not replace disease-specific forecasts.

The target is dominated by Lyme: KME contributes 2.24% of summed complete overlapping target counts. This model is therefore mainly a combined service-demand/surveillance forecast, not evidence that Lyme and KME share one biological process.

## Design

- Analysis unit: statistical region × issue week.
- Target: reported Lyme + KME cases in exactly t+1..t+8; issue week excluded.
- Population: mandatory log exposure offset and incidence denominator.
- Features evaluated: annual seasonality, region, previous eight completed weeks, and four lagged ERA5-Land summaries.
- Weather aggregation: the existing verified municipality polygon-overlay weekly data, then municipality-area-weighted aggregation to region.
- Validation: expanding rolling origin with target-window containment and an eight-week boundary purge.
- Feature-complete rows: 5952; folds: 8 (2018–2025).

## Development results

| Candidate | Pooled MAE | RMSE | Poisson deviance |
|---|---:|---:|---:|
| `baseline_region_historical_rate` | 48.296816 | 81.041646 | 51.358917 |
| `baseline_persistence_8w` | 50.337583 | 90.964383 | INVALID |
| `glm_seasonal_region_offset` | 35.343934 | 59.574161 | 24.076482 |
| `glm_past_combined_offset` | 33.798324 | 59.149941 | 25.669027 |
| `glm_weather_only_offset` | 49.347263 | 82.844845 | 55.275579 |
| `glm_seasonal_region_weather_offset` | 36.955094 | 63.916593 | 27.137291 |
| `glm_combined_weather_offset` | 35.756190 | 63.304863 | 27.980770 |
| `catboost_combined_weather_offset` | 27.799611 | 52.532209 | 16.880995 |

Selected candidate: **`glm_past_combined_offset`**.

CatBoost is promoted only when it beats the best non-ML model on pooled MAE and in every validation fold. No extensive hyperparameter search, classification target, thresholds, or risk categories were used.

These are development results through 2025. ISO year 2026 remains unavailable in canonical outcomes and is not evaluated here.
