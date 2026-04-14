# Model A V2 Methodology

## Core Idea

Model A V1 was learning too much of the seasonal shape directly.
Model A V2 forces a baseline-plus-adjustment structure:

1. baseline = same-month-last-year prevalence
2. residual target = observed prevalence - baseline
3. residual model uses:
   - target-month weather anomalies versus historical month climatology
   - issue month
   - lead month
   - month-of-year encoding
   - baseline context versus previous December and previous Q4

## Validation

- training years: 2017-2024
- final validation year: 2025
- inner alpha selection years: 2023 and 2024

## Important Caveat

Historical validation still relies on observed monthly weather as a proxy for what
historical forecast weather would have been. The future operational run does use the
real Copernicus forecast weather block.
