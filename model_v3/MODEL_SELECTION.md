# Model selection freeze before the 2025 lockbox

- **Freeze status:** FROZEN
- **Freeze date:** 2026-08-14
- **Protected lockbox:** calendar year 2025
- **Lockbox status at freeze:** outcomes not accessed for evaluation; no 2025 target was materialized or scored

This document freezes the model-selection decisions made from the 2016–2024
development evidence. The selected model is the final **lockbox candidate**, not
yet a deployment-approved model. The 2025 lockbox may be used once, after the
required 2025 inputs have been prepared under the unchanged contracts below.

After the lockbox is opened, none of the target, features, preprocessing,
missing-value rules, model family, parameters, comparator, metrics, calibration,
or evaluation rules in this document may be changed in response to its results.
Changing any such decision requires formally abandoning 2025 as the lockbox and
declaring a new, later, untouched lockbox before further model selection.

## Frozen prediction task

| Item | Frozen definition | Reason |
|---|---|---|
| Analysis unit | `municipality_code × issue_week` | This is the prespecified Lyme analysis unit and preserves municipality-specific counts on an explicit weekly time axis. |
| Target | `target_lyme_cases_next_4w` | This is the prespecified primary Lyme count target. |
| Horizon | Sum of reported Lyme cases at exactly `t+1`, `t+2`, `t+3`, and `t+4` | Four weeks is the prespecified forecast horizon. The issue week `t` is excluded. |
| Target dates | `target_window_start = issue_week + 1 week`; `target_window_end = issue_week + 4 weeks` | Date arithmetic handles year and ISO-week boundaries without treating week numbers as a continuous counter. |
| Eligible target | All four future municipality-weeks must exist and have non-missing Lyme counts | A missing future week is unknown, not zero. Incomplete target windows are excluded from supervised fitting and evaluation. |
| Output | Non-negative expected four-week Lyme case count for a municipality | The task is count forecasting, not classification and not personal-risk estimation. |

KME is outside this model. The target is not incidence: incidence is used only
for the explicitly defined past-epidemiology predictor below. Population is an
exposure/offset in the count model.

## Frozen feature groups

All features are evaluated as of `issue_week`. No observed value from the issue
week or a later week may enter a predictor.

### Included

1. **Municipality identity**

   - `municipality_code` is a categorical predictor.
   - The same 212 verified GURS municipality polygons/codes are fixed analytical
     zones for every year. This is a modelling rule, not a reconstruction of
     historical municipal boundaries.

2. **Annual seasonality**

   - Sine and cosine terms are derived deterministically from `issue_week`.
   - They represent smooth annual timing without using case outcomes.

3. **Past Lyme incidence**

   - One backward-looking epidemiological predictor uses reported Lyme cases
     from exactly the previous four completed weeks, `t-4` through `t-1`.
   - Its denominator is the same safely lagged population value used for the
     model exposure.
   - The issue week and all future weeks are excluded.

4. **Lagged ERA5-Land weather**

   Seven verified variables are included:

   - 2 m temperature (`t2m`)
   - 2 m dewpoint temperature (`d2m`)
   - total precipitation (`tp`)
   - soil temperature layer 1 (`stl1`)
   - soil temperature layer 2 (`stl2`)
   - volumetric soil water layer 1 (`swvl1`)
   - volumetric soil water layer 2 (`swvl2`)

   Each variable contributes three backward-looking features: lag 1 completed
   week, lag 2 completed weeks, and the aggregate of the previous four completed
   weeks. Weekly and four-week aggregation is a mean for instantaneous variables
   and a sum for total precipitation. This gives 21 weather predictors.

   ERA5-Land weeks run from Monday 00:00 UTC through Sunday 23:00 UTC and must
   end before `issue_week`. The final ERA5-Land `expver=0001` product is used as
   the source of record. Weather after the verified source cutoff is never
   extrapolated, repeated, or synthesized.

5. **Population exposure**

   - Population enters as the offset/baseline `log(population / 100000)`.
   - It is not supplied again as an ordinary numeric predictor.
   - For an issue year, select the most recent known municipality population
     from a strictly earlier year. Prefer the immediately previous year when it
     exists; otherwise use the latest earlier year.
   - This conservative rule is applied identically to fitting, prediction, the
     statistical comparator, and the past-incidence denominator. It does not
     claim exact historical population publication timestamps.

