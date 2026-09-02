# KME model-selection freeze

- **Freeze status:** FROZEN
- **Freeze date:** 2026-08-30
- **Frozen system ID:** `kme_region_eight_week_v1`
- **Repository-controlled lockbox:** ISO week-numbering year 2026
- **Lockbox status:** RESERVED_NOT_ACCESSED_BY_THIS_PIPELINE

This document freezes the KME development decision before any 2026 KME outcome is loaded by this pipeline. Because the seal date falls during 2026, this is a retrospective/ongoing holdout rather than a fully prospective forecast experiment. External human access to 2026 outcomes is UNKNOWN and cannot be audited from the repository. The 2015–2025 outcomes are development evidence, not an untouched lockbox. The protected period follows ISO week-numbering year 2026, and every evaluated t+1..t+8 target week must remain inside that ISO year. After 2026 outcomes are accessed by the pipeline, changing this specification requires formally abandoning 2026 and declaring a later untouched lockbox.

## Frozen prediction task

- Analysis unit: **statistical region × issue week**.
- Target: reported regional KME cases in exactly **t+1 through t+8**.
- The issue week is excluded.
- `target_window_start = issue_week + 1 week`; `target_window_end = issue_week + 8 weeks`.
- All eight future weeks must exist; incomplete targets are excluded, never zero-filled.
- Output: a non-negative expected reported regional count, not personal risk or a classification probability.

The verified 2022 SURS municipality-to-statistical-region mapping is used by municipality code as a fixed analytical geography for every year. This is an analytical convention, not a historical-boundary reconstruction.

## Frozen selected model

Selected model: **`glm_seasonal_region_offset`**.

`log(E[target_kme_cases_next_8w]) = log(region_population/100000) + intercept + annual_sin + annual_cos + statistical_region_fixed_effect`

- Poisson GLM with log link, implemented by `statsmodels.GLM`.
- Population is the offset `log(region_population/100000)`, never an ordinary feature.
- Region uses deterministic treatment-coded fixed effects.
- Seasonality is one annual sine/cosine harmonic derived only from `issue_week`.
- Predictions are expected counts obtained from the fitted log-link model.
- Parameters: `maxiter=100`, `tol=1e-08`; other behavior is from frozen `statsmodels==0.14.6`.
- Calibration: none. Predictive intervals: not implemented.

## Weather and other evaluated information

Weather remains part of the documented KME development experiment, but it is **not** in the frozen selected model. The earlier common-support comparison evaluated a weather-only GLM, weather-adjusted GLMs, and a compact-weather CatBoost challenger. Weather-only and weather-adjusted GLMs worsened pooled MAE. CatBoost improved pooled MAE by only about 1.7% and beat the selected GLM in 4/8 folds, failing the predeclared stability rule.

The frozen selected-model finalization therefore does not require weather and does not reject a valid row because an unused weather value is absent. This is a preprocessing correction, not a formula change. The prior weather experiment and its predictions remain frozen evidence and are not discarded.

Past eight-week KME counts are retained only for the persistence baseline and are not supplied to the selected GLM. Municipality area remains only an aggregation weight in the weather experiment; it is not a selected predictor. Land cover, elevation, long-term trend, thresholds, risk categories, and generated predictions remain excluded.

## Frozen population and missing-value rules

- For each mapped municipality, use the latest present population year strictly before the issue calendar year; sum those values to the region.
- Exclude a regional row if any mapped municipality lacks a safe earlier population value.
- NIJZ blank case cells retain the previously verified source-specific zero rule.
- Missing target weeks, missing past weeks required by the persistence baseline, unmatched codes, duplicates, or negative counts are rejected or explicitly excluded; none becomes an invented zero.

## Frozen validation

- Expanding rolling-origin folds validate ISO years 2017–2025.
- Training requires `target_window_end < validation_start`.
- Validation target windows must remain entirely inside the validation ISO year.
- An explicit eight-week target embargo purges boundary-crossing training rows.
- Primary metric: pooled MAE. Secondary metrics: RMSE and mean Poisson deviance where mathematically valid.

