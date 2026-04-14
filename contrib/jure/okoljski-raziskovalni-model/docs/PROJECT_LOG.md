# Project Log

## Scope

This file tracks `okoljski_raziskovalni_model` from copied raw inputs to grouped environmental graphs and validation outputs.

## Planned Pipeline

1. Normalize local source files.
2. Build the municipality-week master panel.
3. Review and flag variables for environmental use.
4. Build a date-aligned environmental model-ready panel.
5. Run grouped environmental/source ablations.
6. Generate presentation graphs and commentary.
7. Validate development stability and final holdout behavior.

## Validation Reservation

- `2025` is reserved as the final untouched validation year.

## Notes

- This standalone project copies the raw inputs so it can be reproduced later without depending on the older mixed predictive workflow.
- The earlier project folders are intentionally left untouched outside this subproject for now.

## Current Implementation Status

- Stage 1 complete: local Slovenia datasets normalized into a reproducible form.
- Stage 2 complete: municipality-week master panel rebuilt inside the standalone project.
- Stage 3 complete: variables flagged so environmental, identifier, target, and optional local-source roles are explicit.
- Stage 4 complete: environmental model-ready panel built with current-burden rolling targets and holdout reservation.
- Stage 5 complete: grouped environmental ablation run with disease-history predictors excluded.
- Stage 6 complete: standalone graphs and commentary generated from the grouped evaluation outputs.
- Stage 7 complete: development stability and reserved `2025` holdout validation completed and written to `data/processed/model_validation/`.

## Frozen Design Choices

- This branch explains environmental burden patterns rather than forecasting future burden.
- Disease-history predictors are excluded from the main explanatory comparisons.
- Environmental lags are allowed because exposure can precede reporting.
- Raw calendar fields are replaced by a hidden annual-phase control rather than being ranked as visible factors.
- Copernicus tick-activity proxy columns are retired from this branch at the master-panel stage rather than scored as core environmental factors.
- Broad mixed weather blocks were retired in favor of smaller scientific factor families.
- The earlier `all_local_combined` comparison was removed so local sources are judged one factor family at a time.
- Low-coverage local data are kept in the comparison framework, but their coverage must always be read alongside their score.

## Current Findings Snapshot

- `Combined tick-borne burden`: strongest scored groups are `Land Cover`, `Topography`, `Copernicus Humidity`, and `Copernicus Precipitation`.
- `KME / TBE`: strongest scored groups are `Land Cover` and `Copernicus Precipitation`; `OBROD Summary` is the only local family with a small positive average effect.
- `Lyme / borreliosis`: strongest scored groups are `Land Cover` and `Copernicus Humidity`.
- Retiring the Copernicus tick-activity proxy block materially changed the ranking and removed a noisy derived family from the main comparison.
- The combined target still behaves more like Lyme than KME, which is expected because Lyme contributes most of the combined case volume.
- No local factor family improves the combined reference model on average in the current run.
- Lyme shows a small positive `GOZDIS Humidity` signal, but it covers only about `4.7%` of validation rows and must be treated as low-coverage evidence.
- Holdout validation confirms `Land Cover` across all three targets.
- Holdout validation confirms `Copernicus Humidity` for Lyme and the combined target, and confirms `Copernicus Precipitation` for KME and the combined target.
- `OBROD Summary` does not confirm on the holdout because there is no OBROD coverage in the reserved `2025` year.

## Reproducibility Note

The standalone branch can be rebuilt from its own copied inputs by running:

```powershell
py -3 scripts/run_environment_pipeline.py
```
