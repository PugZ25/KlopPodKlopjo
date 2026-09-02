# Model A V2 Residual Forecast Report

- generated at: `2026-04-14T12:43:24.945625+00:00`

## Design

- baseline = same-month-last-year prevalence
- model predicts residual adjustment around that baseline
- weather inputs enter as month-climatology anomalies rather than only raw values

## Validation Split

- lyme_prevalence: train years `2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024`; final validation year `2025`
- kme_prevalence: train years `2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024`; final validation year `2025`
- combined_prevalence: train years `2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024`; final validation year `2025`

## Alpha Selection

- lyme_prevalence: selected alpha `100.0` from mean inner-fold RMSE `247.5360`
- kme_prevalence: selected alpha `100.0` from mean inner-fold RMSE `10.8517`
- combined_prevalence: selected alpha `100.0` from mean inner-fold RMSE `256.3445`

## Validation Metrics

- lyme_prevalence:
  rmse = `371.5763`
  mae = `291.6420`
  bias = `-206.7156`
  mape_pct = `45.3460`
  baseline_rmse = `401.4531`
  baseline_mae = `295.1033`
  baseline_mape_pct = `32.5717`
- kme_prevalence:
  rmse = `5.0476`
  mae = `4.4984`
  bias = `2.5704`
  mape_pct = `101.3043`
  baseline_rmse = `3.9913`
  baseline_mae = `2.9338`
  baseline_mape_pct = `79.6196`
- combined_prevalence:
  rmse = `371.8364`
  mae = `293.0326`
  bias = `-204.2413`
  mape_pct = `45.8245`
  baseline_rmse = `401.6667`
  baseline_mae = `296.7476`
  baseline_mape_pct = `33.1180`

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
