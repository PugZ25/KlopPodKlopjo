# Fresh Open-Meteo weather context

This is the active delivery path for the public precaution app. The disease
signals remain weekly and require no current Lyme or KME case feed. The separate
weather panel refreshes daily from seven completed UTC days ending yesterday.

## Meaning and limits

- The source is Open-Meteo's forecast endpoint with the explicit DWD
  `icon_seamless` model.
- Values are recent operational-model history, not weather-station observations,
  direct tick measurements, infection risk, or an epidemiological case feed.
- Weather is not an input to either selected disease score.
- No tick-activity formula or categorical activity threshold is created. Air
  temperature, precipitation, shallow-soil temperature, and shallow-soil
  moisture are shown as descriptive context that can support precaution.
- The weekly model issue date is the current Monday. A daily weather refresh does
  not change the model signal between Mondays.

Open-Meteo documents multi-coordinate queries and the hourly soil variables in
its [forecast API documentation](https://open-meteo.com/en/docs). Model selection
and availability are documented on the
[DWD ICON API page](https://open-meteo.com/en/docs/dwd-api).

## Spatial conversion

The pipeline does not call one municipality centroid and does not claim native
ICON polygon integration. It queries 298 frozen sample coordinates, disables
Open-Meteo elevation downscaling, and selects the nearest ICON cell. It then
applies the existing 1,043 normalized municipality/grid intersection weights
derived from the fixed GURS 2026 municipality zones. The result contains one
seven-day record for each of all 212 municipalities.

This makes the delivered spatial summaries consistent with the established
polygon-weighted municipality layout while keeping the distinct source model
and approximation explicit.

## Reproducible path

1. `model_v3.features.open_meteo_activity_weather plan` resolves the current
   Monday and the seven completed days through yesterday.
2. `sync` downloads six immutable batched JSON responses, records exact request
   URLs and SHA-256 hashes, and writes a retrieval manifest.
3. `build` rejects incomplete time axes, changed units, unexpected coordinates,
   non-physical precipitation or moisture, missing sample points, and changed
   spatial weights before writing municipality values and a quality summary.
4. `model_v3.predict.precaution_snapshot` verifies that quality summary and keeps
   weather separate from the sealed Lyme and KME scores.
5. The daily GitHub Actions workflow verifies the frontend and publishes the
   dated static JSON. An invalid retrieval fails closed, leaving the previously
   published snapshot available.

Completed retrievals and derived outputs are idempotent: an exact manual rerun
reuses them only after validating request support, hashes, configuration, and
pipeline provenance. A failed download removes only its newly created partial
directory. The frontend displays a warning when the published snapshot is more
than 36 hours old, making a missed daily refresh visible without changing any
disease or activity score.

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
  --recent-weather RETRIEVAL_DIRECTORY/derived/municipality_recent_weather.csv \
  --weather-quality RETRIEVAL_DIRECTORY/derived/quality_summary.json
```

The `plan` output supplies `signal_issue_week`; `sync` prints the exact manifest
path, and `build` prints the two paths consumed by the snapshot generator. No
CDS or case-data credentials are required.
