# Lyme prediction snapshot contract v1

This contract exposes one municipality-level, four-week Lyme case-count prediction snapshot from the frozen selected model. The current artifact is a retrospective snapshot derived from the sealed Phase 15 prediction output. It is not a live/current forecast and is not connected to the frontend.

Both `prediction_snapshot.parquet` and `prediction_snapshot.json` are serialized from the same validated Arrow table. The JSON path contains no separate prediction or feature implementation.

## Snapshot selection and lineage

- Selected model: `catboost_poisson_s3_weather_offset`.
- Issue-date rule: the latest `issue_week` present for that model in the sealed Phase 15 prediction output.
- Analysis unit: one row per canonical municipality for one issue date.
- Horizon: expected reported Lyme cases in exactly `t+1` through `t+4`; the issue week is excluded.
- Municipality names: joined from the canonical municipality dimension by `municipality_code`.
- Population denominator: the already-selected model exposure in the sealed prediction row. Phase 9's conservative rule selected the latest present population year strictly before the issue year.
- Prediction generation time: `completed_at_utc` in the sealed Phase 15 receipt. This identifies when the source prediction was generated, not when the files were copied into this contract.

All input hashes are pinned in `model_v3/config/lyme_prediction_snapshot.json`. A mismatch stops generation.

## Fields

| Field | Arrow type | Nullable | Meaning |
|---|---|---:|---|
| `municipality_code` | string | no | Canonical municipality code; join key. |
| `municipality_name` | string | no | Canonical municipality name for the code. |
| `issue_date` | date32 | no | The selected model's weekly issue date (`issue_week`, a Monday). |
| `horizon_weeks` | int16 | no | `4`; forecast covers `t+1..t+4`. |
| `predicted_cases` | float64 | no | Expected reported Lyme case count over the four-week horizon. Non-negative; it need not be an integer. |
| `predicted_incidence_per_100k` | float64 | yes | `predicted_cases / population_exposure * 100,000`, only for a positive population denominator. |
| `lower_interval` | float64 | yes | Lower predictive interval endpoint, if supplied by the frozen model. Currently null because that model supplies no predictive intervals. |
| `upper_interval` | float64 | yes | Upper predictive interval endpoint, if supplied by the frozen model. Currently null because that model supplies no predictive intervals. |
| `model_version` | string | no | Selected model ID plus the full SHA-256 of its frozen configuration. |
| `data_version` | string | no | Full SHA-256 of the sealed selected-model prediction source. |
| `generated_at` | UTC timestamp | no | Source prediction completion time from the sealed receipt. |
| `data_status` | string | no | Explicit snapshot/denominator status defined below. |

`data_status` has two allowed v1 values:

- `retrospective_lockbox_evaluation_prediction`: prediction and incidence denominator are valid.
- `retrospective_lockbox_evaluation_prediction_missing_population_denominator`: predicted cases are present, but incidence is null because the population denominator is missing or non-positive.

## JSON envelope

The JSON document has `schema_version` and a `predictions` array. Each prediction object contains exactly the twelve fields above. Dates use ISO `YYYY-MM-DD`; UTC timestamps use an ISO timestamp ending in `Z`; unavailable values use JSON `null`.

The output deliberately excludes observed outcomes, model inputs, arbitrary risk scores, risk categories, probabilities, and personal-risk language.