### Excluded

- Municipality area is excluded. It was nearly neutral in the static-geography
  ablation and is exactly collinear with municipality fixed effects in the
  statistical comparator; giving it only to CatBoost would break the matched
  information comparison.
- Elevation and land-cover variables are excluded because they were not part of
  the verified final matched experiment.
- Current-week or future cases and weather are excluded.
- Generated model predictions are excluded as features.
- Classification labels, low/medium/high categories, and personal-risk outputs
  are excluded.

## Frozen model

The final lockbox candidate is
`catboost_poisson_s3_weather_offset`: a CatBoost count model with Poisson loss,
the feature groups above, and the log population exposure supplied as the
CatBoost `Pool` baseline.

The baseline is on the log-count scale. CatBoost learns corrections to that
initial approximation, and prediction uses the exponential prediction type to
return expected counts. Municipality is one-hot encoded: `one_hot_max_size=255`
is greater than the 212 verified municipality categories, so target-derived
categorical statistics are not used for this field.

### Frozen CatBoost parameters

| Parameter | Value |
|---|---:|
| `loss_function` | `Poisson` |
| `eval_metric` | `Poisson` |
| `prediction_type` | `Exponent` |
| `iterations` | `200` |
| `depth` | `6` |
| `learning_rate` | `0.05` |
| `l2_leaf_reg` | `3.0` |
| `random_seed` | `0` |
| `random_strength` | `1.0` |
| `one_hot_max_size` | `255` |
| `has_time` | `true` |
| `task_type` | `CPU` |
| `thread_count` | `1` |
| `allow_writing_files` | `false` |
| `verbose` | `false` |
| Early stopping | none |
| Hyperparameter search | none |
| Validation labels supplied to CatBoost | no |

Options not listed above remain the defaults of the frozen dependency
`catboost==1.2.10`. Changing the CatBoost version, an explicit parameter, or a
relevant library default is a model change.

The conservative settings were selected before the lockbox and were not tuned
extensively. `has_time=true`, deterministic row ordering, a fixed seed, and one
CPU thread reduce nondeterministic or order-dependent variation. Withholding
validation labels from the training library prevents fold validation outcomes
from affecting fitting, iteration selection, or stopping.

## Frozen baseline comparator

The primary model-selection comparator is
`model_s3_weather_offset_matched`, a Poisson GLM containing:

- the same safely lagged population offset;
- the same seasonality terms;
- municipality fixed effects;
- the same past four-week Lyme incidence predictor;
- the same 21 lagged ERA5-Land weather predictors; and
- exactly the same complete rows as the CatBoost candidate.

This is the primary comparator because it changes model form while holding the
available information and evaluation sample constant.

Phase 8 Baseline D (municipality plus seasonal historical expectation) remains
the secondary simple epidemiological benchmark. It is reported for MAE and RMSE,
but not used as the primary Poisson-deviance comparator because it produced zero
predictions for some positive observations, making mean Poisson deviance
mathematically invalid without adding an arbitrary floor.

## Frozen preprocessing

1. Load development rows only; reject or skip lockbox rows before parsing
   outcome numeric values.
2. Sort deterministically by `issue_week`, then `municipality_code`.
3. Require a complete target window and the explicit target-training eligibility
   status.
4. Join municipalities by `municipality_code`, never by municipality name when
   a code is available.
5. Select population independently within municipality using the strictly
   previous-year rule above.
6. Aggregate ERA5-Land grid-cell polygons to the fixed municipality polygons by
   area-weighted polygon overlay in EPSG:3794. Ocean/missing grid-cell values are
   excluded and remaining intersection weights are renormalized. Weather is not
   assigned from a single municipality centroid point.
7. Create only completed-week weather lags and the past-case feature described
   above.
8. Standardize the continuous model predictors using the arithmetic mean and
   population standard deviation fitted on the training rows only. Apply those
   frozen training statistics unchanged to the corresponding validation or
   lockbox rows. Do not standardize the population offset.
