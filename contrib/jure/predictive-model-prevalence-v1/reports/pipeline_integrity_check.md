# Pipeline Integrity Check

Verified locally on `2026-04-14`.

## Successful Commands

```powershell
py -3 reproducible_acquisition_pipelines\validate_pipelines.py
py -3 scripts\run_predictive_historical_data_pipeline.py
py -3 scripts\build_copernicus_forecast_processing_assets.py
py -3 scripts\build_predictive_model_training_tables.py
py -3 scripts\run_model_a_v2_residual_modeling.py
py -3 scripts\run_model_c_v2_residual_modeling.py
py -3 scripts\generate_model_a_v2_presentation_graphs.py
py -3 scripts\generate_model_c_v2_presentation_graphs.py
```

## Result

All listed commands completed successfully on the local workspace.

## Important Note

During `build_copernicus_forecast_processing_assets.py`, `xarray` reported that the
`cfgrib` engine was unavailable because the local Python 3.14 environment did not have
an ecCodes runtime. This did not block the processing step because the script completed
and the required outputs were written.

The dedicated GRIB numeric extraction step remains the place where Python `3.13` with a
working ecCodes installation is required.

## Methodology Status

- raw acquisition: reproducible and validated
- historical predictive panels: reproducible and built successfully
- future Copernicus processing: reproducible and built successfully
- Model A V2: operationally usable for Lyme and combined, weaker for KME
- Model C V2: usable as a climate-effect scenario model for Lyme and combined, weaker
  for KME
