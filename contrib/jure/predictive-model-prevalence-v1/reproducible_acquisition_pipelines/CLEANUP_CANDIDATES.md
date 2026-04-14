# Cleanup Candidates

Cleanup has now been applied for the first agreed removal pass.

## Why This File Exists

The main predictive project currently contains some exploratory or duplicate assets
from the acquisition build-out phase. The duplicate pipelines in
`reproducible_acquisition_pipelines/` have now been validated, so the first removal
pass is complete.

## Removed In The First Cleanup Pass

- `Predikcijski model prevalence V1/raw/copernicus/climate_atlas/probes/`
  - temporary benchmark downloads used only to estimate Atlas runtime and file size
- duplicate exploratory run folders:
  - `Predikcijski model prevalence V1/Copernicus_predictive_data/model_c_climate/runs/20260413T205109Z/`
  - `Predikcijski model prevalence V1/Copernicus_predictive_data/model_a_operational/runs/20260413T195922Z/`
- exploratory report folders:
  - `Predikcijski model prevalence V1/reports/live_probe/`
  - `Predikcijski model prevalence V1/reports/live_batch/`
- superseded generic acquisition scripts:
  - `Predikcijski model prevalence V1/scripts/run_copernicus_future_pipeline.py`
  - `Predikcijski model prevalence V1/scripts/download_copernicus_seasonal_forecasts.py`
- transient clutter:
  - `Predikcijski model prevalence V1/scripts/__pycache__/`
  - `.DS_Store` files under `Predikcijski model prevalence V1/raw/copernicus/`

## Not Cleanup Candidates

- current validated raw Model A downloads
- current validated raw Model C downloads
- predictive historical panels
- anything inside `environmental_explanation_project/`

## Retained On Purpose

- archived reports and run summaries that document successful acquisition
- the clean portable duplicate pipelines under `reproducible_acquisition_pipelines/`
- current main entrypoints:
  - `Predikcijski model prevalence V1/scripts/run_model_a_slovenia_partitioned_download.py`
  - `Predikcijski model prevalence V1/scripts/run_model_c_climate_chunked_download.py`

## Validation Basis

The cleanup was applied only after:

1. the duplicate pipelines validated cleanly
2. the staged duplicate outputs were inspected
3. the removal set was narrowed to explicitly redundant exploratory assets
