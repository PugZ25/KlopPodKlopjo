# ERA5-Land municipality-week weather

This active Phase 12 layer transforms the verified final ERA5-Land archive
into deterministic fixed-municipality weekly observations. It opens only files
from 2016 through 2024. The enforced development weather cutoff is
`2024-12-31 23:00 UTC`; no post-cutoff weather is extrapolated or synthesized.

By explicit project rule, ERA5-Land `valid_time` is the retrospective weather
availability cutoff. Model features may use only completed Monday-to-Sunday
weather weeks strictly before `issue_week`; no additional publication-vintage
embargo is applied.

The documented GURS snapshot downloaded 2026-04-04 supplies the same 212 fixed
analytical municipality zones for every year. Grid cells are constructed from
the 0.1-degree coordinate midpoints, transformed with the municipalities to
`EPSG:3794`, intersected, and normalized by intersection area. ERA5-Land ocean
`NaN` cells are excluded from the denominator and the remaining intersection
weights are renormalized. A municipality with no present intersecting source
cell fails; missing values are never converted to zero.

Instantaneous temperature and soil variables are arithmetic means over 168
hourly municipality values. ERA5-Land total precipitation is deaccumulated at
the hourly grid-cell level following its 00 UTC forecast-cycle convention,
converted from metres to millimetres, then summed. Only negative differences
within a float32 machine-roundoff bound are clamped to zero; a larger negative
difference fails validation.

The first and last source weeks are incomplete because the archive starts on
2016-03-30 and the development cutoff occurs on 2024-12-31. They remain in the
output with explicit `incomplete_source_week` status and blank weather values.
No partial week is eligible for a model feature.

Reproduce with:

```bash
./.venv/bin/python -B -m model_v3.features.weather_weekly \
  --config model_v3/config/era5_land_weekly_weather.json
```
