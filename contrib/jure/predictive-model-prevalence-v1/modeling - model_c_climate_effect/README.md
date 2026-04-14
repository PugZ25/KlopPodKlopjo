# Model C Climate-Effect Modeling

This folder is the dedicated modeling workspace for Model C.

Status:

- retained as the Model C V1 workspace for comparison
- not the primary active branch anymore
- the active climate-effect branch is `modeling - model_c_v2_residual_climate/`

Model C goal:

- fit Slovenia-level yearly prevalence models for Lyme, KME, and combined tick-borne disease
- use Copernicus climate-scenario covariates rather than short-range weather forecasts
- produce graph-ready future prevalence trajectories, especially for the next 10 years

This workspace stays downstream of:

- `../data processing - copernicus_forecast_data/outputs/model_c/`

It does not modify the upstream processing outputs.

## Workflow

1. copy the processed Model C calibration, projection, and observed-reference tables into `inputs/`
2. reserve the last two observed years, 2024 and 2025, as grouped final validation years
3. fit three separate prevalence models:
   - Lyme prevalence per 100k
   - KME prevalence per 100k
   - combined tick-borne prevalence per 100k
4. run recursive future projections by scenario family
5. write graph-ready tables into `outputs/`

## Main Command

```powershell
py -3 scripts/run_model_c_climate_modeling.py
```
