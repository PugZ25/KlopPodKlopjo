# Reproducible Acquisition Methodology

## Why This Folder Exists

The early acquisition phase produced useful outputs, but the active project needed a
clean, portable, self-contained copy of the downloader logic.

## Design Principles

- no dependency on the main project scripts
- all outputs stay under local `output/`
- both acquisition branches can be copied elsewhere and still run
- request manifests and run summaries are recorded for reproducibility

## Branches

- Model A downloader
  - Slovenia seasonal forecast weather
- Model C downloader
  - Slovenia climate Atlas scenario data

## Validation Rule

Before any cleanup of older exploratory acquisition artifacts, this folder must validate
successfully using `validate_pipelines.py`.
