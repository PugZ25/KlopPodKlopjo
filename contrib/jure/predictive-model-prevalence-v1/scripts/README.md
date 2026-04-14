# Scripts

This folder contains the runnable Python entrypoints for the predictive project.

## Groups

- acquisition
  - `run_model_a_slovenia_partitioned_download.py`
  - `run_model_c_climate_chunked_download.py`
- historical panel assembly
  - `run_predictive_historical_data_pipeline.py`
  - `build_predictive_panels.py`
  - `sync_reference_inputs.py`
- future-data processing
  - `build_copernicus_forecast_processing_assets.py`
  - `build_predictive_model_training_tables.py`
  - `extract_model_a_forecast_values.py`
- modeling
  - `run_model_a_operational_modeling.py`
  - `run_model_a_v2_residual_modeling.py`
  - `run_model_c_climate_modeling.py`
  - `run_model_c_v2_residual_modeling.py`
- chart generation
  - `generate_model_a_presentation_graphs.py`
  - `generate_model_a_v2_presentation_graphs.py`
  - `generate_model_c_presentation_graphs.py`
  - `generate_model_c_v2_presentation_graphs.py`
- shared utility
  - `pipeline_utils.py`

## Active Recommendation

Prefer the V2 scripts for current forecasting and presentation work.
