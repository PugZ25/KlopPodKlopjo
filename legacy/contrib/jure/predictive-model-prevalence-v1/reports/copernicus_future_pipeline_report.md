# Copernicus Future Pipeline Report

- mode: `live`
- generated at: `2026-04-13T17:28:40.660420+00:00`

## Raw State

- ERA5-Land hourly files present: `119`
- DEM tiles present: `12`
- land-cover tif files present: `6`
- GURS municipality GeoJSON present: `True`

## Environment

- `cdsapi` installed: `True`
- `~/.cdsapirc` present: `False`
- `CDSAPI_URL` present: `False`
- `CDSAPI_KEY` present: `False`
- any usable CDS credentials detected: `False`

## Runs

### monthly_stats -> copernicus_temperature

- output dir: `C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\raw\copernicus\forecast\copernicus_temperature\seasonal-monthly-single-levels`
- source: https://cds.climate.copernicus.eu/datasets/seasonal-monthly-single-levels
- exit code: `1`

```powershell
C:\Users\George\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\scripts\download_copernicus_seasonal_forecasts.py --dataset-kind monthly_stats --variable-family copernicus_temperature --originating-centre ecmwf --system 51 --output-dir C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\raw\copernicus\forecast\copernicus_temperature\seasonal-monthly-single-levels --years 2026 --months 01 --leadtime-months 1 2 3 4 5 6
```

### STDOUT

```text
Planned 1 CDS requests for seasonal-monthly-single-levels -> copernicus_temperature.
```

### STDERR

```text
Unable to initialize the CDS API client. Add valid CDS credentials via ~/.cdsapirc or the CDSAPI_URL and CDSAPI_KEY environment variables, then rerun the acquisition.
Missing/incomplete configuration file: C:\Users\George/.cdsapirc
```

## Post-Processing Status

Raw forecast acquisition is the current stopping point.
Municipality or Slovenia aggregation has not started yet.
Post-processing should begin only after the target raw forecast files are present under `raw/copernicus/forecast/`.

