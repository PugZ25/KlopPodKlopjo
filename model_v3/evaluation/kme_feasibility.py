from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "kme_feasibility.json"

YEAR_COLUMNS = (
    "iso_year",
    "n_observed_weeks",
    "total_kme_cases",
    "n_nonzero_municipality_weeks",
)
MUNICIPALITY_COLUMNS = (
    "municipality_code",
    "municipality_name",
    "total_kme_cases",
    "n_observed_weeks",
    "n_nonzero_weeks",
    "fraction_zero_weeks",
)
REGION_COLUMNS = (
    "statistical_region_code",
    "statistical_region_name",
    "total_kme_cases",
    "n_observed_weeks",
    "n_nonzero_weeks",
    "fraction_zero_weeks",
)
WINDOW_DISTRIBUTION_COLUMNS = (
    "analysis_level",
    "horizon_weeks",
    "window_case_count",
    "n_rolling_windows",
    "fraction_of_rolling_windows",
)
DESIGN_COLUMNS = (
    "design_id",
    "analysis_level",
    "horizon_weeks",
    "status",
    "candidate_target_definition",
    "n_units",
    "n_observed_weeks",
    "n_unique_rolling_window_starts",
    "n_candidate_targets",
    "n_nonzero_candidate_targets",
    "fraction_nonzero_candidate_targets",
    "median_candidate_target_count",
    "p95_candidate_target_count",
    "p99_candidate_target_count",
    "maximum_candidate_target_count",
    "rolling_window_overlap_fraction",
    "n_anchored_nonoverlap_blocks",
    "n_nonzero_anchored_nonoverlap_blocks",
    "fraction_nonzero_anchored_nonoverlap_blocks",
    "n_units_with_any_observed_case",
    "n_units_without_any_observed_case",
    "effective_sample_size",
    "effective_sample_size_status",
    "limitation",
)


class KmeFeasibilityError(ValueError):
    """Raised when canonical KME feasibility inputs or outputs are invalid."""


