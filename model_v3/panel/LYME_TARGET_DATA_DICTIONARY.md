# Lyme four-week target data dictionary

## Purpose

This dataset defines the primary Lyme forecast target at the `municipality × issue_week` analysis unit. It contains target and target-quality metadata only. It contains no feature columns and does not build a predictive model.

## Reproduce

From the repository root:

```bash
./.venv/bin/python -B -m model_v3.panel.lyme_four_week_target \
  --config model_v3/config/lyme_four_week_target.json
```

Input: `model_v3/outputs/canonical/weekly_cases.csv`.

Output: `model_v3/outputs/targets/lyme_four_week_target.csv`.

The shared canonical input contains the sealed 2025 lockbox. The target loader
parses each row's `issue_week` first and skips every row on or after
`2025-01-01` before parsing municipality or case values. No 2025 issue row or
numeric 2025 target is materialized. A pre-2025 issue row whose intended target
window enters 2025 remains present with `incomplete_future_horizon`, a missing
target value, and `target_training_eligible=false`.

## Definition

For municipality `m` and issue week `t`:

```text
target_lyme_cases_next_4w(m, t)
  = lyme_cases(m, t+1)
  + lyme_cases(m, t+2)
  + lyme_cases(m, t+3)
  + lyme_cases(m, t+4)
```

The issue week `t` is explicitly excluded. No week after `t+4` is included. Date arithmetic uses consecutive seven-day steps, so ISO week 53 and year boundaries are handled by calendar dates rather than string or week-number arithmetic.

## Columns

| Column | Type | Meaning |
|---|---|---|
| `municipality_code` | three-character string | Municipality key copied from the canonical weekly case dataset. |
| `issue_week` | ISO date | Monday of the analysis issue week `t`. |
| `target_lyme_cases_next_4w` | nullable non-negative integer | Sum of Lyme cases at exactly `t+1` through `t+4`. Missing unless `target_status` is `complete`. |
| `target_window_start` | ISO date | Intended first target week, exactly `t+1` or seven days after `issue_week`. |
| `target_window_end` | ISO date | Intended final target week, exactly `t+4` or 28 days after `issue_week`. |
| `target_status` | string enum | Completeness status described below. |
| `target_training_eligible` | boolean | `true` only when `target_status` is `complete`; otherwise `false`. |

## Target statuses

| Status | Meaning | Target value | Training eligibility |
|---|---|---|---|
| `complete` | All four municipality-specific future Mondays `t+1..t+4` exist and have canonical Lyme case values. | Four-week sum | `true` |
| `incomplete_future_horizon` | At least one required future Monday lies after that municipality's final observed issue week, with no earlier internal week missing. | Missing | `false` |
| `missing_future_week` | At least one required future Monday at or before that municipality's final observed issue week is absent. | Missing | `false` |

Missing future rows never become zero. Rows with an incomplete target window are retained for auditability but are explicitly ineligible for supervised training.

## Scope exclusions

- No current-week or historical feature is created.
- No eight-week target is created.
- No KME target or model is created.
- No predictive model is created.
