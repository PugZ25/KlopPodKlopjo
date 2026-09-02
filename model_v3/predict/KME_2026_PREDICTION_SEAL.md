# Sealed KME 2026 predictions

## Status

**SEALED WITHOUT PIPELINE ACCESS TO 2026 KME OUTCOMES.**

The frozen regional eight-week KME model was fitted once to 6651 eligible 2015–2025 development rows. This stage did not load or create a 2026 KME target and did not parse a 2026 KME outcome.

Because the seal date is during 2026, this is a retrospective/ongoing repository-controlled holdout, not a fully prospective lockbox. Whether any person accessed 2026 outcomes outside this repository pipeline is `UNKNOWN` and cannot be audited from repository state.

## Prediction scope

- Analysis unit: statistical region × issue week.
- Issue period: ISO week-numbering year 2026.
- Horizon: exactly t+1 through t+8, excluding issue week.
- Eligible issue weeks: 45, from 2025-12-29 through 2026-11-02.
- Regions: 12.
- Sealed selected-model predictions: 540.
- Sealed historical-rate baseline predictions: 540.

The final eligible issue date is chosen by date arithmetic so its t+8 week remains in ISO year 2026; no week number is manually assumed.

## Frozen model fit

- Candidate: `glm_seasonal_region_offset`.
- Formula: `log(E[target_kme_cases_next_8w]) = log(region_population/100000) + intercept + annual_sin + annual_cos + statistical_region_fixed_effect`.
- Population is the offset and incidence denominator, not an ordinary feature.
- Fit convergence: true in 7 iterations.
- Parameters: 14; warnings: 0.
- Weather, current/past KME cases, classifications, thresholds and generated predictions are absent from the selected-model design.
- Predictive intervals are unavailable, so interval fields are null rather than fabricated.

## Persistence baseline

The persistence algorithm is sealed, but its later 2026 numeric predictions are not fabricated. It requires reported cases in t−8..t−1, including already-observed 2026 weeks for later issue dates. The immutable rule is stored in `kme_2026_persistence_baseline_contract.json`; each value must be generated sequentially before its future t+1..t+8 outcome window is accessed.

## Canonical outputs

CSV, Parquet and JSON are generated from the same sorted in-memory prediction table. Their hashes and all input, configuration, code and coefficient hashes are recorded in `kme_2026_prediction_seal_manifest.json`.

- CSV: `a7ade5ecca9c22cb3588c7963dff3e0edfc31b2239672b95a23c6d85f7ac0906`
- Parquet: `c3a6e008909e28906458b5fce7e94754b6a13569b0718baa87e4514c4243f19b`
- JSON: `4cbe474593fd55681396520b96a4cb511ad9a892c579fd6b42fa96f43a8f52fd`
- Coefficients: `1263c02735ca074e9c0e087ea0f9b7c81eff390a3df5e4d0639669fa497d8f70`

These are sealed model outputs, not observed performance and not personal-risk estimates.
