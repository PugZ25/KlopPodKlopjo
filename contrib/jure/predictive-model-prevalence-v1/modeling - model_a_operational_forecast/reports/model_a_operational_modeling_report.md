# Model A Operational Forecast Modeling Report

- generated at: `2026-04-14T08:21:10.762596+00:00`

## Important Caveat

- historical validation still uses observed monthly weather as a proxy for historical forecast weather
- the future operational outlook does use the real Copernicus forecast weather block

## Validation Structure

- lyme_prevalence: train target years `2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024`; final validation year `2025`
- kme_prevalence: train target years `2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024`; final validation year `2025`
- combined_prevalence: train target years `2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024`; final validation year `2025`

## Alpha Selection

- lyme_prevalence: selected alpha `100.0` from mean inner-fold RMSE `473.0033`
- kme_prevalence: selected alpha `1.0` from mean inner-fold RMSE `8.6387`
- combined_prevalence: selected alpha `100.0` from mean inner-fold RMSE `477.1894`

## Final Validation Metrics

- lyme_prevalence rmse: `290.3737`
- lyme_prevalence mae: `228.9771`
- lyme_prevalence bias: `-107.0731`
- lyme_prevalence mape_pct: `51.4316`
- kme_prevalence rmse: `12.6136`
- kme_prevalence mae: `9.9331`
- kme_prevalence bias: `8.6301`
- kme_prevalence mape_pct: `166.1708`
- combined_prevalence rmse: `290.8938`
- combined_prevalence mae: `227.7867`
- combined_prevalence bias: `-104.1172`
- combined_prevalence mape_pct: `51.4666`

## Operational Coverage

- lyme_prevalence: target `2026-02-01` from issue `2026-01-01`
- lyme_prevalence: target `2026-03-01` from issue `2026-02-01`
- lyme_prevalence: target `2026-04-01` from issue `2026-03-01`
- lyme_prevalence: target `2026-05-01` from issue `2026-04-01`
- lyme_prevalence: target `2026-06-01` from issue `2026-04-01`
- lyme_prevalence: target `2026-07-01` from issue `2026-04-01`
- lyme_prevalence: target `2026-08-01` from issue `2026-04-01`
- lyme_prevalence: target `2026-09-01` from issue `2026-04-01`
- lyme_prevalence: target `2026-10-01` from issue `2026-04-01`
- kme_prevalence: target `2026-02-01` from issue `2026-01-01`
- kme_prevalence: target `2026-03-01` from issue `2026-02-01`
- kme_prevalence: target `2026-04-01` from issue `2026-03-01`
- kme_prevalence: target `2026-05-01` from issue `2026-04-01`
- kme_prevalence: target `2026-06-01` from issue `2026-04-01`
- kme_prevalence: target `2026-07-01` from issue `2026-04-01`
- kme_prevalence: target `2026-08-01` from issue `2026-04-01`
- kme_prevalence: target `2026-09-01` from issue `2026-04-01`
- kme_prevalence: target `2026-10-01` from issue `2026-04-01`
- combined_prevalence: target `2026-02-01` from issue `2026-01-01`
- combined_prevalence: target `2026-03-01` from issue `2026-02-01`
- combined_prevalence: target `2026-04-01` from issue `2026-03-01`
- combined_prevalence: target `2026-05-01` from issue `2026-04-01`
- combined_prevalence: target `2026-06-01` from issue `2026-04-01`
- combined_prevalence: target `2026-07-01` from issue `2026-04-01`
- combined_prevalence: target `2026-08-01` from issue `2026-04-01`
- combined_prevalence: target `2026-09-01` from issue `2026-04-01`
- combined_prevalence: target `2026-10-01` from issue `2026-04-01`
