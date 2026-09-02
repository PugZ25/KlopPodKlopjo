# Weather data contract

## Decision

**Status: implemented for retrospective development through the verified
ERA5-Land weather cutoff.**

This project treats ERA5-Land weather as a core data source. By explicit
project rule, the source `valid_time` is the retrospective availability
cutoff. No additional publication-delay embargo is invented. A feature for
`issue_week = t` may use only complete Monday-to-Sunday weather weeks ending
strictly before `t`, and it may never use or create weather after the verified
source cutoff.

The active final ERA5-Land (`expver=0001`) archive contains hourly data from
2016-03-30 00:00 UTC through 2024-12-31 23:00 UTC. The same verified product,
definitions, units, grid, and aggregation code are used throughout the
retrospective development experiment. Preliminary `expver=0005` is not mixed
in. This contract does not authorize operational predictions requiring
weather beyond the archive cutoff; a future source extension must first pass
the same schema and quality checks.

The 2025 weather files and 2025 epidemiological targets were not opened. No
2025 performance was computed.

## Variable contract

| VARIABLE | SOURCE | UNIT | TEMPORAL RESOLUTION | SPATIAL RESOLUTION | MUNICIPALITY AGGREGATION | AVAILABLE AT ISSUE TIME? | TRAIN SOURCE | INFERENCE SOURCE |
|---|---|---|---|---|---|---|---|---|
| `2m_temperature` (`t2m`) | CDS `reanalysis-era5-land`, final `0001` | raw K; output °C = K − 273.15 | hourly instantaneous; complete-week mean | regular 0.1° × 0.1° | fixed-zone area-weighted mean | Yes when the completed source week ends before `issue_week` and not after cutoff | verified local final ERA5-Land archive | same archive through cutoff |
| `2m_dewpoint_temperature` (`d2m`) | CDS `reanalysis-era5-land`, final `0001` | raw K; output °C = K − 273.15 | hourly instantaneous; complete-week mean | regular 0.1° × 0.1° | fixed-zone area-weighted mean | Same rule | same final archive | same final archive through cutoff |
| `total_precipitation` (`tp`) | CDS `reanalysis-era5-land`, final `0001` | raw m water equivalent; output mm | hourly accumulated validity values; official deaccumulation then complete-week sum | regular 0.1° × 0.1° | fixed-zone area-weighted precipitation depth | Same rule | same final archive | same final archive through cutoff |
| `soil_temperature_level_1` (`stl1`, 0–7 cm) | CDS `reanalysis-era5-land`, final `0001` | raw K; output °C | hourly instantaneous; complete-week mean | regular 0.1° × 0.1° | fixed-zone area-weighted mean | Same rule | same final archive | same final archive through cutoff |
| `soil_temperature_level_2` (`stl2`, 7–28 cm) | CDS `reanalysis-era5-land`, final `0001` | raw K; output °C | hourly instantaneous; complete-week mean | regular 0.1° × 0.1° | fixed-zone area-weighted mean | Same rule | same final archive | same final archive through cutoff |
| `volumetric_soil_water_layer_1` (`swvl1`, 0–7 cm) | CDS `reanalysis-era5-land`, final `0001` | m³/m³, unchanged | hourly instantaneous; complete-week mean | regular 0.1° × 0.1° | fixed-zone area-weighted mean | Same rule | same final archive | same final archive through cutoff |
| `volumetric_soil_water_layer_2` (`swvl2`, 7–28 cm) | CDS `reanalysis-era5-land`, final `0001` | m³/m³, unchanged | hourly instantaneous; complete-week mean | regular 0.1° × 0.1° | fixed-zone area-weighted mean | Same rule | same final archive | same final archive through cutoff |

Official source documentation:

- [ERA5-Land data documentation](https://confluence.ecmwf.int/spaces/CKB/pages/140385202/ERA5-Land+data+documentation);
- [ERA5-Land CDS dataset](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land);
- [official accumulated-variable conversion table](https://confluence.ecmwf.int/pages/viewpage.action?pageId=253727898).

## Spatial contract

The GURS geometry snapshot downloaded 2026-04-04 defines 212 fixed analytical
municipality zones. By project rule, these same zones apply to every analysis
year; the pipeline does not attempt historical boundary reconstruction.

The transformation:

1. constructs grid-cell polygons from coordinate midpoint edges;
2. transforms grid cells and municipalities to `EPSG:3794`;
3. intersects cells with municipality polygons;
4. normalizes intersection-area weights within municipality;
5. excludes source `NaN` cells and renormalizes present weights.

A municipality with no present source cell fails. Missing weather is never
converted to zero.

## Temporal and feature contract

Weather weeks run from Monday 00:00 UTC through Sunday 23:00 UTC and require
all 168 hourly values. Partial weeks have explicit
`incomplete_source_week` status and blank weather columns.

The Phase 12 experiment uses, for each verified weekly variable:

- lag 1: `t−1` completed week;
- lag 2: `t−2` completed week;
- previous four: exactly `t−4..t−1` (mean for instantaneous variables, sum
  for weekly precipitation totals).

Current-week, centered, and future weather are forbidden. A missing completed
week makes that row ineligible for the weather experiment; it is not imputed.
Weather standardization is fitted on the training portion of each fold only.

## Development archive audit

The loader filters filenames before opening NetCDF data. For 2016–2024:

- source files: 106;
- valid times: 76,776 hourly rows;
- range: 2016-03-30 00:00 UTC through 2024-12-31 23:00 UTC;
- missing or duplicate hours: 0;
- distinct grids and seven-variable schemas: 1 each;
- observed `expver`: `0001` only;
- lockbox-or-later files opened: 0.

The weekly output has 97,096 municipality-week rows: 456 complete weeks for
each of 212 municipalities and two explicit incomplete boundary weeks. Early
2016 issue rows without four prior complete weather weeks are excluded from
all four experiment arms so their comparison remains like-for-like.

## Implemented outputs

- `model_v3/outputs/weather/era5_land_municipality_weekly.csv`;
- `model_v3/outputs/weather/era5_land_municipality_grid_weights.csv`;
- `model_v3/outputs/weather/era5_land_weekly_quality_summary.json`;
- `model_v3/outputs/weather_ablation/` for the four-arm fold predictions,
  metrics, coefficients, diagnostics, and quality summary.

The implemented comparison is S1, S1 plus static area, S1 plus weather, and S1
plus both. It reuses the existing development folds and population offset; it
does not use classification, CatBoost, risk categories, or the 2025 lockbox.

Phase 13 separately uses the same verified lagged weather contract in a
weather-aware CatBoost challenger and a matched statistical reference. That
experiment remains development-only and does not authorize weather beyond the
verified source cutoff.
