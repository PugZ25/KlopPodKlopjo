# Model C Methodology

## Why Reserve Validation Data

Yes, Model C needs reserved validation data before final fitting.

The yearly observed window is short, only 2016-2025, and the calibration table contains
two scenario-family rows per observed year. Because of that:

- validation must be reserved by calendar year, not by individual row
- otherwise the same observed target year would leak into both train and validation

## Validation Design

- final validation years: 2024 and 2025
- grouped rule: both scenario-family rows for a held-out year stay together in validation
- validation mode: recursive, so 2025 predictions depend on the 2024 prediction rather
  than the observed 2024 target

This is closer to the real future rollout.

## First-Pass Feature Block

The first-pass Model C prevalence models use a compact feature set to avoid overfitting:

- yearly climate temperature mean
- yearly climate near-surface specific humidity
- yearly climate precipitation proxy
- yearly climate upper-soil moisture proxy
- scenario-family indicator
- target lag 1 year
- target rolling mean over the previous 3 years

The longer lag block already exists in the calibration table, but the compact block is
safer for the first fit because the observed window is small.

## Output Style

The model output focus is prevalence per 100k, because the requested downstream product
is a graphable past-to-future disease-prevalence trajectory.
