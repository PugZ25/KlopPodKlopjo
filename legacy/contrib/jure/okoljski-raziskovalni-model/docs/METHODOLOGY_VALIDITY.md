# Methodology Validity Review

## Purpose

This note explains why `okoljski_raziskovalni_model` is considered a valid explanatory baseline and where its limits are.

## Why The Baseline Is Methodologically Acceptable

The current branch is methodologically acceptable for environmental factor comparison because:

- it uses a clear `municipality x week` unit of analysis
- it keeps the outcome definition explicit through rolling current-burden targets
- it removes disease-history predictors from the main explanatory branch
- it excludes municipality identity from the explanatory ranking
- it avoids ranking raw calendar fields directly and replaces them with a hidden annual-phase control
- it removes the Copernicus tick-activity proxy block that previously blurred the interpretation
- it reserves `2025` as an untouched holdout year before final validation
- it validates grouped findings both across development folds and on the reserved holdout

## What The Baseline Validly Supports

This baseline validly supports statements such as:

- which grouped environmental factor families are most useful in the cleaned KME explanation branch
- which signals are stable across development years
- which findings survive an untouched holdout year
- which local sources should be treated as exploratory because their coverage is weak

## What The Baseline Does Not Validly Support

This baseline should not be used as proof of:

- direct biological causality
- final operational outbreak forecasting quality
- the best possible predictive model architecture
- source superiority without considering coverage constraints

## Important Limitation

Holdout `Spearman` values in the reference models remain weak or negative.

Interpretation:

- the branch is stronger as an explanatory grouped-comparison framework than as a polished ranking-based forecasting system
- this does not invalidate the grouped factor findings
- it does mean a separate predictive branch should be built for future-risk forecasting

## Coverage Rule For Local Sources

Local-source findings must always be read with coverage:

- `exploratory_low_coverage`
  around single-digit percent coverage and not strong enough for broad claims
- `partial_local_coverage`
  meaningful but still clearly subnational
- `moderate_subnational_coverage`
  useful evidence but not a national source
- `national_coverage`
  broad enough to support stronger comparison claims

## Freeze Decision

The current repository is appropriate to freeze as:

- the validated explanatory baseline for environmental factor comparison

It is not appropriate to freeze as:

- the final predictive modeling solution
