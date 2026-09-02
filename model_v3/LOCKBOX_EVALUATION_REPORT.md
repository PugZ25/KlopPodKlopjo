# Final 2025 Lyme lockbox evaluation

- **Evaluation status:** COMPLETE — one-time lockbox opened
- **Lockbox:** calendar year 2025
- **Final model:** `catboost_poisson_s3_weather_offset`
- **Eligible issue weeks:** 47 (2025-01-06 through 2025-11-24)
- **Observed 2025 calendar weeks:** 51 (through 2025-12-22)
- **Boundary-purged issue weeks with incomplete future horizon:** 4
- **Municipalities:** 212 fixed analytical zones
- **Predictions per system:** 9964
- **Protected weekly-case SHA-256:** `e85085beb9314b7866781d0a8b77e5afe58812280de2e8503680576bd65daf1d`

The frozen development design was applied without tuning, feature changes, target changes, threshold changes, calibration, or model reselection. Results below are descriptive evaluation evidence; they do not authorize post-lockbox model selection.

## DEVELOPMENT PERFORMANCE

Development values are the frozen rolling-origin results from 2017–2024 and are shown separately from the lockbox.

| System | N | MAE | RMSE | Mean Poisson deviance | Deviance status |
|---|---:|---:|---:|---:|---|
| CatBoost Poisson challenger with matched S3 and lagged ERA5-Land information | 81832 | 1.182640 | 2.799903 | 1.515964 | valid |
| S3 seasonality, municipality fixed effects, past incidence and lagged ERA5-Land weather with population exposure | 81832 | 1.320194 | 3.264934 | 1.721608 | valid |
| Municipality and seasonal historical count expectation | 81832 | 1.335796 | 3.187324 | N/A | invalid_zero_prediction_positive_observation_present |

## LOCKBOX PERFORMANCE

| System | N | MAE | RMSE | Mean Poisson deviance | Deviance status |
|---|---:|---:|---:|---:|---|
| Frozen CatBoost Poisson final model | 9964 | 1.168779 | 2.162938 | 1.538509 | valid |
| Matched S3 weather Poisson GLM | 9964 | 1.218328 | 2.349835 | 1.668909 | valid |
| Municipality and seasonal historical expectation | 9964 | 1.204113 | 2.118063 | N/A | invalid_zero_prediction_positive_observation_present |

### Development-to-lockbox change for the frozen final model

- MAE: 1.182640 → 1.168779
- RMSE: 2.799903 → 2.162938
- Mean Poisson deviance: 1.515964 → 1.538509

These changes are reported without modifying or replacing the frozen model.

## Calibration diagnostics

These are diagnostics only. No recalibration was fitted or applied.

| System | Observed total | Predicted total | Observed mean | Predicted mean | Mean error (prediction − observation) | O/P ratio |
|---|---:|---:|---:|---:|---:|---:|
| Frozen CatBoost Poisson final model | 19467.000000 | 16831.536408 | 1.953733 | 1.689235 | -0.264499 | 1.156579 |
| Matched S3 weather Poisson GLM | 19467.000000 | 16144.069514 | 1.953733 | 1.620240 | -0.333494 | 1.205830 |
| Municipality and seasonal historical expectation | 19467.000000 | 17524.777778 | 1.953733 | 1.758809 | -0.194924 | 1.110827 |

Ten deterministic equal-count reliability groups are saved in `model_v3/outputs/lockbox_2025/lyme_lockbox_calibration_groups.csv`.

## Municipality-level error distribution

The table below summarizes the frozen final model's MAE across 212 municipalities. Full per-municipality results for all systems are saved separately.

| Minimum | P25 | Median | P75 | P90 | Maximum |
|---:|---:|---:|---:|---:|---:|
| 0.037109 | 0.543931 | 0.899861 | 1.461719 | 2.171617 | 9.963946 |

Highest municipality-level MAE values:

| Municipality | Code | N weeks | MAE | Mean error | Observed total | Predicted total |
|---|---|---:|---:|---:|---:|---:|
| Ljubljana | 061 | 47 | 9.963946 | -5.500987 | 2299.000000 | 2040.453603 |
| Novo mesto | 085 | 47 | 5.220977 | -2.520133 | 425.000000 | 306.553733 |
| Maribor | 070 | 47 | 5.033400 | 0.625490 | 435.000000 | 464.398040 |
| Domžale | 023 | 47 | 4.121391 | -2.190006 | 379.000000 | 276.069707 |
| Ajdovščina | 001 | 47 | 3.403299 | -0.045132 | 318.000000 | 315.878815 |
| Radovljica | 102 | 47 | 3.322735 | -0.788997 | 446.000000 | 408.917162 |
| Slovenj Gradec | 112 | 47 | 3.247433 | -1.460136 | 209.000000 | 140.373601 |
| Kranj | 052 | 47 | 2.984155 | -0.558594 | 493.000000 | 466.746103 |
| Nova Gorica | 084 | 47 | 2.981485 | -1.043702 | 464.000000 | 414.946022 |
| Jesenice | 041 | 47 | 2.966290 | -0.215840 | 275.000000 | 264.855513 |

## Temporal error distribution

The table below summarizes municipality-level MAE across the 47 eligible issue weeks for the frozen final model.

| Minimum | P25 | Median | P75 | P90 | Maximum |
|---:|---:|---:|---:|---:|---:|
| 0.348099 | 0.740295 | 1.011831 | 1.718510 | 1.988800 | 2.217944 |

Highest issue-week MAE values:

| Issue week | ISO week | MAE | Mean error | Observed total | Predicted total |
|---|---:|---:|---:|---:|---:|
| 2025-06-30 | 27 | 2.217944 | -1.544715 | 847.000000 | 519.520496 |
| 2025-07-21 | 30 | 2.087683 | -1.441277 | 737.000000 | 431.449375 |
| 2025-07-07 | 28 | 2.037375 | -1.477612 | 783.000000 | 469.746260 |
| 2025-06-23 | 26 | 2.007219 | -0.566470 | 893.000000 | 772.908300 |
| 2025-06-16 | 25 | 2.003164 | -0.220013 | 860.000000 | 813.357275 |
| 2025-07-14 | 29 | 1.979223 | -1.271680 | 775.000000 | 505.403816 |
| 2025-06-09 | 24 | 1.950954 | 0.045292 | 850.000000 | 859.601818 |
| 2025-07-28 | 31 | 1.915204 | -1.301858 | 707.000000 | 431.006126 |
| 2025-05-26 | 22 | 1.914939 | 0.399785 | 764.000000 | 848.754456 |
| 2025-06-02 | 23 | 1.908349 | 0.277808 | 820.000000 | 878.895240 |

## Interval metrics

Not available. The frozen final CatBoost system did not define predictive intervals, and no interval method was added after opening the lockbox.

## Lockbox integrity

- Target is exactly `t+1..t+4`; issue week `t` is excluded.
- Every evaluated target window is fully contained in 2025.
- Training targets end before 2025.
- Population is from the most recent strictly earlier year.
- Case and weather features end at `t-1` or earlier.
- ERA5-Land uses the same final product, seven variables, units, weekly aggregation, and frozen polygon-overlay weights as development.
- No thresholding, classification, calibration fitting, or model reselection was performed.
- The run receipt prevents a second evaluation execution.
