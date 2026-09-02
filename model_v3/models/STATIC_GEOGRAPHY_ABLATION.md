# Lyme static-geography ablation

## Scope and reproduction

This Phase 11 experiment compares the unchanged Phase 9 S1 statistical model
with that same model plus one static municipality descriptor. It uses the same
Phase 6 development folds and the same target, population exposure rule,
Poisson family, log link and fitting settings as Phase 9. It does not evaluate
the 2025 lockbox.

Run from the repository root after building the static feature layer:

```bash
./.venv/bin/python -B -m model_v3.features.static_geography \
  --config model_v3/config/static_geography.json
./.venv/bin/python -B -m model_v3.models.static_geography_ablation \
  --config model_v3/config/lyme_static_geography_ablation.json
```

## Controlled comparison

The control is Phase 9 S1 without any change:

```text
target_lyme_cases_next_4w
  ~ 1 + seasonal_sin_annual + seasonal_cos_annual
  + offset(log(population))
```

The augmented arm appends exactly one column:

```text
target_lyme_cases_next_4w
  ~ 1 + seasonal_sin_annual + seasonal_cos_annual
  + municipality_area_km2
  + offset(log(population))
```

Population remains an explicit exposure and is not an ordinary feature. The
same conservative previous-year population selection used in Phase 9 applies
to both arms. The implementation recomputes the control and checks every
development prediction against the existing Phase 9 S1 output; that output is
used only for a post-fit parity assertion and never as a feature or fitting
input.

S2 and S3 are not used as the control because their municipality fixed effects
already span every time-invariant municipality-level column. Adding municipality
area to either design would be exactly non-identifiable, so it would not be a
valid ablation of a separately estimable static effect.

## Static feature contract

The only feature is `municipality_area_km2`. Its full source, acquisition date,
transformation, unit and missing-data contract are in
`model_v3/features/STATIC_GEOGRAPHY.md` and the machine-readable static feature
quality summary. Missing, invalid or nonpositive area fails the pipeline; no
value is imputed.

The source is a GURS municipality-boundary snapshot downloaded 2026-04-04. By
explicit project rule, those same 212 zones define the analytical
municipalities throughout 2016-2024. No time-varying historical boundary
reconstruction is attempted.

## Evaluation and outputs

Both arms receive identical fold rows. Training eligibility is controlled by
`target_window_end < validation_start`; validation target windows remain fully
inside their validation year. Metrics are MAE, RMSE and mean Poisson deviance.
For each metric the incremental result is:

```text
augmented metric - control metric
```

Because lower is better for all three metrics, a negative value is labelled
`improvement`, a positive value `deterioration`, and zero `no_change`. These
labels are descriptive and use no model-selection threshold.

Outputs under `model_v3/outputs/static_geography_ablation/` include row-level
fold predictions, fold and aggregate metrics, the incremental comparison,
fit diagnostics, coefficients, realized configuration and a machine-readable
quality summary. No predictive interval is produced in this ablation; the
comparison concerns point-forecast metrics only.

No weather, land-cover, elevation, CatBoost, classification metric, threshold
or generated prediction feature is used.