@dataclass(frozen=True)
class CanonicalKmeData:
    municipalities: Mapping[str, str]
    statistical_regions: Mapping[str, str]
    region_by_municipality: Mapping[str, str]
    weeks: tuple[date, ...]
    iso_year_by_week: Mapping[date, int]
    cases_by_municipality: Mapping[str, tuple[int, ...]]
    cases_by_statistical_region: Mapping[str, tuple[int, ...]]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_repo_path(path_value: str | Path, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repo_root / path


def repository_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("schema_version") != 1:
        raise KmeFeasibilityError("Unsupported KME feasibility schema_version")
    horizons = config.get("descriptive_windows", {}).get("horizons_weeks")
    if horizons != [4, 8, 12]:
        raise KmeFeasibilityError("KME feasibility horizons must be exactly 4, 8, and 12")
    return config


def require_file_hash(path: Path, expected_sha256: str, label: str) -> str:
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise KmeFeasibilityError(
            f"{label} SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    return actual_sha256


def parse_iso_date(value: str, label: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise KmeFeasibilityError(f"Invalid {label}: {value!r}") from exc
    if parsed.weekday() != 0:
        raise KmeFeasibilityError(f"{label} must be a canonical Monday: {value!r}")
    return parsed


def read_municipalities(path: Path, expected_count: int) -> dict[str, str]:
    required = {"municipality_code", "municipality_name"}
    result: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeFeasibilityError("Canonical municipality schema is invalid")
        for row in reader:
            code = row["municipality_code"]
            name = row["municipality_name"]
            if not code or not name:
                raise KmeFeasibilityError("Municipality code and name must be present")
            if code in result:
                raise KmeFeasibilityError(f"Duplicate municipality code: {code}")
            result[code] = name
    if len(result) != expected_count:
        raise KmeFeasibilityError(
            f"Expected {expected_count} municipalities, found {len(result)}"
        )
    return result


def read_statistical_regions(path: Path, expected_count: int) -> dict[str, str]:
    required = {"statistical_region_code", "statistical_region_name"}
    result: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeFeasibilityError("Canonical statistical-region schema is invalid")
        for row in reader:
            code = row["statistical_region_code"]
            name = row["statistical_region_name"]
            if not code or not name:
                raise KmeFeasibilityError("Statistical-region code and name must be present")
            if code in result:
                raise KmeFeasibilityError(f"Duplicate statistical-region code: {code}")
            result[code] = name
    if len(result) != expected_count:
        raise KmeFeasibilityError(
            f"Expected {expected_count} statistical regions, found {len(result)}"
        )
    return result


def read_municipality_region_mapping(
    path: Path,
    municipalities: Mapping[str, str],
    regions: Mapping[str, str],
) -> dict[str, str]:
    required = {"municipality_code", "statistical_region_code"}
    result: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeFeasibilityError("Municipality-region mapping schema is invalid")
        for row in reader:
            municipality = row["municipality_code"]
            region = row["statistical_region_code"]
            if municipality not in municipalities:
                raise KmeFeasibilityError(f"Unknown mapped municipality: {municipality}")
            if region not in regions:
                raise KmeFeasibilityError(f"Unknown mapped statistical region: {region}")
            if municipality in result:
                raise KmeFeasibilityError(f"Duplicate municipality mapping: {municipality}")
            result[municipality] = region
    if set(result) != set(municipalities):
        raise KmeFeasibilityError("Municipality-region mapping does not cover municipalities exactly")
    if set(result.values()) != set(regions):
        raise KmeFeasibilityError("Municipality-region mapping does not cover regions exactly")
    return result


def read_calendar(path: Path) -> tuple[tuple[date, ...], dict[date, int]]:
    required = {"issue_week", "year", "iso_week"}
    year_by_week: dict[date, int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeFeasibilityError("Canonical calendar schema is invalid")
        for row in reader:
            week = parse_iso_date(row["issue_week"], "calendar.issue_week")
            if week in year_by_week:
                raise KmeFeasibilityError(f"Duplicate calendar week: {week}")
            try:
                source_year = int(row["year"])
                source_week = int(row["iso_week"])
            except ValueError as exc:
                raise KmeFeasibilityError("Invalid canonical ISO year/week") from exc
            iso = week.isocalendar()
            if source_year != iso.year or source_week != iso.week:
                raise KmeFeasibilityError(
                    f"Calendar ISO fields contradict issue_week {week.isoformat()}"
                )
            year_by_week[week] = source_year
    weeks = tuple(sorted(year_by_week))
    if not weeks:
        raise KmeFeasibilityError("Canonical calendar is empty")
    if any(later - earlier != timedelta(weeks=1) for earlier, later in zip(weeks, weeks[1:])):
        raise KmeFeasibilityError("Canonical calendar contains a missing week")
    return weeks, year_by_week


def read_weekly_kme_cases(
    path: Path,
    municipalities: Mapping[str, str],
    weeks: Sequence[date],
) -> dict[str, tuple[int, ...]]:
    required = {"municipality_code", "issue_week", "kme_cases"}
    expected_weeks = set(weeks)
    values: dict[tuple[str, date], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeFeasibilityError("Canonical weekly_cases schema is invalid")
        for row in reader:
            code = row["municipality_code"]
            if code not in municipalities:
                raise KmeFeasibilityError(f"Unmatched municipality code: {code}")
            week = parse_iso_date(row["issue_week"], "weekly_cases.issue_week")
            if week not in expected_weeks:
                raise KmeFeasibilityError(f"Weekly case date is absent from calendar: {week}")
            key = (code, week)
            if key in values:
                raise KmeFeasibilityError(
                    f"Duplicate municipality-week row: {code}, {week.isoformat()}"
                )
            raw_value = row["kme_cases"]
            if raw_value == "":
                raise KmeFeasibilityError(
                    f"Missing canonical kme_cases value: {code}, {week.isoformat()}"
                )
            try:
                value = int(raw_value)
            except ValueError as exc:
                raise KmeFeasibilityError(f"Invalid kme_cases value: {raw_value!r}") from exc
            if value < 0:
                raise KmeFeasibilityError("KME case counts must not be negative")
            values[key] = value

    expected_keys = {(code, week) for code in municipalities for week in weeks}
    if set(values) != expected_keys:
        missing = sorted(expected_keys - set(values))[:10]
        unexpected = sorted(set(values) - expected_keys)[:10]
        raise KmeFeasibilityError(
            f"Canonical KME grid is incomplete; missing={missing}, unexpected={unexpected}"
        )
    return {
        code: tuple(values[(code, week)] for week in weeks)
        for code in sorted(municipalities)
    }


def read_canonical_kme_data(
    config: Mapping[str, Any], repo_root: Path = REPO_ROOT
) -> tuple[CanonicalKmeData, dict[str, Any]]:
    inputs = config["inputs"]
    paths = {
        key: resolve_repo_path(inputs[key], repo_root)
        for key in (
            "weekly_cases",
            "municipality",
            "calendar",
            "statistical_region",
            "municipality_statistical_region",
        )
    }
    hashes = {
        key: require_file_hash(paths[key], inputs[f"{key}_sha256"], key)
        for key in paths
    }
    expected_count = int(config["canonical_contract"]["expected_municipality_count"])
    municipalities = read_municipalities(paths["municipality"], expected_count)
    expected_region_count = int(
        config["canonical_contract"]["expected_statistical_region_count"]
    )
    statistical_regions = read_statistical_regions(
        paths["statistical_region"], expected_region_count
    )
    region_by_municipality = read_municipality_region_mapping(
        paths["municipality_statistical_region"],
        municipalities,
        statistical_regions,
    )
    weeks, iso_year_by_week = read_calendar(paths["calendar"])
    cases = read_weekly_kme_cases(paths["weekly_cases"], municipalities, weeks)
    cases_by_statistical_region = {
        region: tuple(
            sum(
                cases[municipality][week_index]
                for municipality, mapped_region in region_by_municipality.items()
                if mapped_region == region
            )
            for week_index in range(len(weeks))
        )
        for region in sorted(statistical_regions)
    }
    data = CanonicalKmeData(
        municipalities=municipalities,
        statistical_regions=statistical_regions,
        region_by_municipality=region_by_municipality,
        weeks=weeks,
        iso_year_by_week=iso_year_by_week,
        cases_by_municipality=cases,
        cases_by_statistical_region=cases_by_statistical_region,
    )
    lineage = {
        "paths": {key: repository_path(path, repo_root) for key, path in paths.items()},
        "sha256": hashes,
    }
    return data, lineage


def rolling_window_counts(values: Sequence[int], horizon_weeks: int) -> list[int]:
    if horizon_weeks <= 0:
        raise KmeFeasibilityError("horizon_weeks must be positive")
    if len(values) < horizon_weeks:
        return []
    cumulative = [0]
    for value in values:
        if value < 0:
            raise KmeFeasibilityError("KME case counts must not be negative")
        cumulative.append(cumulative[-1] + value)
    return [
        cumulative[start + horizon_weeks] - cumulative[start]
        for start in range(len(values) - horizon_weeks + 1)
    ]


def anchored_nonoverlap_counts(values: Sequence[int], horizon_weeks: int) -> list[int]:
    return [
        sum(values[start : start + horizon_weeks])
        for start in range(0, len(values) - horizon_weeks + 1, horizon_weeks)
    ]


def nearest_rank(values: Sequence[int], probability: float) -> int:
    if not values:
        raise KmeFeasibilityError("Cannot calculate a quantile from no values")
    if probability < 0 or probability > 1:
        raise KmeFeasibilityError("Quantile probability must be in [0, 1]")
    ordered = sorted(values)
    if probability == 0:
        return ordered[0]
    rank = math.ceil(probability * len(ordered))
    return ordered[rank - 1]


def build_year_rows(data: CanonicalKmeData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year in sorted(set(data.iso_year_by_week.values())):
        indices = [
            index
            for index, week in enumerate(data.weeks)
            if data.iso_year_by_week[week] == year
        ]
        values = [
            data.cases_by_municipality[code][index]
            for code in data.cases_by_municipality
            for index in indices
        ]
        rows.append(
            {
                "iso_year": year,
                "n_observed_weeks": len(indices),
                "total_kme_cases": sum(values),
                "n_nonzero_municipality_weeks": sum(value > 0 for value in values),
            }
        )
    return rows


def build_municipality_rows(data: CanonicalKmeData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code in sorted(data.municipalities):
        values = data.cases_by_municipality[code]
        rows.append(
            {
                "municipality_code": code,
                "municipality_name": data.municipalities[code],
                "total_kme_cases": sum(values),
                "n_observed_weeks": len(values),
                "n_nonzero_weeks": sum(value > 0 for value in values),
                "fraction_zero_weeks": sum(value == 0 for value in values) / len(values),
            }
        )
    return rows


def build_statistical_region_rows(data: CanonicalKmeData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code in sorted(data.statistical_regions):
        values = data.cases_by_statistical_region[code]
        rows.append(
            {
                "statistical_region_code": code,
                "statistical_region_name": data.statistical_regions[code],
                "total_kme_cases": sum(values),
                "n_observed_weeks": len(values),
                "n_nonzero_weeks": sum(value > 0 for value in values),
                "fraction_zero_weeks": sum(value == 0 for value in values) / len(values),
            }
        )
    return rows


def analysis_window_values(
    cases_by_unit: Mapping[str, Sequence[int]], horizon_weeks: int
) -> tuple[list[int], list[int]]:
    rolling: list[int] = []
    nonoverlap: list[int] = []
    for code in sorted(cases_by_unit):
        values = cases_by_unit[code]
        rolling.extend(rolling_window_counts(values, horizon_weeks))
        nonoverlap.extend(anchored_nonoverlap_counts(values, horizon_weeks))
    return rolling, nonoverlap


def municipality_window_values(
    data: CanonicalKmeData, horizon_weeks: int
) -> tuple[list[int], list[int]]:
    return analysis_window_values(data.cases_by_municipality, horizon_weeks)


def statistical_region_window_values(
    data: CanonicalKmeData, horizon_weeks: int
) -> tuple[list[int], list[int]]:
    return analysis_window_values(data.cases_by_statistical_region, horizon_weeks)


def build_window_distribution_rows(
    data: CanonicalKmeData, horizons: Sequence[int]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for analysis_level, cases_by_unit in (
        ("municipality", data.cases_by_municipality),
        ("statistical_region", data.cases_by_statistical_region),
    ):
        for horizon in horizons:
            values, _ = analysis_window_values(cases_by_unit, horizon)
            histogram = Counter(values)
            for count in sorted(histogram):
                rows.append(
                    {
                        "analysis_level": analysis_level,
                        "horizon_weeks": horizon,
                        "window_case_count": count,
                        "n_rolling_windows": histogram[count],
                        "fraction_of_rolling_windows": histogram[count] / len(values),
                    }
                )
    return rows


def build_design_rows(
    data: CanonicalKmeData, config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_definition = config["descriptive_windows"]["definition"]
    for design in config["candidate_designs"]:
        analysis_level = design["analysis_level"]
        if analysis_level == "municipality":
            cases_by_unit = data.cases_by_municipality
        elif analysis_level == "statistical_region":
            cases_by_unit = data.cases_by_statistical_region
        else:
            raise KmeFeasibilityError(
                f"Unsupported candidate analysis level: {analysis_level}"
            )
        n_units = len(cases_by_unit)
        n_units_with_cases = sum(sum(values) > 0 for values in cases_by_unit.values())
        horizon = int(design["horizon_weeks"])
        rolling, nonoverlap = analysis_window_values(cases_by_unit, horizon)
        rows.append(
            {
                "design_id": design["design_id"],
                "analysis_level": analysis_level,
                "horizon_weeks": horizon,
                "status": "descriptive_feasibility_computed",
                "candidate_target_definition": target_definition,
                "n_units": n_units,
                "n_observed_weeks": len(data.weeks),
                "n_unique_rolling_window_starts": len(data.weeks) - horizon + 1,
                "n_candidate_targets": len(rolling),
                "n_nonzero_candidate_targets": sum(value > 0 for value in rolling),
                "fraction_nonzero_candidate_targets": sum(value > 0 for value in rolling)
                / len(rolling),
                "median_candidate_target_count": nearest_rank(rolling, 0.5),
                "p95_candidate_target_count": nearest_rank(rolling, 0.95),
                "p99_candidate_target_count": nearest_rank(rolling, 0.99),
                "maximum_candidate_target_count": max(rolling),
                "rolling_window_overlap_fraction": (horizon - 1) / horizon,
                "n_anchored_nonoverlap_blocks": len(nonoverlap),
                "n_nonzero_anchored_nonoverlap_blocks": sum(
                    value > 0 for value in nonoverlap
                ),
                "fraction_nonzero_anchored_nonoverlap_blocks": sum(
                    value > 0 for value in nonoverlap
                )
                / len(nonoverlap),
                "n_units_with_any_observed_case": n_units_with_cases,
                "n_units_without_any_observed_case": n_units - n_units_with_cases,
                "effective_sample_size": None,
                "effective_sample_size_status": "UNKNOWN_requires_model_and_dependence_structure",
                "limitation": (
                    "Rolling windows overlap and municipality observations share calendar time; "
                    "raw row counts are not an effective sample size. Anchored non-overlap blocks "
                    "are a transparent support diagnostic, not an independence claim."
                ),
            }
        )
    return rows


def csv_value(value: Any) -> Any:
    return "" if value is None else value


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column)) for column in columns})


def file_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": repository_path(path, repo_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def render_report(
    data: CanonicalKmeData,
    year_rows: Sequence[Mapping[str, Any]],
    municipality_rows: Sequence[Mapping[str, Any]],
    region_rows: Sequence[Mapping[str, Any]],
    design_rows: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> str:
    total_cells = len(data.municipalities) * len(data.weeks)
    total_cases = sum(sum(values) for values in data.cases_by_municipality.values())
    nonzero_cells = sum(
        value > 0 for values in data.cases_by_municipality.values() for value in values
    )
    zero_fraction = 1.0 - nonzero_cells / total_cells
    municipality_sorted = sorted(
        municipality_rows,
        key=lambda row: (-int(row["total_kme_cases"]), row["municipality_code"]),
    )
    region_status = config["statistical_region_mapping"]
    recommendation = config["provisional_recommendation"]

    year_table = markdown_table(
        ("ISO year", "Observed weeks", "KME cases", "Non-zero municipality-weeks"),
        [
            (
                row["iso_year"],
                row["n_observed_weeks"],
                row["total_kme_cases"],
                row["n_nonzero_municipality_weeks"],
            )
            for row in year_rows
        ],
    )
    design_table = markdown_table(
        (
            "Design",
            "Unit",
            "Horizon",
            "Candidate windows",
            "Non-zero",
            "Non-zero %",
            "Anchored non-overlap blocks",
            "Non-zero blocks",
            "Status",
        ),
        [
            (
                row["design_id"],
                row["analysis_level"],
                f"{row['horizon_weeks']} weeks",
                row["n_candidate_targets"] if row["n_candidate_targets"] is not None else "UNKNOWN",
                row["n_nonzero_candidate_targets"]
                if row["n_nonzero_candidate_targets"] is not None
                else "UNKNOWN",
                f"{100 * row['fraction_nonzero_candidate_targets']:.3f}"
                if row["fraction_nonzero_candidate_targets"] is not None
                else "UNKNOWN",
                row["n_anchored_nonoverlap_blocks"]
                if row["n_anchored_nonoverlap_blocks"] is not None
                else "UNKNOWN",
                row["n_nonzero_anchored_nonoverlap_blocks"]
                if row["n_nonzero_anchored_nonoverlap_blocks"] is not None
                else "UNKNOWN",
                row["status"],
            )
            for row in design_rows
        ],
    )
    distribution_table = markdown_table(
        ("Unit", "Horizon", "Zero %", "Non-zero", "Median", "P95", "P99", "Maximum"),
        [
            (
                row["analysis_level"],
                f"{row['horizon_weeks']} weeks",
                f"{100 * (1 - row['fraction_nonzero_candidate_targets']):.3f}",
                row["n_nonzero_candidate_targets"],
                row["median_candidate_target_count"],
                row["p95_candidate_target_count"],
                row["p99_candidate_target_count"],
                row["maximum_candidate_target_count"],
            )
            for row in design_rows
        ],
    )
    top_municipality_table = markdown_table(
        ("Code", "Municipality", "Total KME cases", "Non-zero weeks"),
        [
            (
                row["municipality_code"],
                row["municipality_name"],
                row["total_kme_cases"],
                row["n_nonzero_weeks"],
            )
            for row in municipality_sorted[:10]
        ],
    )
    region_table = markdown_table(
        ("Code", "Statistical region", "Total KME cases", "Non-zero weeks", "Zero weeks %"),
        [
            (
                row["statistical_region_code"],
                row["statistical_region_name"],
                row["total_kme_cases"],
                row["n_nonzero_weeks"],
                f"{100 * row['fraction_zero_weeks']:.3f}",
            )
            for row in sorted(region_rows, key=lambda row: row["statistical_region_code"])
        ],
    )

    return f"""# KME descriptive feasibility analysis

## Scope and definitions

This is the reproducible descriptive design analysis behind the implemented KME pipeline. It uses canonical `kme_cases`, calendar data, and the verified municipality-to-statistical-region mapping. The modelling code and target are separate stages, and the KME horizon is not copied from Lyme.

The source covers {data.weeks[0].isocalendar().year} through {data.weeks[-1].isocalendar().year}: {len(data.weeks)} consecutive canonical ISO weeks for {len(data.municipalities)} fixed municipality zones. Year summaries use the ISO week-numbering year, so dates such as 2014-12-29 are correctly assigned to ISO year 2015.

For feasibility only, an H-week candidate outcome is the sum in every complete consecutive observed H-week interval, including its window start, with one-week stride. These overlapping windows are not an implemented forecast target and do not decide whether a later target includes or excludes an issue week.

## Overall sparsity

- Total observed KME cases: **{total_cases}**.
- Municipality-weeks: **{total_cells}**.
- Municipality-weeks with zero cases: **{total_cells - nonzero_cells} ({100 * zero_fraction:.3f}%)**.
- Municipality-weeks with one or more cases: **{nonzero_cells} ({100 * nonzero_cells / total_cells:.3f}%)**.
- Municipalities with at least one observed case: **{sum(int(row['total_kme_cases']) > 0 for row in municipality_rows)} of {len(municipality_rows)}**.
- Municipalities with no observed case in the entire source period: **{sum(int(row['total_kme_cases']) == 0 for row in municipality_rows)} of {len(municipality_rows)}**.

## Cases by year

{year_table}

## Cases by municipality

The complete 212-row municipality table is written to `model_v3/outputs/kme_feasibility/kme_cases_by_municipality.csv`. The ten municipalities with the largest observed totals are shown below; this is descriptive ranking, not risk.

{top_municipality_table}

## Cases by statistical region

Mapping status: **{region_status['status']}**. Source: **{region_status['source']}**, valid from **{region_status['valid_from']}**. Joins use municipality code. {region_status['fixed_zone_rule']}

{region_table}

## Candidate window distributions

{distribution_table}

The full integer-count histograms for 4, 8, and 12 weeks are in `kme_window_count_distribution.csv`.

## Candidate design comparison

{design_table}

Raw rolling rows are not effective sample sizes: adjacent windows overlap by 75.0%, 87.5%, and 91.7% for 4, 8, and 12 weeks, respectively, and municipalities share calendar time. Effective sample size is therefore **UNKNOWN** until a dependence structure and evaluation design are specified. Anchored non-overlapping blocks are shown only as a support diagnostic; they are not asserted to be independent.

Longer windows increase the fraction containing at least one case, but they reduce distinct temporal blocks and temporal resolution. Region aggregation materially reduces zeros relative to municipality-level windows, but it does not create additional cases or independent observations.

## Selected design

**{recommendation['label']}** (`design {recommendation['design_id']}`). Status: **{recommendation['status']}**.

Reason: {recommendation['reason']}

The implemented forecast target is reported regional KME cases in exactly `t+1..t+8`, excluding the issue week. Since 2015-2025 outcomes informed this design, those years are development evidence and must not be presented as an untouched KME lockbox; a future KME lockbox must begin after 2025.
"""


def write_outputs(
    data: CanonicalKmeData,
    lineage: Mapping[str, Any],
    config: Mapping[str, Any],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    output_config = config["outputs"]
    output_directory = resolve_repo_path(output_config["directory"], repo_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "cases_by_year": output_directory / output_config["cases_by_year"],
        "cases_by_municipality": output_directory / output_config["cases_by_municipality"],
        "cases_by_statistical_region": output_directory
        / output_config["cases_by_statistical_region"],
        "window_distribution": output_directory / output_config["window_distribution"],
        "design_comparison": output_directory / output_config["design_comparison"],
        "region_status": output_directory / output_config["region_status"],
        "quality_summary": output_directory / output_config["quality_summary"],
        "report": resolve_repo_path(output_config["report"], repo_root),
    }
    year_rows = build_year_rows(data)
    municipality_rows = build_municipality_rows(data)
    region_rows = build_statistical_region_rows(data)
    horizons = config["descriptive_windows"]["horizons_weeks"]
    distribution_rows = build_window_distribution_rows(data, horizons)
    design_rows = build_design_rows(data, config)

    write_csv(paths["cases_by_year"], YEAR_COLUMNS, year_rows)
    write_csv(paths["cases_by_municipality"], MUNICIPALITY_COLUMNS, municipality_rows)
    write_csv(paths["cases_by_statistical_region"], REGION_COLUMNS, region_rows)
    write_csv(
        paths["window_distribution"], WINDOW_DISTRIBUTION_COLUMNS, distribution_rows
    )
    write_csv(paths["design_comparison"], DESIGN_COLUMNS, design_rows)
    paths["region_status"].write_text(
        json.dumps(config["statistical_region_mapping"], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    paths["report"].parent.mkdir(parents=True, exist_ok=True)
    paths["report"].write_text(
        render_report(
            data,
            year_rows,
            municipality_rows,
            region_rows,
            design_rows,
            config,
        ),
        encoding="utf-8",
    )

    total_cells = len(data.municipalities) * len(data.weeks)
    nonzero_cells = sum(
        value > 0 for values in data.cases_by_municipality.values() for value in values
    )
    region_cells = len(data.statistical_regions) * len(data.weeks)
    nonzero_region_cells = sum(
        value > 0
        for values in data.cases_by_statistical_region.values()
        for value in values
    )
    output_records = {
        key: file_record(path, repo_root)
        for key, path in paths.items()
        if key != "quality_summary"
    }
    quality = {
        "schema_version": 1,
        "pipeline": "model_v3.evaluation.kme_feasibility",
        "status": "complete_with_verified_region_designs",
        "inputs": dict(lineage),
        "canonical_support": {
            "first_issue_week": data.weeks[0].isoformat(),
            "last_issue_week": data.weeks[-1].isoformat(),
            "first_iso_year": data.weeks[0].isocalendar().year,
            "last_iso_year": data.weeks[-1].isocalendar().year,
            "n_weeks": len(data.weeks),
            "n_municipalities": len(data.municipalities),
            "n_statistical_regions": len(data.statistical_regions),
            "n_municipality_weeks": total_cells,
            "total_kme_cases": sum(
                sum(values) for values in data.cases_by_municipality.values()
            ),
            "n_zero_municipality_weeks": total_cells - nonzero_cells,
            "fraction_zero_municipality_weeks": (total_cells - nonzero_cells)
            / total_cells,
            "n_nonzero_municipality_weeks": nonzero_cells,
            "n_municipalities_with_any_case": sum(
                sum(values) > 0 for values in data.cases_by_municipality.values()
            ),
            "n_municipalities_without_any_case": sum(
                sum(values) == 0 for values in data.cases_by_municipality.values()
            ),
            "n_statistical_region_weeks": region_cells,
            "n_zero_statistical_region_weeks": region_cells - nonzero_region_cells,
            "fraction_zero_statistical_region_weeks": (
                region_cells - nonzero_region_cells
            )
            / region_cells,
        },
        "checks": {
            "canonical_hashes_match": True,
            "municipality_codes_unique": True,
            "municipality_week_keys_unique": True,
            "complete_municipality_week_grid": True,
            "weeks_consecutive": True,
            "weeks_are_mondays": True,
            "iso_calendar_fields_verified": True,
            "negative_kme_case_count": 0,
            "missing_kme_case_count": 0,
            "region_mapping_verified": True,
            "region_mapping_joined_by_municipality_code": True,
            "regional_statistics_computed": True,
            "municipality_and_region_case_totals_match": sum(
                sum(values) for values in data.cases_by_municipality.values()
            )
            == sum(sum(values) for values in data.cases_by_statistical_region.values()),
            "feasibility_stage_created_target": False,
            "feasibility_stage_trained_model": False,
            "effective_sample_size_claimed": False,
        },
        "region_mapping": dict(config["statistical_region_mapping"]),
        "candidate_designs": design_rows,
        "provisional_recommendation": dict(config["provisional_recommendation"]),
        "outputs": output_records,
    }
    paths["quality_summary"].write_text(
        json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    quality["quality_summary"] = file_record(paths["quality_summary"], repo_root)
    return quality


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    data, lineage = read_canonical_kme_data(config, repo_root)
    return write_outputs(data, lineage, config, repo_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the KME descriptive design-feasibility analysis."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    quality = run(args.config)
    support = quality["canonical_support"]
    print(
        "Created KME feasibility analysis: "
        f"{support['total_kme_cases']} cases, "
        f"{support['n_municipalities']} municipalities, "
        f"{support['n_weeks']} weeks; regional designs verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
