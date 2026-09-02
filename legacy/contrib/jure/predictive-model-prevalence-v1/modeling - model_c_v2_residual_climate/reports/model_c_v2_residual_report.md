# Model C V2 Residual Climate Report

- generated at: `2026-04-14T12:43:25.303072+00:00`

## Design

- one collapsed historical climate row is used per observed year
- the model predicts climate-driven prevalence adjustment around a baseline trajectory
- future yearly prevalence is generated recursively within each scenario family

## Validation Split

- lyme_prevalence: train years `2019, 2020, 2021, 2022, 2023`; final validation years `2024, 2025`
- kme_prevalence: train years `2019, 2020, 2021, 2022, 2023`; final validation years `2024, 2025`
- combined_prevalence: train years `2019, 2020, 2021, 2022, 2023`; final validation years `2024, 2025`

## Alpha Selection

- lyme_prevalence: selected alpha `10.0` from mean inner-fold RMSE `1136.6846`
- kme_prevalence: selected alpha `10.0` from mean inner-fold RMSE `17.0780`
- combined_prevalence: selected alpha `10.0` from mean inner-fold RMSE `1159.9585`

## Validation Metrics

- lyme_prevalence:
  rmse = `1436.7760`
  mae = `1433.3217`
  bias = `-1433.3217`
  mape_pct = `23.4778`
  baseline_rmse = `3187.5572`
  baseline_mae = `2707.3415`
  baseline_mape_pct = `37.7253`
- kme_prevalence:
  rmse = `83.7346`
  mae = `65.1208`
  bias = `65.1208`
  mape_pct = `50.6317`
  baseline_rmse = `21.2269`
  baseline_mae = `19.1451`
  baseline_mape_pct = `14.5624`
- combined_prevalence:
  rmse = `1414.4914`
  mae = `1405.2201`
  bias = `-1405.2201`
  mape_pct = `22.6906`
  baseline_rmse = `3205.1470`
  baseline_mae = `2737.0078`
  baseline_mape_pct = `37.5254`

## Projection Coverage

- combined_prevalence / high_emissions: `2026` to `2100` with `75` projected yearly points
- combined_prevalence / medium_emissions: `2026` to `2100` with `75` projected yearly points
- kme_prevalence / high_emissions: `2026` to `2100` with `75` projected yearly points
- kme_prevalence / medium_emissions: `2026` to `2100` with `75` projected yearly points
- lyme_prevalence / high_emissions: `2026` to `2100` with `75` projected yearly points
- lyme_prevalence / medium_emissions: `2026` to `2100` with `75` projected yearly points
