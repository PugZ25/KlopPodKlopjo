# Model C Climate Pipeline

## Goal

Acquire the long-term climate-effect inputs for Model C:

- Slovenia scope only
- climate-projection oriented rather than operational weather
- scenario-based outputs for long-range disease burden analysis

## Preferred Dataset

- `multi-origin-c3s-atlas`

## Variable Strategy

This duplicate pipeline downloads the first-pass Model C package.

Regional `CORDEX-EUR-11` chunks:

- `monthly_temperature`
  - best historical match:
    `air_temperature_c_mean`
- `monthly_precipitation`
  - best historical match:
    `precipitation_sum_mm`
- `monthly_near_surface_specific_humidity`
  - best historical match:
    `relative_humidity_pct_mean` as a proxy rather than an exact one-to-one match

Global `CMIP6` chunks:

- `monthly_soil_moisture_in_upper_soil_portion`
  - best historical match:
    `soil_water_layer_1_m3_m3_mean` as a proxy

The soil-moisture part uses `CMIP6` because this Atlas dataset does not expose the
same soil-moisture variable under `CORDEX-EUR-11`.

## Scenario Structure

`CORDEX-EUR-11`:

- `historical` / `1970-2005`
- `rcp_4_5` / `2006-2100`
- `rcp_8_5` / `2006-2100`

`CMIP6`:

- `historical` / `1850-2014`
- `ssp2_4_5` / `2015-2100`
- `ssp5_8_5` / `2015-2100`

## Localization

The Atlas API accepted the Slovenia bbox directly for the downloaded package:

- north: `46.9`
- west: `13.3`
- south: `45.3`
- east: `16.6`

So this duplicate pipeline is Slovenia-localized at request time, not a whole-Europe
download cropped afterward.

## Method

1. define a fixed first-pass chunk plan
2. request one Atlas chunk at a time
3. save each chunk into a stable path under this duplicate pipeline folder
4. write per-chunk and per-run reports
5. keep the staged package separate from the main predictive project until cleanup
   decisions are made

## Commands

Dry-run:

```powershell
py -3 model_c_climate/run_download.py --dry-run
```

Live duplicate acquisition:

```powershell
py -3 model_c_climate/run_download.py --clear-proxy-env
```

## Output Layout

- `../output/model_c/raw/climate_atlas/`
- `../output/model_c/reports/runs/`

## Notes

- this pipeline is intentionally focused on raw acquisition only
- it does not yet extract or aggregate the ZIP payloads
- later we can compare these staged duplicate outputs with the current project
  climate downloads before removing older exploratory assets