9. Supply `municipality_code` as the categorical field and
   `log(population / 100000)` as the CatBoost baseline.

For the one final pre-lockbox fit, the scaler is fitted once on all eligible
2016–2024 development rows, then applied unchanged to eligible 2025 inputs.

## Frozen missing-value handling

| Condition | Frozen handling | Reason |
|---|---|---|
| Blank NIJZ case cell | Convert to zero under the explicitly verified NIJZ source rule | In this source, blank case cells were confirmed to mean zero. This rule is source-specific. |
| Missing future target week or count | Mark target incomplete and exclude the row | Missing outcome data must not silently become zero. |
| Incomplete `t-4..t-1` case history | Exclude the row from models requiring the past-incidence feature | Imputation would invent past epidemiological information. |
| Missing required weather week/value | Exclude the row from both matched models | Weather is never zero-filled, forward-filled, or extrapolated. Equal exclusion preserves the matched comparison. |
| No strictly earlier population value | Exclude the row | An issue-year or future population value cannot be substituted when availability is unverified. |
| Missing/unmatched municipality code | Reject and report | Municipality identity, exposure, weather overlay, and target grouping depend on a verified code. |
| Early development weather prehistory | Exclude affected rows from both matched models | The weather contract requires complete backward-looking windows. |

No model-native missing-value routing is relied upon for required frozen
features. No missing value is converted to zero except the verified NIJZ blank
case rule.

## Frozen validation and final lockbox procedure

Development years are 2016–2024, subject to actual verified dates and complete
input windows. Model comparison uses eight expanding rolling-origin folds with
validation years 2017 through 2024.

For every fold:

- training rows precede the validation period;
- `train.target_window_end < validation_start` is mandatory;
- the complete validation target window must be contained within that fold's
  validation period;
- rows whose four-week targets cross a boundary are purged;
- feature transformations are fitted on training rows only; and
- neither 2025 inputs nor outcomes participate in fitting, feature decisions,
  hyperparameters, selection, calibration, or reported development metrics.

The matched weather experiment evaluated 81,832 validation predictions across
the eight folds. The weather history begins on 2016-03-30, so 3,604 early rows
that lacked required weather prehistory were removed from each relevant
expanding training sample; validation windows were complete. The two compared
models always used identical row sets within a fold.

After this freeze, the one-shot lockbox procedure is:

1. Prepare eligible 2025 feature rows under the unchanged source and feature
   contracts. Extend the verified ERA5-Land archive through the needed 2025
   completed weeks using the same variables, product, units, overlay, and weekly
   aggregations; do not fabricate values beyond the actual source cutoff.
2. Fit the frozen scaler and one final frozen CatBoost model on all eligible
   development rows only. A development row remains eligible only when its full
   target window is contained in development and all frozen predictors exist.
3. Predict eligible 2025 rows without supplying 2025 labels to fitting or
   preprocessing.
4. Only then load/materialize the corresponding complete 2025 targets and
   evaluate once using the frozen metrics.
5. Report missing or ineligible 2025 rows explicitly; do not impute them to make
   the evaluation sample larger.

There is no final all-development model artifact at freeze time. Creating it
only under the frozen protocol is intentional and does not require access to
2025 outcomes.

## Frozen metrics and selection evidence

The frozen count-forecast metrics are:

- mean absolute error (MAE), lower is better;
- root mean squared error (RMSE), lower is better; and
- mean Poisson deviance, lower is better and reported only when predictions are
  strictly positive and the metric is mathematically valid.

No single primary metric or numeric materiality threshold was prespecified.
Therefore, selection requires improvement across all three aggregate metrics
and reasonable fold stability, rather than choosing whichever metric looks best
after evaluation.

### Direct matched development comparison

| Model | MAE | RMSE | Mean Poisson deviance |
|---|---:|---:|---:|
| Matched S3 Poisson GLM | 1.320194 | 3.264934 | 1.721608 |
| Frozen CatBoost candidate | 1.182640 | 2.799903 | 1.515964 |
| Relative change, CatBoost vs S3 | -10.42% | -14.24% | -11.94% |

