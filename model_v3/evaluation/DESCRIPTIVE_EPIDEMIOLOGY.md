# Lyme descriptive epidemiology

## Scope and period

This stage produces descriptive summaries only. It does not train a model, evaluate predictions, select features or hyperparameters, perform calibration, or make causal interpretations.

The configured descriptive period is 2016–2024. The year assigned to a case row is the Gregorian calendar year containing its Monday `issue_week`. This matches the rolling-origin validation policy. Week-of-year summaries use the canonical ISO week number. The 2025 lockbox is excluded from every table and plot. Each temporal loader parses only the row date or year needed for cutoff selection, then skips lockbox rows before parsing municipality, case, population, calendar-value, or target-value fields.

Reproduce from the repository root:

```bash
./.venv/bin/python -B -m model_v3.evaluation.descriptive_epidemiology \
  --config model_v3/config/lyme_descriptive_epidemiology.json
```

All outputs are written beneath `model_v3/outputs/descriptive/`. CSV is used to avoid adding a Parquet dependency; SVG diagnostic plots are produced with the Python standard library.

## Incidence definition

Municipality-year Lyme incidence per 100,000 is calculated only when the SURS population denominator is present and greater than zero:

```text
incidence_per_100000
  = reported_lyme_cases_during_issue_year
  / population_total_on_1_january_of_that_year
  × 100,000
```

The numerator is the sum of canonical weekly `lyme_cases` for a municipality in the stated issue year. The denominator is canonical SURS `Population - Total - 1 January` for the same municipality and year. Missing or nonpositive population produces a missing incidence value and an explicit denominator status. Incidence is not labelled or interpreted as risk.

Annual aggregate incidence uses only municipality-year rows with valid denominators. Its numerator and denominator columns make any excluded municipality-year rows explicit.

## Output tables

| Output | Unit or grouping | Main contents |
|---|---|---|
| `lyme_cases_by_year.csv` | issue year | Reported cases and observed municipality-week counts. |
| `lyme_cases_by_iso_week.csv` | ISO week-of-year | Reported cases aggregated across the development period, with observed-week counts. |
| `lyme_cases_by_municipality.csv` | municipality | Reported cases across the development period. |
| `population_by_municipality_year.csv` | municipality × year | Population denominator and validity status. |
| `lyme_incidence_by_municipality_year.csv` | municipality × issue year | Case numerator, population denominator and incidence per 100,000. |
| `lyme_incidence_by_year.csv` | issue year | Aggregate valid-denominator numerator, denominator and incidence per 100,000. |
| `lyme_zero_case_proportion.csv` | issue year plus overall | Zero-case municipality-week numerator, observed municipality-week denominator and proportion. |
| `lyme_next_4w_target_distribution.csv` | target count | Frequency and cumulative distribution among target-complete development rows whose windows end before 2025. |
| `missing_data_summary.csv` | dataset × column | Missing counts and proportions for the development-period inputs. |
| `supervised_row_summary.csv` | development period | Candidate, target-complete, lockbox-excluded and usable supervised row counts. |

## Diagnostic plots

Each SVG states its numerator, denominator and period in the plot itself:

- annual reported Lyme case counts;
- annual reported Lyme incidence per 100,000;
- empirical cumulative distribution of the next-four-week Lyme target.

The plots are descriptive diagnostics only and contain no causal claims or model performance.
