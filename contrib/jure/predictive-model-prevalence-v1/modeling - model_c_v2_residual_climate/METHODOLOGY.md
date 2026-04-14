# Model C V2 Methodology

## Core Idea

Model C V1 was too close to a direct regression on duplicated scenario-family rows.
Model C V2 changes that:

1. collapse historical scenario rows to one climate-analogue row per year
2. define a baseline prevalence trajectory
3. predict only the climate-driven adjustment around that baseline

## Baseline Strategy

- Lyme: lag-1 yearly prevalence
- Combined: lag-1 yearly prevalence
- KME: rolling 3-year prevalence mean

## Climate Feature Compression

The model uses two compact indices:

- thermal_humidity_index
- wetness_index

These are built from standardized climate anomaly columns using the historical
collapsed years only.