CatBoost improved MAE in 6/8 folds, RMSE in 6/8 folds, and Poisson deviance in
7/8 folds. MAE and RMSE deteriorated in 2017 and 2018; Poisson deviance
deteriorated in 2018. This is a material aggregate improvement with imperfect
but majority out-of-time stability, so CatBoost is selected for the one-shot
lockbox evaluation. The early-fold deterioration must remain visible in the
final interpretation.

Phase 8 Baseline D achieved development MAE 1.335796 and RMSE 3.187324. Its
Poisson deviance is not reported for selection because 4,114 positive-observation
pairs had a zero prediction.

The Phase 12 linear ablation did not show an incremental benefit from weather.
The final CatBoost experiment also did not include a same-row, otherwise
identical weather-free CatBoost control. Consequently, this freeze does **not**
claim that weather alone caused the CatBoost improvement. Weather remains in the
final candidate because it is a prespecified core project input and was present
in the completed matched challenger experiment; its independent incremental
value remains unresolved and must not be inferred from the lockbox by changing
the model afterward.

## Calibration and uncertainty

No calibration is applied. No thresholding, risk categorization, or decision
threshold is defined. No predictive intervals are produced by the frozen
CatBoost implementation. The output is an expected municipality-level count,
not an individual probability or personal-risk score.

Adding calibration, choosing a threshold, or selecting an interval method after
viewing 2025 outcomes would be post-lockbox model selection and is prohibited
unless 2025 is formally abandoned as the lockbox.

## Reproducibility identifiers

All hashes below are SHA-256. The canonical weekly-case hash was carried forward
from the Phase 13 provenance record rather than recomputed during this freeze,
so the freeze did not parse or inspect protected 2025 outcome values.

### Processed data and development evidence

| Artifact | SHA-256 | Bytes |
|---|---|---:|
| `model_v3/outputs/canonical/population.csv` | `8834ce82435e7b6a45a1504538e489bec8877568d43bf07a806e23cb499a38ad` | 54,290 |
| `model_v3/outputs/canonical/weekly_cases.csv`, source used by protected loaders | `e85085beb9314b7866781d0a8b77e5afe58812280de2e8503680576bd65daf1d` | 2,312,486 |
| `model_v3/outputs/targets/lyme_four_week_target.csv` | `2ed87bdd4f60e7d1279883edf7c17612875ee8f0af59f30656fd287220158459` | 5,894,149 |
| `model_v3/outputs/weather/era5_land_municipality_weekly.csv` | `b1006aee6f07470309e3448a9afaa516bafe1108952dfd62026bcdcbcf0c768f` | 15,885,561 |
| `model_v3/outputs/weather/era5_land_weekly_quality_summary.json` | `9d6fb543bed9ecb52bd0c15ff2867d9f68e3c3dee281bb96462ef4bfcc90bd75` | — |
| `model_v3/outputs/validation/lyme_rolling_origin_fold_manifest.csv` | `57cce888d8cc653d92be5dc332ced4f462e7930e6668004259d132d6fe1d6f30` | 1,044 |
| `model_v3/outputs/catboost_challenger/lyme_catboost_challenger_configuration.json` | `1caed622fce2fff9654a4408320eebe29c699605c87582dcb062e2c60bfa2d61` | — |
| `model_v3/outputs/catboost_challenger/lyme_catboost_challenger_quality_summary.json` | `25472ecdfda2422965b87fc4302d463b97fc1876e541fa8361218f13a6ec7184` | — |
| `model_v3/outputs/catboost_challenger/lyme_catboost_challenger_fold_predictions.csv` | `69bff149b665a5049a93026e6ee462622a5bee6f017faeefe0950c471cc7935e` | — |
| `model_v3/outputs/catboost_challenger/lyme_matched_statistical_reference_fold_predictions.csv` | `b0c99162b6603d2f24d91fb20bdcde0f5ac2c479057411e09fc478f89f090562` | — |
| `model_v3/outputs/catboost_challenger/lyme_catboost_development_comparison.csv` | `c19c6c0fa71a855471337604d4243e693671499597ee6c108c84fd3c29a043a5` | — |
| `model_v3/outputs/catboost_challenger/lyme_catboost_vs_statistical_fold_differences.csv` | `760010fcb55e5ddba4fe8854071ec6f667f35b953ec29fc99095b0406bc326fa` | — |
| `model_v3/outputs/catboost_challenger/lyme_catboost_stability_summary.csv` | `247751e9236cd8d33acdaca6de14205d93adc0f0af186265f02495ddb3aece0c` | — |

