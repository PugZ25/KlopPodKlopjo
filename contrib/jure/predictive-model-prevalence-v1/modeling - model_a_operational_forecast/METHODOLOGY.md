# Model A Methodology

## Important Constraint

Model A does not yet have a full historical hindcast weather block for humidity,
precipitation, and soil under the same reproducible acquisition path as the future files.

Because of that, the first-pass Model A validation uses:

- observed historical monthly weather as a proxy for what forecast weather would have been
- a fixed latest-observed disease anchor across the January-to-April operational issue window

That matches the current future forecast table, where `latest_observed_month_available`
is fixed at `2025-12-01`.

## Operational Window

The first-pass operational line uses the latest available issue for each target month from:

- January 2026 issue
- February 2026 issue
- March 2026 issue
- April 2026 issue

This yields one canonical forecast point per target month for:

- February 2026 through October 2026

## Validation Design

- final holdout year: 2025
- validation months: February through October 2025, using the same latest-issue structure
- inner alpha selection years: 2023 and 2024

## First-Pass Feature Block

- target-month weather block: temperature, humidity, precipitation, soil temperature level 1
- target-month seasonal encoding
- issue month and lead month
- December prevalence anchor from the previous year
- previous-year Q4 prevalence mean
- same-month previous-year prevalence

This is a practical first-pass operational design, not yet the final forecast-validation design.
