# Script Execution Methodology

## Purpose

The scripts in this folder are organized as reproducible project entrypoints rather
than one-off notebooks.

## Recommended Execution Order

1. validate acquisition logic if raw future data must be refreshed
2. build historical predictive panels
3. build future Copernicus processing assets
4. assemble model-ready training tables
5. run active V2 models
6. generate V2 charts

## Active Command Sequence

```powershell
py -3 reproducible_acquisition_pipelines\validate_pipelines.py
py -3 scripts\run_predictive_historical_data_pipeline.py
py -3 scripts\build_copernicus_forecast_processing_assets.py
py -3 scripts\build_predictive_model_training_tables.py
py -3.13 scripts\extract_model_a_forecast_values.py
py -3 scripts\run_model_a_v2_residual_modeling.py
py -3 scripts\run_model_c_v2_residual_modeling.py
py -3 scripts\generate_model_a_v2_presentation_graphs.py
py -3 scripts\generate_model_c_v2_presentation_graphs.py
```

## Stability Rule

When adding new scripts, place them in one of the existing groups and document them in
this folder instead of creating undocumented parallel entrypoints.