The target artifact's quality report records zero materialized lockbox targets
and zero parsed lockbox case values. It may contain protected structural row
metadata, but protected outcome values are not an input to development fitting
or evidence review.

### Configuration

| File | SHA-256 |
|---|---|
| `model_v3/config/canonical_epidemiology.json` | `e626ea736a1b29d63fa73d87b79ebc37fa999aef9a594880e78fcb97e0c34d10` |
| `model_v3/config/lyme_four_week_target.json` | `e9b19793599309924cbafc1b535d3ef8996aa5b2fef6ba3576a91bd0720419fb` |
| `model_v3/config/lyme_rolling_origin_validation.json` | `1da0ff79a681f87e81c5fd0a157a8459984af31f127fbfb2b9e8b707f4b80f08` |
| `model_v3/config/era5_land_weekly_weather.json` | `f2cc284b660689b27a15d1e55912b2111ace90a2b6926cdeb006fea849865637` |
| `model_v3/config/weather_data_contract.json` | `aeaebf963e61e4cd0d0ce3dd9610c95767ca916cf9464c693a37a4151213b13e` |
| `model_v3/config/lyme_catboost_challenger.json` | `b74bde5dd13d1f04f3d17e7c1b72acece7f2e1f3e69c2791f9b4b6e89f341305` |

### Active implementation and dependency lock

| File | SHA-256 |
|---|---|
| `model_v3/data/canonical_epidemiology.py` | `6ad9e4458e50d6efc11b9c67879f49925af557684f7ea12311f036899b62bc4e` |
| `model_v3/panel/lyme_four_week_target.py` | `858ad225988cfcbd220dd7ff4467050a976a4ef2ad0861b366f8a98ca294418e` |
| `model_v3/validation/rolling_origin.py` | `c7a7e2d5208895c83ddf3cebd0be78e243eb504e79cf7f866d32f176e5299881` |
| `model_v3/features/weather_weekly.py` | `6f2efb947355ae4c5954f2518b3603aadb985519e4f27f8a5f53e1f0e0c5c4e1` |
| `model_v3/models/seasonal_count_models.py` | `42bb3f863906d62c9943b374f87463cdf33fa5e98c3dccdd3610a99ab93800fd` |
| `model_v3/models/catboost_challenger.py` | `9b2e391ef0f08d1df92371d4dfbe98337f691a51c3bc44233fb633a29cf6e733` |
| `model_v3/requirements.txt` | `b0dc82fa6b002024fc56fd727b161935c48379b6cf8ad4e0c5fe9ae497267bae` |

The relevant frozen dependency versions include `catboost==1.2.10`,
`numpy==2.4.4`, and `statsmodels==0.14.6`.

### Repository version caveat

Git `HEAD` at freeze time is
`274dafa952750bd2e110bfa635735756a3ad24d0`. However, `model_v3/` is untracked
in that repository state. Therefore the commit hash alone does **not** identify
the frozen v3 implementation. The SHA-256 file and artifact identifiers above
are the authoritative reproducibility record until the v3 tree is committed.
Committing the unchanged frozen files is recordkeeping; changing their modelling
content is prohibited by this freeze.

## Frozen decision summary

The one model authorized for the initial 2025 lockbox evaluation is
`catboost_poisson_s3_weather_offset`, compared primarily with
`model_s3_weather_offset_matched` and secondarily with Phase 8 Baseline D. It
uses the exact four-week future Lyme count target, fixed municipality-week unit,
strictly backward-looking case and ERA5-Land features, fixed municipality zones,
and conservatively lagged population exposure. It uses the unchanged rolling
validation, preprocessing, missingness, parameters, metrics, and no-calibration
policy recorded above.
