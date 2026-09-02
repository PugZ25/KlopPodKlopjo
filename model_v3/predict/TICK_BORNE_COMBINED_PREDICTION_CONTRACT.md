# Combined Lyme + KME prediction snapshot contract

This snapshot forecasts the **combined reported count of Lyme disease and KME/TBE cases**. The project label “tick-borne diseases” refers only to those two components, not every tick-borne disease.

- Analysis unit: statistical region × issue date.
- Issue date: `2025-12-29`.
- Target window: `2026-01-05` through `2026-02-23` (exactly t+1..t+8).
- Past epidemiological input: `2025-11-03` through `2025-12-22` (exactly t−8..t−1).
- Model: frozen Poisson GLM with seasonality, region, past combined incidence, and population offset.
- Weather: evaluated during development but not selected.
- Predictive intervals: unavailable and therefore null.

The JSON and Parquet outputs are generated from one canonical Arrow table. They contain no observed outcomes, risk scores, categories, probabilities, or personal-risk statements. Because this snapshot was sealed during 2026 for a target window that has already elapsed in calendar time, it is repository-controlled retrospective output, not a fully prospective experiment.
