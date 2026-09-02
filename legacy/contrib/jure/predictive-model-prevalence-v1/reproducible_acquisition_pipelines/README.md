# Reproducible Acquisition Pipelines

This folder is a clean duplicate of the raw data acquisition layer for the predictive
project. It exists so the Model A and Model C download workflows can be copied,
rerun, and modified without touching the current predictive project outputs.

## Goal

- keep one self-contained folder that can be copied elsewhere and still run
- stage duplicate downloads inside this folder first
- validate the duplicate pipelines before deleting any older exploratory scripts,
  probes, or messy reports from the main predictive project
- separate the two active acquisition targets clearly:
  - Model A: Slovenia operational seasonal forecasts
  - Model C: Slovenia climate-effect Atlas projections

## Folder Design

- `common.py`
  - shared utilities, timestamps, output roots, Slovenia bbox, proxy cleanup
- `model_a_forecast/`
  - self-contained Model A downloader and methodology README
- `model_c_climate/`
  - self-contained Model C downloader and methodology README
- `output/`
  - local staged outputs written by these duplicate pipelines
- `validate_pipelines.py`
  - dry-run validation for both duplicate pipelines
- `requirements.txt`
  - minimal runtime dependency list
- `CLEANUP_CANDIDATES.md`
  - items that are likely removable later, but are not deleted yet

## Reproducibility Rules

- both pipelines use only relative paths inside this folder
- both pipelines write their raw files and reports under local `output/`
- both pipelines record request manifests and per-run reports
- the only external requirement is CDS credentials and accepted licences
- if you copy this whole folder somewhere else, the scripts still run because they
  do not depend on `Predikcijski model prevalence V1/scripts/`

## Credentials

The pipelines rely on the Copernicus CDS API credentials already configured on the
machine. Either of these is acceptable:

- `~/.cdsapirc`
- `CDSAPI_URL` and `CDSAPI_KEY` environment variables

If proxy environment variables point at a dead local proxy, use `--clear-proxy-env`.

## Validation

Dry-run validation for both pipelines:

```powershell
py -3 validate_pipelines.py
```

## Staged Output Layout

- `output/model_a/raw/`
  - duplicate seasonal forecast downloads
- `output/model_a/reports/`
  - Model A run reports
- `output/model_c/raw/`
  - duplicate climate Atlas downloads
- `output/model_c/reports/`
  - Model C run reports
- `output/validation/`
  - dry-run validation reports

## Later Cleanup Policy

Do not delete anything from the main predictive project until:

1. the duplicate pipelines validate cleanly
2. the staged duplicate outputs are inspected
3. we agree which old exploratory assets are actually redundant

That removal step is intentionally deferred.
