# Weekly Open-Meteo weather features

This is the active weather-delivery path for the public precaution app. The
disease signals remain weekly and require no current Lyme or KME case feed. The
pipeline refreshes daily, but its analytical window changes only on Monday: it
retrieves the five completed Monday-to-Sunday UTC weeks strictly before the
current issue week. Four weeks are Lyme model inputs; the fifth supports the
previous issue week's comparison score.

## Meaning and limits

- The source is Open-Meteo's forecast endpoint with the explicit DWD
  `icon_seamless` model.
- Values are recent operational-model history, not weather-station observations,
  direct tick measurements, infection risk, or an epidemiological case feed.
- Air temperature, precipitation, and shallow-soil temperature from the four
  most recent completed weeks are inputs to the deployed Lyme score. Weather is
  not an input to the regional KME score.
- No tick-activity formula or categorical activity threshold is created. Air
  temperature, dew point, precipitation, two soil-temperature layers, and two
  soil-moisture layers are mapped to the established weekly ERA5-Land schema.
  Soil moisture is displayed but excluded from the score because its live ICON
  values fell outside the ERA5-Land training support. The latest completed week
  is shown as descriptive context.
- The weekly model issue date is the current Monday. A daily weather refresh does
  not change the model signal between Mondays.
- The public output is a precaution signal for the current Monday-to-Sunday
  week. The Lyme proxy is trained against reported Lyme cases in that same week
  `t`, while every runtime weather input comes from completed weeks `t-4`
  through `t-1`. The signal is still a modelled relative proxy, not a
  measurement of current-week tick activity, observed cases, or personal risk.

Open-Meteo documents multi-coordinate queries and the hourly soil variables in
its [forecast API documentation](https://open-meteo.com/en/docs). Model selection
and availability are documented on the
[DWD ICON API page](https://open-meteo.com/en/docs/dwd-api).

## Spatial conversion and source bridge

The pipeline does not call one municipality centroid and does not claim native
ICON polygon integration. It queries 298 frozen sample coordinates, disables
Open-Meteo elevation downscaling, and selects the nearest ICON cell. It then
applies the existing 1,043 normalized municipality/grid intersection weights
derived from the fixed GURS 2026 municipality zones. The result contains five
complete weekly records for each of all 212 municipalities.

This keeps the delivered spatial summaries consistent with the established
polygon-weighted municipality layout while keeping the source approximation
explicit. ERA5-Land trained the retrospective weather candidate; DWD ICON
supplies live inference values. The mapped variables and units match, but a
completed overlapping-source bias calibration is still absent. Deployment is
therefore recorded as an explicit product-policy override, not evidence that
the weather candidate improved validation. For every scored feature, the live
cross-municipality median must stay inside a season-matched outer fence derived
from final-training issue-week medians in a circular ±2 ISO-week window. The
fence is `Q1 - 3×IQR` through `Q3 + 3×IQR`, with only a source-resolution
allowance; otherwise snapshot generation fails closed. This detects systematic
source shifts without rejecting a legitimate local weather extreme.

## Reproducible path

1. `model_v3.features.open_meteo_activity_weather plan` resolves the current
   Monday and the five completed weeks before it.
2. `sync` downloads six immutable batched JSON responses, records exact request
   URLs and SHA-256 hashes, and writes a retrieval manifest.
3. `build` rejects incomplete time axes, changed units, unexpected coordinates,
   non-physical precipitation or moisture, missing sample points, and changed
   spatial weights before writing the seven-variable municipality-week table
   and a quality summary.
4. `model_v3.predict.precaution_snapshot` verifies the quality summary, applies
   the four-week weather features to the sealed Lyme proxy, and keeps weather
   separate from the sealed regional KME score.
5. The daily GitHub Actions workflow verifies the frontend and publishes the
   dated static JSON. An invalid retrieval fails closed, leaving the previously
   published snapshot available.

Completed retrievals and derived outputs are idempotent: an exact manual rerun
reuses them only after validating request support, hashes, configuration, and
pipeline provenance. A failed download removes only its newly created partial
directory. The frontend displays a warning when the published snapshot is more
than 36 hours old, making a missed refresh visible.

Relevant files:

- `model_v3/config/open_meteo_activity_weather.json`
- `model_v3/features/open_meteo_activity_weather.py`
- `model_v3/config/precaution_snapshot.json`
- `model_v3/predict/precaution_snapshot.py`
- `.github/workflows/daily-open-meteo-precaution.yml`

## Manual refresh

From the repository root:

```bash
python -m model_v3.features.open_meteo_activity_weather plan
python -m model_v3.features.open_meteo_activity_weather sync
python -m model_v3.features.open_meteo_activity_weather build \
  --manifest data/raw/open_meteo_activity_weather/retrievals/RETRIEVAL_ID/manifest.json
python -m model_v3.predict.precaution_snapshot \
  --issue-week YYYY-MM-DD \
  --recent-weather RETRIEVAL_DIRECTORY/derived/municipality_weekly_weather.csv \
  --weather-quality RETRIEVAL_DIRECTORY/derived/quality_summary.json
```

The `plan` output supplies `signal_issue_week`; `sync` prints the exact manifest
path, and `build` prints the two paths consumed by the snapshot generator. No
CDS or case-data credentials are required.
