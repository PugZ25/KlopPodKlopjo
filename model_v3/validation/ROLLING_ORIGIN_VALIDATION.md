# Lyme rolling-origin validation policy

## Scope

This stage generates time-aware development folds for the primary four-week Lyme target. It does not create features, train a model, choose hyperparameters, calibrate predictions, or calculate performance.

Input: `model_v3/outputs/targets/lyme_four_week_target.csv`.

Outputs:

- `model_v3/outputs/validation/lyme_rolling_origin_fold_manifest.csv`
- `model_v3/outputs/validation/lyme_rolling_origin_quality.json`

Reproduce from the repository root:

```bash
./.venv/bin/python -B -m model_v3.validation.rolling_origin \
  --config model_v3/config/lyme_rolling_origin_validation.json
```

## Development and lockbox periods

- Configured development years: 2016 through 2024.
- Reserved lockbox year: 2025.
- Only years actually present in the target metadata are used; missing calendar years are not manufactured.
- The first available development year seeds training. Each later available development year becomes one validation period, with an expanding training history.
- The generator selects and uses target-window metadata only; it does not access or use the numeric target value for fold construction.
- Rows with a 2025 `issue_week`, and rows whose target windows enter 2025, are absent from every development fold.

For the verified current input, the available development years are 2016–2024, producing validation folds for 2017–2024.

## Boundary rules

For each validation year, `validation_start` and `validation_end` are the minimum and maximum actually observed `issue_week` dates in that year.

A row may enter training only when:

```text
target_status = complete
target_training_eligible = true
issue_week < validation_start
target_window_end < validation_start
```

The final comparison is strict. A training target ending exactly on `validation_start` is purged.

This evaluation definition requires a validation target window to be wholly contained in its validation period:

```text
target_status = complete
target_training_eligible = true
validation_start <= issue_week <= validation_end
target_window_start >= validation_start
target_window_end <= validation_end
```

Consequently, late-year validation issue weeks whose four-week targets cross into the next year are purged. In particular, 2024 target windows that enter the 2025 lockbox are not used.

## Fold manifest columns

| Column | Meaning |
|---|---|
| `fold_id` | Deterministic identifier based on fold order and validation year. |
| `train_issue_start` | Earliest included training issue week. |
| `train_issue_end` | Latest included training issue week after the boundary purge. |
| `train_target_end_max` | Latest target-window end among included training rows; always strictly before validation start. |
| `validation_start` | Earliest observed issue week in the validation year. |
| `validation_end` | Latest observed issue week in the validation year and the latest allowed validation target-window end. |
| `n_train` | Included municipality-week training rows. |
| `n_validation` | Included municipality-week validation rows. |
| `number_of_purged_rows` | Sum of eligible training-boundary and validation-containment exclusions for the fold. |
| `n_train_boundary_purged` | Eligible pre-validation rows excluded because their target window does not end strictly before validation starts. |
| `n_validation_boundary_purged` | Eligible validation-year rows excluded because their target window is not wholly contained. |
| `n_ineligible_excluded` | Rows in the fold's candidate periods already marked target-ineligible by the target stage; these are not counted as boundary purges. |

The fold manifest contains boundaries and counts, not model outcomes or performance metrics. Exact row membership is generated deterministically by `generate_rolling_origin_folds` using the documented rules.
