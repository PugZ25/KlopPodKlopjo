# Tedenski CatBoost Dataset

Ta dokument opisuje koncni tedenski dataset za modeliranje borelioze in KME na ravni obcine.

## Kaj je zdruzeno

- tedenske vremenske znacilke po obcinah
- Copernicus DEM znacilke
- Copernicus CLC land-cover znacilke
- SURS letne demografske znacilke
- NIJZ tedenski primeri borelioze in KME

Koncen izhod je:
- `data/processed/training/obcina_weekly_tick_borne_catboost_ready.csv`
- `data/processed/training/obcina_weekly_tick_borne_catboost_ready_manifest.json`

## Metodoloska pravila

- Join po prostoru vedno temelji na `obcina_sifra`.
- Join po casu za cilje in epidemioloske lage temelji na `week_start`.
- Za boreliozo so dodani samo:
  - `lyme_cases_lag_2w`
  - `lyme_cases_lag_3w`
  - `lyme_cases_prev_4w_sum`
- Za KME so dodani samo:
  - `kme_cases_lag_2w`
  - `kme_cases_prev_8w_sum`
- `prev_4w_sum` in `prev_8w_sum` uporabljata izkljucno pretekle tedne `t-1 ... t-k`.
- Delna okna se ne uporabljajo. Ce ni dovolj zgodovine, je vrednost prazna (`NaN`).
- V izvozenem datasetu ni trenutnih `lyme_cases` ali `kme_cases` kot featurejev, samo target stolpci.
- Letne SURS znacilke se pripnejo z zadnjim razpolozljivim letom, ki ni v prihodnosti glede na opazovani teden.

## CatBoost uporaba

Pripravljena sta primera konfiguracij:

- `ml/training/example_tick_borne_lyme_config.json`
- `ml/training/example_tick_borne_kme_config.json`

Ucni split mora ostati casovno urejen po `week_start`. Nakljucni split ni metodolosko primeren.
