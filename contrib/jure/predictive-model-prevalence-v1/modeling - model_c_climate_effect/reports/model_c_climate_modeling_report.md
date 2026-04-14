# Model C Climate-Effect Modeling Report

- generated at: `2026-04-14T07:15:34.899368+00:00`

## Validation Design

- final validation years are `2024` and `2025`
- both scenario-family rows for the same calendar year stay in the same split
- validation is recursive across the held-out years

## Split Summary

- lyme_prevalence: training years `2019, 2020, 2021, 2022, 2023`; final validation years `2024, 2025`
- kme_prevalence: training years `2019, 2020, 2021, 2022, 2023`; final validation years `2024, 2025`
- combined_prevalence: training years `2019, 2020, 2021, 2022, 2023`; final validation years `2024, 2025`

## Alpha Selection

- lyme_prevalence: selected alpha `100.0` from mean inner-fold RMSE `2502.4864`
- kme_prevalence: selected alpha `100.0` from mean inner-fold RMSE `79.4031`
- combined_prevalence: selected alpha `100.0` from mean inner-fold RMSE `2434.9948`

## Final Validation Metrics

- lyme_prevalence weighted_rmse: `1318.3941`
- lyme_prevalence weighted_mae: `1284.4670`
- lyme_prevalence weighted_bias: `268.7452`
- lyme_prevalence weighted_mape_pct: `21.6750`
- kme_prevalence weighted_rmse: `48.4277`
- kme_prevalence weighted_mae: `46.8349`
- kme_prevalence weighted_bias: `46.8349`
- kme_prevalence weighted_mape_pct: `35.0831`
- combined_prevalence weighted_rmse: `1316.9324`
- combined_prevalence weighted_mae: `1271.7734`
- combined_prevalence weighted_bias: `316.1580`
- combined_prevalence weighted_mape_pct: `21.1071`

## Future Coverage

- combined_prevalence / high_emissions: `2026` to `2100` with `75` projected yearly points
- combined_prevalence / medium_emissions: `2026` to `2100` with `75` projected yearly points
- kme_prevalence / high_emissions: `2026` to `2100` with `75` projected yearly points
- kme_prevalence / medium_emissions: `2026` to `2100` with `75` projected yearly points
- lyme_prevalence / high_emissions: `2026` to `2100` with `75` projected yearly points
- lyme_prevalence / medium_emissions: `2026` to `2100` with `75` projected yearly points
