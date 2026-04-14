# Methodology

This document describes the methodology used by `okoljski_raziskovalni_model`.

## Goal

The purpose of `okoljski_raziskovalni_model` is to identify which environmental factors and which data sources best explain municipality-level weekly burden of:

- combined tick-borne disease burden
- `KME / TBE`
- `Lyme / tick borreliosis`

This repository is not the main forecasting branch.

## Why A Separate Branch Was Needed

The earlier workflow mixed two ideas:

- forecasting future burden
- explaining environmental factors

Those goals overlap, but they are not the same.

The explanatory baseline therefore changes the design in three key ways:

1.  It uses date-aligned disease targets rather than future targets.
2.  It removes disease-history predictors from the main explanatory model.
3.  It keeps environmental lag structure because incubation and reporting delay make earlier environmental exposure biologically relevant.

## Unit Of Analysis

Each row is one:

- municipality
- week

All source data are aligned to this panel.

## Targets

The environmental branch uses rolling current burden targets:

- `tickborne_current4w_per100k`
  - rolling 4-week combined tick-borne burden ending at the row week
- `lyme_current4w_per100k`
  - rolling 4-week Lyme burden ending at the row week
- `kme_current8w_per100k`
  - rolling 8-week KME burden ending at the row week

These choices were made because weekly counts, especially for `KME`, are sparse and noisy.

## Predictors

The main explanatory predictors are:

- hidden annual-phase control derived from `week_start`
- `Copernicus` temperature
- `Copernicus` humidity
- `Copernicus` precipitation
- `Copernicus` soil
- `Copernicus` land cover
- `Copernicus` topography
- `Copernicus` population context
- `ARSO` local temperature
- `ARSO` local humidity
- `ARSO` local precipitation
- `GOZDIS` local temperature
- `GOZDIS` local humidity
- `GOZDIS` local precipitation
- `OBROD` forestry summary

Not used as explanatory predictors in this branch:

- past disease-count lags
- current disease counts
- raw calendar fields such as month and ISO week
- Copernicus tick-activity proxy columns
- source-construction metadata
- sparse `OBROD` species-detail columns

The raw Copernicus source files are kept for provenance, but the tick-activity proxy block is removed immediately when the standalone master panel is built.

## Lag Logic

Environmental lags are allowed because disease outcomes can reflect earlier exposures rather than only same-week conditions.

This branch therefore keeps or derives lagged environmental features, especially for dynamic weather sources.

## Validation Reservation

The project reserves `2025` as an untouched validation year.

Split policy:

- `2016-2020`: historical training-only
- `2021-2024`: development backtesting
- `2025`: final holdout

This is frozen before the environmental models are tuned.

## Model Family

The grouped evaluation currently uses `CatBoost`.

Why:

- good performance on structured tabular data
- robust handling of missing values
- suitable for mixed numeric/categorical inputs

The model is used here as a tool for comparing grouped factor usefulness, not as proof of causality.

## Validation Logic

Validation in this branch happens in two layers.

First, the grouped-ablation development folds already test multiple model variants across `2021-2024`.

That tells us whether a factor family looks useful repeatedly, not just in one lucky year.

Second, a reserved `2025` holdout check retrains each variant on all pre-2025 eligible rows and evaluates it once on the untouched holdout year.

Important rule:

- the holdout stage freezes model complexity from development by using each variant's mean development `best_iteration`
- the holdout year is therefore not used for early stopping or hyperparameter tuning

This means we are validating both:

- the reference environmental model itself
- the conclusions from the grouped ablation comparisons

## Grouped Evaluation Logic

The grouped evaluation compares whole factor families instead of only individual variables.

Core environmental groups:

- `copernicus_temperature`
- `copernicus_humidity`
- `copernicus_precipitation`
- `copernicus_soil`
- `topography`
- `land_cover`
- `population`

Local source groups:

- `arso_temperature`
- `arso_humidity`
- `arso_precipitation`
- `gozdis_temperature`
- `gozdis_humidity`
- `gozdis_precipitation`
- `obrod_summary`

Hidden control:

- `time_control_hidden`

The hidden control is present in every scored variant, but it is not ranked as a main explanatory factor.

Interpretation rule:

- positive score for a local group means adding it helped
- positive score for a core group means removing it hurt performance, so the group was useful

## Important Interpretation Cautions

- strong importance does not imply causality
- the hidden annual-phase control is a nuisance control, not by itself an ecological mechanism
- splitting weather into smaller groups improves interpretation, but overlapping weather families can still share signal
- low-coverage local sources must be interpreted together with coverage
- negative score for a weather block may indicate redundancy or noisy representation, not that weather is biologically irrelevant