Finalized feature-support rows: **6651**. Explicit exclusions: `{"incomplete_past_case_window_for_persistence_baseline": 88, "missing_safe_population": 53}`. Validation predictions per system: **4764**.

## Finalized development evidence

| System | Pooled MAE | RMSE | Poisson deviance |
|---|---:|---:|---:|
| `baseline_region_historical_rate` | 1.516110 | 2.765246 | 2.587539 |
| `baseline_persistence_8w` | 1.793871 | 3.553123 | INVALID |
| `glm_seasonal_region_offset` | 1.174228 | 2.191803 | 1.616393 |

The selected seasonal regional GLM remains materially better than both simple baselines. All 9 frozen GLM fits reported convergence and no recorded warnings. These are development results; they are not 2026 lockbox performance.

## Frozen 2026 lockbox procedure

1. Treat calendar year 2026 as protected. Loaders must reject or skip 2026 KME outcome rows before numeric parsing during feature preparation and prediction.
2. Build only the frozen region, issue-date, safe population and seasonality inputs.
3. Fit one final frozen GLM on eligible 2015–2025 development rows, preserving the complete-target, safe-population and persistence-comparator support rules recorded here.
4. Generate and checksum 2026 predictions before parsing 2026 KME outcomes.
5. Open complete 2026 targets once, restricted to issue weeks and t+1..t+8 target windows fully contained in ISO week-numbering year 2026.
6. Report the selected model and both declared baselines. Do not tune or substitute another model after observing the result.

## Reproducibility identifiers

Configuration: `model_v3/config/kme_model_freeze.json` — `ac68961cbc9463805b35d2dcde86b47fa789814f8c302895d3123646bc83821b`

Freeze code: `model_v3/models/kme_model_freeze.py` — `38393d2373541654a9c236b0edfc222d089211a9f0e9e2d1f29a260e4a2ac7b3`

Git HEAD at freeze: `274dafa952750bd2e110bfa635735756a3ad24d0`. The worktree was not clean, so file hashes—not the commit alone—are authoritative.

- `model_v3/outputs/targets/kme_eight_week_target.csv` — `9b0040e61f54a66f78e3e7c4b6904dff91a3be7e55ead917598b4eefde605396`
- `model_v3/outputs/canonical/weekly_cases.csv` — `e85085beb9314b7866781d0a8b77e5afe58812280de2e8503680576bd65daf1d`
- `model_v3/outputs/canonical/population.csv` — `8834ce82435e7b6a45a1504538e489bec8877568d43bf07a806e23cb499a38ad`
- `model_v3/outputs/canonical/statistical_region.csv` — `6944802708d34933eeb8b50d998647cbc29c3a16d451d65806d57eb582a80bd4`
- `model_v3/outputs/canonical/municipality_statistical_region.csv` — `2b16e6126d87505f2480f5d2c13f7e055737b1118b84dfa16ff48d09af4f4cde`
- `model_v3/outputs/kme_region_model/kme_model_selection.json` — `c24fbef80b56793cd0c2e9d93de18b9495a32001d5900a3e0a4d6d2f7672cfa0`
- `model_v3/outputs/kme_region_model/kme_aggregate_metrics.csv` — `9da69cf892e86b5a6410c7cca2b94606a17c8af6b7cc4ef2cd8d158a5a13f98f`
- `model_v3/config/kme_region_model.json` — `5c9b73ec8b08bd1026c5730b88b1176206e105784d2becdf3de45cd8ceaad686`
- `model_v3/models/kme_region_model.py` — `5a0c3f666994e70c966d28812a37e370e2d6ca15764a09292eba54937348e4ae`
- `model_v3/config/kme_eight_week_target.json` — `2619180aa576179d23838d26d9971b0cc0486bfbdd5f3c9eb99de571693b0e77`
- `model_v3/panel/kme_eight_week_target.py` — `5b66982154eb13ee0dafb1dbd65559876507e77dea322c27cf7ea6062557314a`
