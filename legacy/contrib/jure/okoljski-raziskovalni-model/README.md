# okoljski_raziskovalni_model

`okoljski_raziskovalni_model` is the validated environmental research baseline for municipality-week tick-borne disease analysis in Slovenia.

Its role is specific:

- identify which environmental factor families matter most for `KME / TBE`, `Lyme / tick borreliosis`, and combined tick-borne burden
- compare national backbone sources against optional local data sources
- provide a reproducible, presentation-ready explanatory baseline before a separate forecasting branch is built

This repository is not the final forward-looking predictive model.

## Canonical Name

The canonical project name is now `okoljski_raziskovalni_model`.

Compatibility note:

- this project previously lived under the working name `environmental_explanation_project`
- some script filenames still keep the older `environment_` prefix for compatibility and auditability
- the repository, documentation, and presentation references should use `okoljski_raziskovalni_model`

## What This Model Does

This branch explains validated environmental signal in municipality-week burden data.

It does this by:

- building a national weekly municipality panel
- excluding disease-history predictors from the main explanatory branch
- using grouped CatBoost ablations to compare environmental factor families
- validating the findings both on development folds and on a reserved `2025` holdout

The core question is:

- which grouped environmental factors are robustly useful for explaining current rolling disease burden?

## What This Model Does Not Do

This branch should not be presented as:

- the final operational forecasting model
- proof of causality
- a future-weather prediction system

It is an explanatory and comparative baseline.

## Repository Structure

This repository now follows a clearer GitHub-ready structure inspired by the reference `GITlookup` project:

```text
okoljski_raziskovalni_model/
|-- data/
|   |-- raw/           # copied source data by provider
|   |-- interim/       # normalized and staged intermediate outputs
|   |-- processed/     # model-ready, evaluation, validation outputs
|   `-- metadata/      # dataset catalog and variable inventory
|-- docs/              # methodology, validity notes, project log
|-- pipelines/         # canonical pipeline entrypoint and pipeline notes
|-- scripts/           # implementation scripts used by the pipeline
`-- tests/             # test and integrity-check notes
```

## Pipeline Entry Point

Canonical entrypoint:

```powershell
py -3 pipelines/run_okoljski_raziskovalni_model.py
```

Compatibility entrypoint:

```powershell
py -3 scripts/run_environment_pipeline.py
```

## Pipeline Stages

1. Normalize local Slovenia datasets.
2. Build the municipality-week master panel.
3. Flag variables for explanatory use.
4. Build the model-ready environmental panel.
5. Run grouped factor ablations.
6. Build explanatory graphs and commentary.
7. Validate development stability and final holdout behavior.

## Data Layout

- [data/README.md](data/README.md)
- [data/raw/README.md](data/raw/README.md)
- [data/interim/README.md](data/interim/README.md)
- [data/processed/README.md](data/processed/README.md)

Key output directories:

- `data/interim/model_staging/`
- `data/processed/model_ready/`
- `data/processed/model_grouped_evaluation/`
- `data/processed/model_validation/`

## Documentation

- [docs/README.md](docs/README.md)
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md)
- [docs/METHODOLOGY_VALIDITY.md](docs/METHODOLOGY_VALIDITY.md)
- [docs/PROJECT_LOG.md](docs/PROJECT_LOG.md)
- [data/interim/Slovenia_local_data_normalized/README_LOCAL_DATA_NORMALIZATION.md](<data/interim/Slovenia_local_data_normalized/README_LOCAL_DATA_NORMALIZATION.md>)

## Current Validated Findings

Development plus reserved-holdout validation currently support these baseline claims:

- `Land Cover` confirms across all three targets
- `Copernicus Humidity` confirms for `Lyme` and combined tick-borne burden
- `Copernicus Precipitation` confirms for `KME` and combined tick-borne burden
- `GOZDIS Humidity` remains only exploratory low-coverage evidence for `Lyme`
- `OBROD Summary` does not confirm on the `2025` holdout because holdout coverage is absent there

## Where To See Scores

Best summary files:

- [data/processed/model_validation/ENVIRONMENT_VALIDATION_REPORT.md](<data/processed/model_validation/ENVIRONMENT_VALIDATION_REPORT.md>)
- [data/processed/model_validation/environment_validation_signal_summary.csv](<data/processed/model_validation/environment_validation_signal_summary.csv>)
- [data/processed/model_validation/environment_holdout_group_scores.csv](<data/processed/model_validation/environment_holdout_group_scores.csv>)
- [data/processed/model_grouped_evaluation/ENVIRONMENT_GROUPED_ABLATION_REPORT.md](<data/processed/model_grouped_evaluation/ENVIRONMENT_GROUPED_ABLATION_REPORT.md>)

## Recommended Usage

Use this repository when you need:

- a clean environmental explanation baseline
- validated presentation graphs for factor-family importance
- a frozen reference point before building a separate future-prediction branch

For forward prediction with Copernicus forecast weather and disease-history features, build a separate predictive branch rather than extending this repository's scientific claims beyond its intended scope.
