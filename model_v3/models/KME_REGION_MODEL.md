# KME statistical-region forecasting system

## Outcome

The implemented KME system uses **statistical region × issue week** and predicts the reported KME count in exactly **t+1 through t+8**. The issue week is excluded. This choice follows the verified SURS regional feasibility analysis: region × 8-week windows are materially less sparse than municipality windows while retaining more temporal blocks than a 12-week horizon.

This is rolling-origin development evidence, not untouched lockbox performance. KME observations from 2015-2025 already informed design, so a future KME lockbox must begin after this period.

## Information available at issue time

- Population: sum of the latest present municipality values strictly before the issue calendar year; used as `log(population/100000)` offset and as the past-incidence denominator.
- Past epidemiology: regional KME cases in exactly `t-8..t-1`.
- Seasonality: one annual sine/cosine harmonic derived from issue date.
- Weather: final ERA5-Land 0001, using complete weeks `t-4..t-1` only. Municipality weekly inputs come from grid-cell polygon-intersection overlay weights, not point or centroid sampling; those municipality means are then area-weighted to regions.
- Compact weather features: 4-week mean air temperature, 4-week precipitation sum, 4-week mean shallow-soil temperature, and 4-week mean shallow-soil moisture.

Current/future cases and weather are rejected. Weather-missing rows are excluded from every comparator, preserving common support. Municipality/region area is not an ordinary predictor because it is time-invariant and redundant with region identity; it is used only for weather aggregation.

## Candidate specifications

- Regional historical rate: training-only regional target count divided by population exposure, rescaled to each validation exposure.
- Persistence: regional count from exactly `t-8..t-1`.
- Seasonal regional GLM: `log(E[Y]) = log(population/100000) + intercept + annual_sin + annual_cos + region_effect`.
- Past-incidence GLM: seasonal regional GLM plus training-standardized prior 8-week incidence.
- Weather-only GLM: `log(E[Y]) = log(population/100000) + intercept + four_training_standardized_weather_summaries`; it deliberately excludes seasonality, region, and past cases.
- Weather-adjusted GLMs: the seasonal regional GLM with weather, and then with both weather and past incidence.
- CatBoost challenger: Poisson loss with `log(population/100000)` as the input baseline and the same region, seasonality, past-incidence, and compact weather information. Its fixed conservative parameters are in `model_v3/config/kme_region_model.json`; no search is run.

The GLMs use a log link and produce expected counts by exponentiating the fitted linear predictor plus offset. All 40 GLM fits and all 8 CatBoost fits completed with no recorded warning; the GLMs reported convergence. Predictive intervals are not implemented for this development experiment.

## Validation

8 expanding rolling-origin folds validate ISO years 2018-2025. Training target windows end strictly before validation starts. Validation target windows remain fully within their validation ISO year. The eight-week target boundary is explicitly purged.

Feature-complete panel rows: 5952. Validation predictions per system: 4236.

## Results

| Candidate | Type | Pooled MAE | RMSE | Poisson deviance | Folds better than persistence |
|---|---|---:|---:|---:|---:|
| `catboost_compact_weather_offset` | ml_challenger | 1.2076 | 2.2265 | 1.5718 | 7/8 |
| `glm_seasonal_region_offset` | statistical_model | 1.2289 | 2.2425 | 1.6829 | 7/8 |
| `glm_past_kme_offset` | statistical_model | 1.2328 | 2.2784 | 1.7351 | 7/8 |
| `glm_seasonal_region_weather_offset` | statistical_model | 1.2618 | 2.3284 | 1.7787 | 7/8 |
| `glm_compact_weather_offset` | statistical_model | 1.2665 | 2.3599 | 1.8447 | 7/8 |
| `baseline_region_historical_rate` | baseline | 1.5827 | 2.8190 | INVALID | 6/8 |
| `glm_weather_only_offset` | statistical_model | 1.6232 | 2.8807 | 2.9081 | 5/8 |
| `baseline_persistence_8w` | baseline | 1.8296 | 3.6613 | INVALID | 0/8 |

Selected development system: **`glm_seasonal_region_offset`**.

Selection rule: CatBoost requires lower pooled MAE and lower MAE in every validation fold; otherwise select the lowest pooled-MAE non-ML system. CatBoost promoted: **false**.

The explicit weather-only model has MAE 1.6232. Adding weather to the seasonal regional model changes MAE from 1.2289 to 1.2618; adding both past incidence and weather gives 1.2665. These are deteriorations, so weather remains a tested ablation rather than a forced component of the selected sparse-data model. CatBoost with the full compact feature set improves the seasonal regional reference in 4/8 folds, which is not stable enough for promotion under the pre-declared rule.

## Small-sample safeguards

- Region aggregation reduces municipality-level structural zeros without disaggregating predictions back to municipalities.
- The weather set is limited a priori to four summaries; correlated duplicate depths and fine lag variants are excluded.
- CatBoost uses one conservative fixed configuration and no hyperparameter search.
- CatBoost is not promoted for a small pooled improvement; it must also improve every validation fold over the best non-ML system.
- No low/medium/high categories, personal-risk language, classification probabilities, or arbitrary risk scores are created.

## Limitations

- The historical NIJZ source lacks observation-level publication/revision timestamps. Canonical confirmation-week values are used; past cases stop at `t-1` as a conservative modelling safeguard, not a verified NIJZ publication delay.
- Weather associations need not be causal and may partly reflect human outdoor activity.
- Overlapping eight-week targets make row-level errors dependent; rolling-year folds, not nominal row count, are the primary stability evidence.
- No untouched KME lockbox remains in 2015-2025.
- This system forecasts regional reported counts. Municipality forecasts or disaggregation are not implemented.
