# KME descriptive feasibility analysis

## Scope and definitions

This is the reproducible descriptive design analysis behind the implemented KME pipeline. It uses canonical `kme_cases`, calendar data, and the verified municipality-to-statistical-region mapping. The modelling code and target are separate stages, and the KME horizon is not copied from Lyme.

The source covers 2015 through 2025: 574 consecutive canonical ISO weeks for 212 fixed municipality zones. Year summaries use the ISO week-numbering year, so dates such as 2014-12-29 are correctly assigned to ISO year 2015.

For feasibility only, an H-week candidate outcome is the sum in every complete consecutive observed H-week interval, including its window start, with one-week stride. These overlapping windows are not an implemented forecast target and do not decide whether a later target includes or excludes an issue week.

## Overall sparsity

- Total observed KME cases: **1120**.
- Municipality-weeks: **121688**.
- Municipality-weeks with zero cases: **120642 (99.140%)**.
- Municipality-weeks with one or more cases: **1046 (0.860%)**.
- Municipalities with at least one observed case: **151 of 212**.
- Municipalities with no observed case in the entire source period: **61 of 212**.

## Cases by year

| ISO year | Observed weeks | KME cases | Non-zero municipality-weeks |
|---|---|---|---|
| 2015 | 53 | 62 | 60 |
| 2016 | 52 | 83 | 82 |
| 2017 | 52 | 102 | 95 |
| 2018 | 52 | 153 | 140 |
| 2019 | 52 | 111 | 102 |
| 2020 | 53 | 187 | 168 |
| 2021 | 52 | 62 | 61 |
| 2022 | 52 | 126 | 114 |
| 2023 | 52 | 63 | 58 |
| 2024 | 52 | 91 | 88 |
| 2025 | 52 | 80 | 78 |

## Cases by municipality

The complete 212-row municipality table is written to `model_v3/outputs/kme_feasibility/kme_cases_by_municipality.csv`. The ten municipalities with the largest observed totals are shown below; this is descriptive ranking, not risk.

| Code | Municipality | Total KME cases | Non-zero weeks |
|---|---|---|---|
| 061 | Ljubljana | 83 | 68 |
| 052 | Kranj | 51 | 42 |
| 043 | Kamnik | 42 | 34 |
| 112 | Slovenj Gradec | 39 | 35 |
| 027 | Gorenja vas-Poljane | 29 | 26 |
| 064 | Logatec | 29 | 29 |
| 070 | Maribor | 29 | 27 |
| 122 | Škofja Loka | 25 | 23 |
| 013 | Cerknica | 24 | 23 |
| 113 | Slovenska Bistrica | 24 | 22 |

## Cases by statistical region

Mapping status: **verified**. Source: **SURS_NUTS3_SKTE5_7_2022**, valid from **2022-11-17**. Joins use municipality code. The verified 2022 municipality-to-statistical-region mapping is used as a fixed analytical geography for every observed year; no historical-boundary reconstruction is claimed.

| Code | Statistical region | Total KME cases | Non-zero weeks | Zero weeks % |
|---|---|---|---|---|
| 01 | POMURSKA STATISTIČNA REGIJA | 39 | 37 | 93.554 |
| 02 | PODRAVSKA STATISTIČNA REGIJA | 106 | 90 | 84.321 |
| 03 | KOROŠKA STATISTIČNA REGIJA | 107 | 79 | 86.237 |
| 04 | SAVINJSKA STATISTIČNA REGIJA | 78 | 59 | 89.721 |
| 05 | ZASAVSKA STATISTIČNA REGIJA | 13 | 13 | 97.735 |
| 06 | POSAVSKA STATISTIČNA REGIJA | 7 | 7 | 98.780 |
| 07 | JUGOVZHODNA SLOVENIJA | 73 | 57 | 90.070 |
| 08 | OSREDNJESLOVENSKA STATISTIČNA REGIJA | 317 | 177 | 69.164 |
| 09 | GORENJSKA STATISTIČNA REGIJA | 236 | 142 | 75.261 |
| 10 | PRIMORSKO-NOTRANJSKA STATISTIČNA REGIJA | 85 | 66 | 88.502 |
| 11 | GORIŠKA STATISTIČNA REGIJA | 51 | 46 | 91.986 |
| 12 | OBALNO-KRAŠKA STATISTIČNA REGIJA | 8 | 8 | 98.606 |

## Candidate window distributions

| Unit | Horizon | Zero % | Non-zero | Median | P95 | P99 | Maximum |
|---|---|---|---|---|---|---|---|
| municipality | 4 weeks | 96.929 | 3717 | 0 | 0 | 1 | 6 |
| municipality | 8 weeks | 94.395 | 6738 | 0 | 1 | 2 | 11 |
| municipality | 12 weeks | 92.062 | 9474 | 0 | 1 | 2 | 13 |
| statistical_region | 4 weeks | 71.220 | 1972 | 0 | 3 | 8 | 17 |
| statistical_region | 8 weeks | 58.319 | 2836 | 0 | 6 | 14 | 28 |

The full integer-count histograms for 4, 8, and 12 weeks are in `kme_window_count_distribution.csv`.

## Candidate design comparison

| Design | Unit | Horizon | Candidate windows | Non-zero | Non-zero % | Anchored non-overlap blocks | Non-zero blocks | Status |
|---|---|---|---|---|---|---|---|---|
| A | municipality | 4 weeks | 121052 | 3717 | 3.071 | 30316 | 934 | descriptive_feasibility_computed |
| B | municipality | 8 weeks | 120204 | 6738 | 5.605 | 15052 | 845 | descriptive_feasibility_computed |
| C | municipality | 12 weeks | 119356 | 9474 | 7.938 | 9964 | 797 | descriptive_feasibility_computed |
| D | statistical_region | 4 weeks | 6852 | 1972 | 28.780 | 1716 | 495 | descriptive_feasibility_computed |
| E | statistical_region | 8 weeks | 6804 | 2836 | 41.681 | 852 | 354 | descriptive_feasibility_computed |

Raw rolling rows are not effective sample sizes: adjacent windows overlap by 75.0%, 87.5%, and 91.7% for 4, 8, and 12 weeks, respectively, and municipalities share calendar time. Effective sample size is therefore **UNKNOWN** until a dependence structure and evaluation design are specified. Anchored non-overlapping blocks are shown only as a support diagnostic; they are not asserted to be independent.

Longer windows increase the fraction containing at least one case, but they reduce distinct temporal blocks and temporal resolution. Region aggregation materially reduces zeros relative to municipality-level windows, but it does not create additional cases or independent observations.

## Selected design

**statistical_region_x_8_week_outcome_window** (`design E`). Status: **approved_by_user_instruction_and_implemented**.

Reason: Regional aggregation materially reduces structural zeros. Eight weeks provides more event-bearing windows than four weeks while preserving twice as many anchored non-overlapping temporal blocks as twelve weeks.

The implemented forecast target is reported regional KME cases in exactly `t+1..t+8`, excluding the issue week. Since 2015-2025 outcomes informed this design, those years are development evidence and must not be presented as an untouched KME lockbox; a future KME lockbox must begin after 2025.
