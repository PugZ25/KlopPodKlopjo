# Predikcijski model prevalence V1

This folder is the standalone predictive workspace for Slovenia tick-borne disease
forecasting. It is separate from the frozen explanatory baseline in
`environmental_explanation_project/`, which remains read-only and is used only as a
reference for data families, naming, and environmental categorization.

## Project Goal

Build a predictive branch for future KME, Lyme, and combined tick-borne burden using:

- copied historical and static local inputs
- Copernicus forecast and climate-projection data
- separate short-range and long-range modeling tracks

## Active Pipeline

The active predictive workflow is:

1. acquire or validate raw Copernicus forecast and climate data
2. build the historical municipality and Slovenia predictive panels
3. process future Copernicus data into model-ready tables
4. fit separate Model A and Model C predictive workspaces
5. generate graph-ready outputs and reports

## Active And Legacy Workspaces

Active workspaces:

- `reproducible_acquisition_pipelines/`
- `data processing - copernicus_forecast_data/`
- `modeling - model_a_v2_residual_forecast/`
- `modeling - model_c_v2_residual_climate/`

Retained for comparison and audit:

- `Copernicus_predictive_data/`
- `modeling - model_a_operational_forecast/`
- `modeling - model_c_climate_effect/`

## Structure

This project keeps the same logical data split used in `GITlookup` even though the
folders stay at the project root:

- `raw/` corresponds to a `data/raw` layer
- `interim/` corresponds to a `data/interim` layer
- `processed/` corresponds to a `data/processed` layer
- `reference data/` holds copied frozen inputs that must not be edited
- `scripts/` holds reproducible entrypoints
- `docs/` holds methodology, structure, and validity notes
- `reports/` holds cross-pipeline run summaries

See:

- [docs/PROJECT_STRUCTURE.md](./docs/PROJECT_STRUCTURE.md)
- [docs/VALIDITY_AND_LIMITATIONS.md](./docs/VALIDITY_AND_LIMITATIONS.md)

## Main Commands

Validate the self-contained acquisition pipelines:

```powershell
py -3 reproducible_acquisition_pipelines\validate_pipelines.py
```

Build the historical predictive panels:

```powershell
py -3 scripts/run_predictive_historical_data_pipeline.py
```

Build forecast-processing assets and model tables:

```powershell
py -3 scripts/build_copernicus_forecast_processing_assets.py
py -3 scripts/build_predictive_model_training_tables.py
```

Extract Model A numeric GRIB values:

```powershell
py -3.13 scripts/extract_model_a_forecast_values.py
```

Run the active V2 models:

```powershell
py -3 scripts/run_model_a_v2_residual_modeling.py
py -3 scripts/run_model_c_v2_residual_modeling.py
```

Generate the active V2 charts:

```powershell
py -3 scripts/generate_model_a_v2_presentation_graphs.py
py -3 scripts/generate_model_c_v2_presentation_graphs.py
```

## Raw Copernicus Family Alignment

The predictive branch keeps the same Copernicus family structure as the explanatory
baseline:

- `copernicus_temperature`
- `copernicus_humidity`
- `copernicus_precipitation`
- `copernicus_soil`
- `land_cover`
- `topography`

Only the first four families require future-data acquisition. Static `land_cover` and
`topography` inputs are already present locally.

## Integrity Status

The local predictive branch was re-run successfully on `2026-04-14` for:

- acquisition-pipeline validation
- historical predictive panel generation
- future forecast-processing table generation
- Model A V2 and Model C V2 execution
- Model A V2 and Model C V2 chart generation

The detailed integrity note is in:

- [reports/pipeline_integrity_check.md](./reports/pipeline_integrity_check.md)

## Important Methodology Caveats

- Model A V2 is a short-range operational prototype. Its historical validation uses
  observed weather as a proxy for archived forecast weather.
- Model C V2 is a climate-effect scenario model, not an exact year-by-year weather
  forecast.
- KME remains weaker than Lyme and combined burden in both V2 branches and should not
  be presented as equally validated.
