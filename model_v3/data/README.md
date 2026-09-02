# Canonical epidemiological data layer

This stage creates four analytical datasets from active raw source files. It creates no target, feature, weather variable, environmental variable, or model input.

## Reproduce

From the repository root, using the existing project environment:

```bash
./.venv/bin/python -m model_v3.data.canonical_epidemiology \
  --config model_v3/config/canonical_epidemiology.json
```

Inputs and outputs are declared in `model_v3/config/canonical_epidemiology.json`. The builder validates schemas before writing and creates `data_quality_summary.json` with input hashes, output hashes, row counts, missingness, joins, duplicate checks, week checks, and unresolved meanings.

CSV is used because the current project environment has neither `pyarrow` nor `fastparquet`. Empty population fields represent missing population values; numeric zero is written as `0`. Under the user-confirmed NIJZ source rule, blank weekly case cells mean zero. SURS null population values remain missing.

## Canonical datasets

| Dataset | Columns | Primary key | Meaning |
|---|---|---|---|
| `municipality.csv` | `municipality_code`, `municipality_name` | `municipality_code` | Current municipality dimension from the GURS source file. |
| `population.csv` | `municipality_code`, `year`, `population` | `municipality_code`, `year` | SURS population total on 1 January. Null source values remain missing. |
| `weekly_cases.csv` | `municipality_code`, `issue_week`, `lyme_cases`, `kme_cases` | `municipality_code`, `issue_week` | Numeric weekly cells from the two disease workbooks. Blank cells remain missing. |
| `calendar.csv` | `issue_week`, `year`, `iso_week` | `issue_week` | ISO-week calendar derived from canonical Monday dates. `year` is the ISO week-numbering year. |

`municipality_code` is a three-character string. Numeric GURS codes are zero-padded to match the three-character SURS code representation. `issue_week` is the Monday obtained from the source `YYYY-WW` token with ISO calendar conversion.

## Source-to-canonical mapping

| Source column or location | Canonical column | Meaning | Transformation |
|---|---|---|---|
| GURS GeoJSON `features[].properties.SIFRA` | `municipality.municipality_code` | Municipality code in the documented GURS municipality layer. | Validate as an integer code and format as a three-character string with leading zeroes. |
| GURS GeoJSON `features[].properties.NAZIV` | `municipality.municipality_name` | Municipality name in the documented GURS municipality layer. | Preserve text after Unicode NFC and surrounding-whitespace normalization. |
| SURS JSON-stat2 `dimension.MERITVE`, category `45` | selection only | `Population - Total - 1 January`, as stated by the source label and active SURS documentation. | Require code `45` and its exact documented label. |
| SURS JSON-stat2 `dimension.OBČINE` category key | `population.municipality_code` | Municipality code. | Preserve the three-digit code and join to `municipality` by code. |
| SURS JSON-stat2 `dimension.LETO` category key | `population.year` | Calendar year of the SURS annual observation. | Validate a four-digit integer year. |
| SURS JSON-stat2 flattened `value` at measure × municipality × year | `population.population` | Population total on 1 January. | Decode in JSON-stat2 dimension order; preserve null; require non-negative integer when present. |
| NIJZ workbook sheet name and row-1 `YYYY-WW` cell | `weekly_cases.issue_week` | Canonical issue week corresponding to the source year-week token. | Require sheet year and token year to match, validate the token as an ISO week, and convert it to ISO Monday. |
| NIJZ row-1 column B `Občina bivališča /Obolenja po tednih` and municipality row label | `weekly_cases.municipality_code` | Source municipality-of-residence label used only to obtain a code. | Unicode NFC, whitespace, and case normalization for lookup against GURS names; use the two explicit aliases below; all subsequent joins use code. |
| Cell in `lyme_2015_2025_student.xlsx` under a week header | `weekly_cases.lyme_cases` | Lyme case count indicated by the repository source path and filename. Reporting-status semantics are `UNKNOWN`. | Preserve a present non-negative integer. Convert a blank cell to `0` under the user-confirmed project rule. |
| Cell in `KME_2015_2025_student.xlsx` under a week header | `weekly_cases.kme_cases` | KME case count indicated by the repository source path and filename. Reporting-status semantics are `UNKNOWN`. | Preserve a present non-negative integer. Convert a blank cell to `0` under the user-confirmed project rule. |
| NIJZ `SKUPAJ` column and row | none | Source aggregate label. | Exclude from canonical rows and use only to validate numeric source totals. |
| `weekly_cases.issue_week` | `calendar.issue_week` | Canonical ISO Monday. | Select unique dates and sort. |
| `calendar.issue_week` | `calendar.year` | ISO week-numbering year. | Derive with `date.isocalendar().year`. |
| `calendar.issue_week` | `calendar.iso_week` | ISO week number. | Derive with `date.isocalendar().week`. |

Explicit NIJZ name mappings, verified against unique GURS and SURS code/name entries:

| NIJZ source name | Municipality code | Canonical GURS name |
|---|---:|---|
| `SV. TROJICA V SLOV. GORICAH` | `204` | `Sveta Trojica v Slovenskih goricah` |
| `SVETI JURIJ V SLOV. GORICAH` | `210` | `Sveti Jurij v Slovenskih goricah` |

## Missing and unknown semantics

- NIJZ workbook blank case cells mean zero under the user-confirmed project rule. Source blanks and source-explicit zeroes are counted separately in the quality summary, while both become canonical `0`.
- The NIJZ workbooks contain no embedded title, description, source URL, or reporting-status definition. Their external provenance beyond the active repository raw-source classification is `UNKNOWN`.
- The workbooks' complete year-week coverage, including ISO week 53 in 2015 and 2020, is validated before ISO conversion.
- A source `SKUPAJ` aggregate that differs from the numeric municipality-row sum has `UNKNOWN` meaning. The discrepancy is reported as a warning; canonical municipality cells are not redistributed, imputed, or changed.
- SURS null values and raw JSON-stat status markers are preserved and reported without interpreting the marker meaning.
