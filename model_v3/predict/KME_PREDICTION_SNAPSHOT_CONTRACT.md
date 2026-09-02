# KME prediction snapshot contract

This contract exposes the frozen selected KME model in the same canonical Parquet-and-JSON pattern used by the Lyme snapshot. It does not change the KME analysis design or evaluate protected outcomes.

## Scope

- Analysis unit: statistical region × issue date.
- Horizon: reported regional KME count in exactly t+1 through t+8; issue week excluded.
- Selected model: `glm_seasonal_region_offset`.
- Snapshot issue date: the latest sealed issue week not after the prediction seal date.
- Geographic convention: the verified statistical-region mapping and fixed municipality zones already frozen for the KME system.
- Population: the same safely lagged regional denominator used by the model offset and incidence calculation.

The current v1 snapshot uses issue date `2026-08-24`. It contains 12 rows, one for each verified statistical region. It is a repository-controlled prediction snapshot, not observed 2026 performance and not a fully prospective experiment.

## Canonical fields

| Field | Meaning |
|---|---|
| `statistical_region_code` | Verified statistical-region code. |
| `statistical_region_name` | Canonical statistical-region name. |
| `issue_date` | Monday issue date. |
| `horizon_weeks` | Fixed value 8. |
| `predicted_cases` | Non-negative expected reported regional KME count for t+1..t+8. |
| `predicted_incidence_per_100k` | `predicted_cases / population_exposure × 100,000`, using the same denominator as the offset. |
| `lower_interval`, `upper_interval` | Null because no predictive-interval method was frozen. |
| `model_version` | Selected model and frozen coefficient hash. |
| `data_version` | Hash-derived input-data identifier carried from the sealed predictions. |
| `generated_at` | Deterministic seal-date timestamp used for snapshot lineage. |
| `data_status` | Explicit repository-controlled prediction status. |

The snapshot does not contain observed targets, arbitrary risk scores, categories, probabilities, or personal-risk language.

## Outputs

- `model_v3/outputs/kme_prediction_snapshot/v1/prediction_snapshot.parquet`
- `model_v3/outputs/kme_prediction_snapshot/v1/prediction_snapshot.json`
- `model_v3/outputs/kme_prediction_snapshot/v1/prediction_snapshot_quality.json`

Parquet and JSON are generated from the same validated Arrow table. The quality summary records schema checks, exact source hashes, output hashes, coverage, lineage, and the fact that no 2026 KME outcome was read.
