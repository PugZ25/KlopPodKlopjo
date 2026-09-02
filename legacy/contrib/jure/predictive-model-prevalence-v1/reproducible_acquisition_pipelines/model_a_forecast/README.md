# Model A Forecast Pipeline

## Goal

Acquire the short-term predictive weather inputs for Model A:

- Slovenia scope only
- operational monthly seasonal forecasts
- lead months `1-6`
- same Copernicus weather families used by the predictive historical panel

## What This Pipeline Downloads

Dataset:

- `seasonal-monthly-single-levels`

Forecast families:

- `copernicus_temperature`
  - CDS variable:
    `2m_temperature`
  - best historical match:
    `air_temperature_c_mean`
- `copernicus_humidity`
  - CDS variables:
    `2m_temperature`, `2m_dewpoint_temperature`
  - best historical match:
    `relative_humidity_pct_mean` via temperature and dewpoint
- `copernicus_precipitation`
  - CDS variable:
    `total_precipitation`
  - best historical match:
    `precipitation_sum_mm`
- `copernicus_soil`
  - CDS variables:
    `soil_temperature_level_1`, `soil_temperature_level_2`,
    `volumetric_soil_water_layer_1`, `volumetric_soil_water_layer_2`
  - best historical match:
    the predictive panel soil-temperature and soil-water backbone

## Localization

This pipeline requests Slovenia directly using the CDS area selector:

- north: `46.9`
- west: `13.3`
- south: `45.3`
- east: `16.6`

## Method

1. choose initialization year and months
2. build one CDS request per family-month
3. store raw GRIB outputs under this duplicate pipeline folder
4. write a request manifest per family
5. write per-run and per-family reports for traceability

## Commands

Dry-run:

```powershell
py -3 model_a_forecast/run_download.py --dry-run --year 2026 --months 01 02 03 04
```

Live duplicate acquisition:

```powershell
py -3 model_a_forecast/run_download.py --year 2026 --months 01 02 03 04 --clear-proxy-env
```

## Output Layout

- `../output/model_a/raw/copernicus_forecast/`
- `../output/model_a/reports/runs/`

## Notes

- this pipeline is deliberately self-contained
- it does not write into the main predictive project raw folders
- later we can compare these staged duplicate outputs with the current project
  downloads before any cleanup
