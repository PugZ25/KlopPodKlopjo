from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "lyme_descriptive_epidemiology.json"
)

DENOMINATOR_VALID = "valid"
DENOMINATOR_MISSING = "missing_population"
DENOMINATOR_NONPOSITIVE = "nonpositive_population"


class DescriptiveEpidemiologyError(ValueError):
    """Raised when descriptive inputs or outputs violate their contract."""


@dataclass(frozen=True, order=True)
class MunicipalityRow:
    municipality_code: str
    municipality_name: str


@dataclass(frozen=True, order=True)
class PopulationRow:
    municipality_code: str
    year: int
    population: int | None


@dataclass(frozen=True, order=True)
class WeeklyLymeRow:
    municipality_code: str
    issue_week: date
    lyme_cases: int


@dataclass(frozen=True, order=True)
class CalendarRow:
    issue_week: date
    iso_year: int
    iso_week: int


@dataclass(frozen=True, order=True)
class TargetMetadataRow:
    municipality_code: str
    issue_week: date
    target_window_start: date
    target_window_end: date
    target_status: str
    target_training_eligible: bool
    target_value: int | None


def resolve_repo_path(raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise DescriptiveEpidemiologyError(
            f"Configured path must be a non-empty string: {raw_path!r}"
        )
    relative = Path(raw_path)
    if relative.is_absolute():
        raise DescriptiveEpidemiologyError(
            f"Configured path must be repository-relative: {raw_path}"
        )
    resolved = (REPO_ROOT / relative).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise DescriptiveEpidemiologyError(
            f"Configured path leaves repository root: {raw_path}"
        )
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, object]:
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise DescriptiveEpidemiologyError(
            f"Descriptive configuration must be inside the repository: {path}"
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise DescriptiveEpidemiologyError(
            "Descriptive configuration schema_version must equal 1."
        )
    inputs = config.get("inputs")
    period = config.get("period")
    incidence = config.get("incidence")
    outputs = config.get("outputs")
    if not all(
        isinstance(value, dict) for value in (inputs, period, incidence, outputs)
    ):
        raise DescriptiveEpidemiologyError(
            "Descriptive inputs, period, incidence, and outputs are required."
        )

    for key in (
        "municipality",
        "population",
        "weekly_cases",
        "calendar",
        "four_week_target",
    ):
        if not isinstance(inputs.get(key), str) or not inputs[key]:
            raise DescriptiveEpidemiologyError(
                f"Descriptive input {key} must be a non-empty path."
            )
    for key in (
        "development_start_year",
        "development_end_year",
        "excluded_lockbox_year",
    ):
        value = period.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise DescriptiveEpidemiologyError(
                f"Descriptive period {key} must be an integer."
            )
    if period["development_start_year"] > period["development_end_year"]:
        raise DescriptiveEpidemiologyError(
            "development_start_year must not exceed development_end_year."
        )
    if period["development_end_year"] >= period["excluded_lockbox_year"]:
        raise DescriptiveEpidemiologyError(
            "The descriptive period must end before the lockbox year."
        )
    if period.get("year_definition") != "gregorian_year_of_issue_week_monday":
        raise DescriptiveEpidemiologyError(
            "Descriptive year_definition must be gregorian_year_of_issue_week_monday."
        )
    if (
        period.get("lockbox_input_rule")
        != "skip_at_or_after_lockbox_start_before_numeric_parsing"
    ):
        raise DescriptiveEpidemiologyError(
            "Descriptive lockbox_input_rule does not match the sealed policy."
        )
    if incidence.get("scale") != 100000:
        raise DescriptiveEpidemiologyError("Incidence scale must equal 100000.")
    if incidence.get("population_measure") != "Population - Total - 1 January":
        raise DescriptiveEpidemiologyError(
            "Incidence population measure does not match the canonical SURS measure."
        )
    if (
        incidence.get("valid_denominator_rule")
        != "population_is_present_and_greater_than_zero"
    ):
        raise DescriptiveEpidemiologyError(
            "Incidence denominator rule must require a present positive population."
        )

    expected_output_keys = {
        "directory",
        "cases_by_year",
        "cases_by_week_of_year",
        "cases_by_municipality",
        "population_by_municipality_year",
        "incidence_by_municipality_year",
        "incidence_by_year",
        "zero_case_proportion",
        "target_distribution",
        "missing_data_summary",
        "supervised_row_summary",
        "cases_by_year_plot",
        "incidence_by_year_plot",
        "target_distribution_plot",
        "quality_summary",
    }
    if set(outputs) != expected_output_keys:
        raise DescriptiveEpidemiologyError(
            "Descriptive output keys do not match the required output contract."
        )
    for key, value in outputs.items():
        if not isinstance(value, str) or not value:
            raise DescriptiveEpidemiologyError(
                f"Descriptive output {key} must be a non-empty string."
            )
    return config


def read_csv(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        observed_columns = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - observed_columns)
        if missing_columns:
            raise DescriptiveEpidemiologyError(
                f"{path.name} is missing columns: {missing_columns}"
            )
        return [dict(row) for row in reader]


def parse_code(value: object, *, context: str) -> str:
    code = str(value).strip() if value is not None else ""
    if not re.fullmatch(r"\d{3}", code):
        raise DescriptiveEpidemiologyError(
            f"{context} must be a three-digit municipality code: {value!r}"
        )
    return code


def parse_monday(value: object, *, context: str) -> date:
    if isinstance(value, date):
        result = value
    elif isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as exc:
            raise DescriptiveEpidemiologyError(
                f"{context} is not an ISO date: {value!r}"
            ) from exc
    else:
        raise DescriptiveEpidemiologyError(f"{context} is not a date: {value!r}")
    if result.weekday() != 0:
        raise DescriptiveEpidemiologyError(
            f"{context} must be a Monday: {result.isoformat()}"
        )
    return result


def parse_nonnegative_integer(value: object, *, context: str) -> int:
    if isinstance(value, bool):
        raise DescriptiveEpidemiologyError(f"{context} must not be boolean.")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(r"\d+", value):
        result = int(value)
    else:
        raise DescriptiveEpidemiologyError(
            f"{context} must be a present non-negative integer: {value!r}"
        )
    if result < 0:
        raise DescriptiveEpidemiologyError(f"{context} must not be negative.")
    return result


def parse_optional_nonnegative_integer(value: object, *, context: str) -> int | None:
    if value in (None, ""):
        return None
    return parse_nonnegative_integer(value, context=context)


def parse_boolean(value: object, *, context: str) -> bool:
    if isinstance(value, bool):
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    raise DescriptiveEpidemiologyError(
        f"{context} must be true or false: {value!r}"
    )


def ensure_unique(keys: Iterable[object], *, dataset: str) -> None:
    counts = Counter(keys)
    duplicates = [key for key, count in counts.items() if count > 1]
    if duplicates:
        raise DescriptiveEpidemiologyError(
            f"{dataset} has duplicate keys: {duplicates[:20]}"
        )


def load_municipalities(path: Path) -> list[MunicipalityRow]:
    raw_rows = read_csv(path, {"municipality_code", "municipality_name"})
    rows: list[MunicipalityRow] = []
    for index, raw in enumerate(raw_rows, start=1):
        code = parse_code(
            raw["municipality_code"], context=f"municipality row {index} code"
        )
        name = raw["municipality_name"].strip()
        if not name:
            raise DescriptiveEpidemiologyError(
                f"municipality row {index} name must be present."
            )
        rows.append(MunicipalityRow(code, name))
    ensure_unique((row.municipality_code for row in rows), dataset="municipality")
    if not rows:
        raise DescriptiveEpidemiologyError("Municipality input is empty.")
    return sorted(rows)


def load_population(path: Path, *, lockbox_year: int) -> list[PopulationRow]:
    raw_rows = read_csv(path, {"municipality_code", "year", "population"})
    rows: list[PopulationRow] = []
    for index, raw in enumerate(raw_rows, start=1):
        year = parse_nonnegative_integer(raw["year"], context=f"population row {index} year")
        if year < 1000 or year > 9999:
            raise DescriptiveEpidemiologyError(
                f"population row {index} year must have four digits."
            )
        if year >= lockbox_year:
            continue
        code = parse_code(raw["municipality_code"], context=f"population row {index} code")
        population = parse_optional_nonnegative_integer(
            raw["population"], context=f"population[{code}, {year}]"
        )
        rows.append(PopulationRow(code, year, population))
    ensure_unique(
        ((row.municipality_code, row.year) for row in rows), dataset="population"
    )
    return sorted(rows)


def load_weekly_lyme(path: Path, *, lockbox_year: int) -> list[WeeklyLymeRow]:
    raw_rows = read_csv(
        path, {"municipality_code", "issue_week", "lyme_cases"}
    )
    rows: list[WeeklyLymeRow] = []
    for index, raw in enumerate(raw_rows, start=1):
        issue_week = parse_monday(
            raw["issue_week"], context=f"weekly row {index} issue_week"
        )
        if issue_week.year >= lockbox_year:
            continue
        code = parse_code(raw["municipality_code"], context=f"weekly row {index} code")
        lyme_cases = parse_nonnegative_integer(
            raw["lyme_cases"], context=f"weekly[{code}, {issue_week}] lyme_cases"
        )
        rows.append(WeeklyLymeRow(code, issue_week, lyme_cases))
    ensure_unique(
        ((row.municipality_code, row.issue_week) for row in rows),
        dataset="weekly_cases",
    )
    return sorted(rows)


def load_calendar(path: Path, *, lockbox_year: int) -> list[CalendarRow]:
    raw_rows = read_csv(path, {"issue_week", "year", "iso_week"})
    rows: list[CalendarRow] = []
    for index, raw in enumerate(raw_rows, start=1):
        issue_week = parse_monday(
            raw["issue_week"], context=f"calendar row {index} issue_week"
        )
        if issue_week.year >= lockbox_year:
            continue
        iso_year = parse_nonnegative_integer(
            raw["year"], context=f"calendar row {index} year"
        )
        iso_week = parse_nonnegative_integer(
            raw["iso_week"], context=f"calendar row {index} iso_week"
        )
        actual_iso = issue_week.isocalendar()
        if (iso_year, iso_week) != (actual_iso.year, actual_iso.week):
            raise DescriptiveEpidemiologyError(
                f"calendar row {index} ISO fields disagree with issue_week."
            )
        rows.append(CalendarRow(issue_week, iso_year, iso_week))
    ensure_unique((row.issue_week for row in rows), dataset="calendar")
    return sorted(rows)


def load_target_metadata(
    path: Path, *, lockbox_year: int
) -> list[TargetMetadataRow]:
    required = {
        "municipality_code",
        "issue_week",
        "target_lyme_cases_next_4w",
        "target_window_start",
        "target_window_end",
        "target_status",
        "target_training_eligible",
    }
    raw_rows = read_csv(path, required)
    rows: list[TargetMetadataRow] = []
    lockbox_start = date(lockbox_year, 1, 1)
    for index, raw in enumerate(raw_rows, start=1):
        issue_week = parse_monday(
            raw["issue_week"], context=f"target row {index} issue_week"
        )
        if issue_week >= lockbox_start:
            continue
        code = parse_code(raw["municipality_code"], context=f"target row {index} code")
        window_start = parse_monday(
            raw["target_window_start"],
            context=f"target row {index} target_window_start",
        )
        window_end = parse_monday(
            raw["target_window_end"],
            context=f"target row {index} target_window_end",
        )
        if window_start != issue_week + timedelta(weeks=1):
            raise DescriptiveEpidemiologyError(
                f"target row {index} window start is not t+1."
            )
        if window_end != issue_week + timedelta(weeks=4):
            raise DescriptiveEpidemiologyError(
                f"target row {index} window end is not t+4."
            )
        status = raw["target_status"].strip()
        eligible = parse_boolean(
            raw["target_training_eligible"],
            context=f"target row {index} eligibility",
        )
        if eligible != (status == "complete"):
            raise DescriptiveEpidemiologyError(
                f"target row {index} status and eligibility disagree."
            )

        # Numeric targets whose windows enter the lockbox are deliberately not parsed.
        target_value: int | None = None
        if window_end < lockbox_start:
            target_value = parse_optional_nonnegative_integer(
                raw["target_lyme_cases_next_4w"],
                context=f"target[{code}, {issue_week}] value",
            )
            if eligible and target_value is None:
                raise DescriptiveEpidemiologyError(
                    f"target[{code}, {issue_week}] is eligible but missing."
                )
            if not eligible and target_value is not None:
                raise DescriptiveEpidemiologyError(
                    f"target[{code}, {issue_week}] is ineligible but has a value."
                )
        rows.append(
            TargetMetadataRow(
                code,
                issue_week,
                window_start,
                window_end,
                status,
                eligible,
                target_value,
            )
        )
    ensure_unique(
        ((row.municipality_code, row.issue_week) for row in rows), dataset="target"
    )
    return sorted(rows)


def calculate_incidence_per_100000(
    reported_cases: int, population: int | None
) -> tuple[float | None, str]:
    """Return incidence per 100,000 and an explicit denominator status."""

    if isinstance(reported_cases, bool) or not isinstance(reported_cases, int):
        raise DescriptiveEpidemiologyError(
            "Reported cases must be a non-negative integer."
        )
    if reported_cases < 0:
        raise DescriptiveEpidemiologyError("Reported cases must not be negative.")
    if population is None:
        return None, DENOMINATOR_MISSING
    if isinstance(population, bool) or not isinstance(population, int):
        raise DescriptiveEpidemiologyError(
            "Population must be a non-negative integer or missing."
        )
    if population < 0:
        raise DescriptiveEpidemiologyError("Population must not be negative.")
    if population == 0:
        return None, DENOMINATOR_NONPOSITIVE
    return reported_cases / population * 100000, DENOMINATOR_VALID


def csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.10f}".rstrip("0").rstrip(".")
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv_rows(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row[column]) for column in columns})


def missing_summary_row(
    dataset: str, column: str, values: Sequence[object], period: str
) -> dict[str, object]:
    missing = sum(value is None or value == "" for value in values)
    return {
        "dataset": dataset,
        "column": column,
        "period": period,
        "n_rows": len(values),
        "n_missing": missing,
        "missing_proportion": missing / len(values) if values else None,
    }


def svg_text(x: float, y: float, text: object, **attributes: object) -> str:
    attrs = " ".join(
        f'{key.replace("_", "-")}="{html.escape(str(value))}"'
        for key, value in attributes.items()
    )
    return f'<text x="{x:.2f}" y="{y:.2f}" {attrs}>{html.escape(str(text))}</text>'


def write_bar_plot(
    path: Path,
    *,
    labels: Sequence[str],
    values: Sequence[float],
    title: str,
    numerator: str,
    denominator: str,
    period: str,
    x_label: str,
    y_label: str,
) -> None:
    if not labels or len(labels) != len(values):
        raise DescriptiveEpidemiologyError("Bar plot labels and values are invalid.")
    width, height = 960, 580
    left, right, top, bottom = 100, 30, 150, 85
    plot_width = width - left - right
    plot_height = height - top - bottom
    maximum = max(values) or 1.0
    slot = plot_width / len(values)
    bar_width = slot * 0.66
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<title>{html.escape(title)}</title>",
        f"<desc>{html.escape(numerator)}; {html.escape(denominator)}; {html.escape(period)}</desc>",
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(30, 38, title, font_size=22, font_weight="bold", fill="#16212d"),
        svg_text(30, 68, f"Numerator: {numerator}", font_size=14, fill="#334155"),
        svg_text(30, 92, f"Denominator: {denominator}", font_size=14, fill="#334155"),
        svg_text(30, 116, f"Period: {period}", font_size=14, fill="#334155"),
    ]
    for tick in range(6):
        fraction = tick / 5
        y = top + plot_height * (1 - fraction)
        value = maximum * fraction
        elements.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#d9e1e8"/>'
        )
        elements.append(
            svg_text(left - 10, y + 5, f"{value:,.1f}", text_anchor="end", font_size=12, fill="#475569")
        )
    for index, (label, value) in enumerate(zip(labels, values)):
        x = left + index * slot + (slot - bar_width) / 2
        bar_height = plot_height * value / maximum
        y = top + plot_height - bar_height
        elements.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" fill="#197a70"/>'
        )
        elements.append(
            svg_text(x + bar_width / 2, top + plot_height + 24, label, text_anchor="middle", font_size=12, fill="#334155")
        )
    elements.extend(
        [
            svg_text(left + plot_width / 2, height - 24, x_label, text_anchor="middle", font_size=14, fill="#16212d"),
            f'<text x="22" y="{top + plot_height / 2:.2f}" transform="rotate(-90 22 {top + plot_height / 2:.2f})" text-anchor="middle" font-size="14" fill="#16212d">{html.escape(y_label)}</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def write_ecdf_plot(
    path: Path,
    *,
    target_distribution: Sequence[Mapping[str, object]],
    denominator_count: int,
    period: str,
) -> None:
    if not target_distribution or denominator_count <= 0:
        raise DescriptiveEpidemiologyError("Target ECDF requires non-empty data.")
    width, height = 960, 580
    left, right, top, bottom = 100, 30, 150, 85
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_target = max(int(row["target_lyme_cases_next_4w"]) for row in target_distribution)
    x_max = max(max_target, 1)
    points = []
    for row in target_distribution:
        x_value = int(row["target_lyme_cases_next_4w"])
        y_value = float(row["cumulative_proportion"])
        x = left + plot_width * x_value / x_max
        y = top + plot_height * (1 - y_value)
        points.append(f"{x:.2f},{y:.2f}")
    title = "Distribution of next-four-week reported Lyme case target"
    numerator = "Target-complete municipality-weeks with target count less than or equal to x"
    denominator = f"{denominator_count:,} lockbox-safe target-complete municipality-weeks"
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<title>{html.escape(title)}</title>",
        f"<desc>{html.escape(numerator)}; {html.escape(denominator)}; {html.escape(period)}</desc>",
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(30, 38, title, font_size=22, font_weight="bold", fill="#16212d"),
        svg_text(30, 68, f"Numerator: {numerator}", font_size=14, fill="#334155"),
        svg_text(30, 92, f"Denominator: {denominator}", font_size=14, fill="#334155"),
        svg_text(30, 116, f"Period: {period}", font_size=14, fill="#334155"),
    ]
    for tick in range(6):
        fraction = tick / 5
        y = top + plot_height * (1 - fraction)
        elements.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#d9e1e8"/>'
        )
        elements.append(
            svg_text(left - 10, y + 5, f"{fraction:.1f}", text_anchor="end", font_size=12, fill="#475569")
        )
    for tick in range(6):
        fraction = tick / 5
        x = left + plot_width * fraction
        elements.append(
            svg_text(x, top + plot_height + 24, f"{x_max * fraction:.0f}", text_anchor="middle", font_size=12, fill="#475569")
        )
    elements.extend(
        [
            f'<polyline points="{" ".join(points)}" fill="none" stroke="#197a70" stroke-width="3"/>',
            svg_text(left + plot_width / 2, height - 24, "target_lyme_cases_next_4w", text_anchor="middle", font_size=14, fill="#16212d"),
            f'<text x="22" y="{top + plot_height / 2:.2f}" transform="rotate(-90 22 {top + plot_height / 2:.2f})" text-anchor="middle" font-size="14" fill="#16212d">Cumulative proportion</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def build_descriptive_epidemiology(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    input_paths = {
        key: resolve_repo_path(value) for key, value in config["inputs"].items()
    }
    missing_input_paths = [
        str(path) for path in input_paths.values() if not path.is_file()
    ]
    if missing_input_paths:
        raise DescriptiveEpidemiologyError(
            f"Descriptive inputs do not exist: {missing_input_paths}"
        )

    start_year = config["period"]["development_start_year"]
    end_year = config["period"]["development_end_year"]
    lockbox_year = config["period"]["excluded_lockbox_year"]
    lockbox_start = date(lockbox_year, 1, 1)

    municipalities = load_municipalities(input_paths["municipality"])
    population = load_population(
        input_paths["population"], lockbox_year=lockbox_year
    )
    weekly_rows = load_weekly_lyme(
        input_paths["weekly_cases"], lockbox_year=lockbox_year
    )
    calendar_rows = load_calendar(
        input_paths["calendar"], lockbox_year=lockbox_year
    )
    target_rows = load_target_metadata(
        input_paths["four_week_target"], lockbox_year=lockbox_year
    )

    municipality_names = {
        row.municipality_code: row.municipality_name for row in municipalities
    }
    municipality_codes = set(municipality_names)
    unmatched_codes = sorted(
        {
            row.municipality_code
            for row in population + weekly_rows + target_rows
            if row.municipality_code not in municipality_codes
        }
    )
    if unmatched_codes:
        raise DescriptiveEpidemiologyError(
            f"Canonical inputs contain unmatched municipality codes: {unmatched_codes}"
        )

    calendar_by_date = {row.issue_week: row for row in calendar_rows}
    missing_calendar_dates = sorted(
        {row.issue_week for row in weekly_rows + target_rows}
        - set(calendar_by_date)
    )
    if missing_calendar_dates:
        raise DescriptiveEpidemiologyError(
            "Canonical calendar is missing issue weeks: "
            f"{[value.isoformat() for value in missing_calendar_dates[:20]]}"
        )

    development_weekly = [
        row for row in weekly_rows if start_year <= row.issue_week.year <= end_year
    ]
    development_population = [
        row for row in population if start_year <= row.year <= end_year
    ]
    development_targets = [
        row for row in target_rows if start_year <= row.issue_week.year <= end_year
    ]
    if not development_weekly or not development_population or not development_targets:
        raise DescriptiveEpidemiologyError(
            "One or more descriptive development inputs are empty."
        )
    development_issue_dates = sorted(
        {row.issue_week for row in development_weekly}
    )
    observed_municipality_week_keys = {
        (row.municipality_code, row.issue_week) for row in development_weekly
    }
    expected_municipality_week_keys = {
        (municipality_code, issue_week)
        for municipality_code in municipality_codes
        for issue_week in development_issue_dates
    }
    missing_municipality_week_keys = sorted(
        expected_municipality_week_keys - observed_municipality_week_keys
    )
    if missing_municipality_week_keys:
        raise DescriptiveEpidemiologyError(
            "Development weekly cases are missing municipality-week rows: "
            f"{missing_municipality_week_keys[:20]}"
        )
    period_start = min(row.issue_week for row in development_weekly)
    period_end = max(row.issue_week for row in development_weekly)
    period_label = f"issue weeks {period_start.isoformat()} to {period_end.isoformat()}"

    cases_by_year_group: dict[int, list[WeeklyLymeRow]] = defaultdict(list)
    cases_by_week_group: dict[int, list[WeeklyLymeRow]] = defaultdict(list)
    cases_by_municipality_group: dict[str, list[WeeklyLymeRow]] = defaultdict(list)
    cases_by_municipality_year: Counter[tuple[str, int]] = Counter()
    for row in development_weekly:
        issue_year = row.issue_week.year
        iso_week = calendar_by_date[row.issue_week].iso_week
        cases_by_year_group[issue_year].append(row)
        cases_by_week_group[iso_week].append(row)
        cases_by_municipality_group[row.municipality_code].append(row)
        cases_by_municipality_year[(row.municipality_code, issue_year)] += row.lyme_cases

    cases_by_year_rows: list[dict[str, object]] = []
    for year in sorted(cases_by_year_group):
        rows = cases_by_year_group[year]
        issue_dates = sorted({row.issue_week for row in rows})
        cases_by_year_rows.append(
            {
                "issue_year": year,
                "period_start": issue_dates[0],
                "period_end": issue_dates[-1],
                "n_issue_weeks": len(issue_dates),
                "n_municipality_weeks": len(rows),
                "reported_lyme_cases": sum(row.lyme_cases for row in rows),
            }
        )

    cases_by_week_rows: list[dict[str, object]] = []
    for iso_week in sorted(cases_by_week_group):
        rows = cases_by_week_group[iso_week]
        cases_by_week_rows.append(
            {
                "iso_week": iso_week,
                "development_period_start": period_start,
                "development_period_end": period_end,
                "n_observed_issue_weeks": len({row.issue_week for row in rows}),
                "n_municipality_weeks": len(rows),
                "reported_lyme_cases": sum(row.lyme_cases for row in rows),
            }
        )

    cases_by_municipality_rows: list[dict[str, object]] = []
    for code in sorted(cases_by_municipality_group):
        rows = cases_by_municipality_group[code]
        cases_by_municipality_rows.append(
            {
                "municipality_code": code,
                "municipality_name": municipality_names[code],
                "period_start": period_start,
                "period_end": period_end,
                "n_issue_weeks": len({row.issue_week for row in rows}),
                "n_municipality_weeks": len(rows),
                "reported_lyme_cases": sum(row.lyme_cases for row in rows),
            }
        )

    population_by_key = {
        (row.municipality_code, row.year): row.population
        for row in development_population
    }
    population_output_rows: list[dict[str, object]] = []
    for code in sorted(municipality_codes):
        for year in range(start_year, end_year + 1):
            value = population_by_key.get((code, year))
            _, status = calculate_incidence_per_100000(0, value)
            population_output_rows.append(
                {
                    "municipality_code": code,
                    "municipality_name": municipality_names[code],
                    "year": year,
                    "population_total_on_1_january": value,
                    "denominator_status": status,
                }
            )

    incidence_rows: list[dict[str, object]] = []
    for code in sorted(municipality_codes):
        for year in range(start_year, end_year + 1):
            cases = cases_by_municipality_year[(code, year)]
            population_value = population_by_key.get((code, year))
            incidence, status = calculate_incidence_per_100000(
                cases, population_value
            )
            year_dates = [
                row.issue_week
                for row in cases_by_year_group.get(year, [])
                if row.municipality_code == code
            ]
            incidence_rows.append(
                {
                    "municipality_code": code,
                    "municipality_name": municipality_names[code],
                    "issue_year": year,
                    "numerator_period_start": min(year_dates) if year_dates else None,
                    "numerator_period_end": max(year_dates) if year_dates else None,
                    "reported_lyme_cases": cases,
                    "population_total_on_1_january": population_value,
                    "incidence_per_100000": incidence,
                    "denominator_status": status,
                }
            )

    incidence_by_year_rows: list[dict[str, object]] = []
    for year in range(start_year, end_year + 1):
        year_rows = [row for row in incidence_rows if row["issue_year"] == year]
        valid_rows = [
            row for row in year_rows if row["denominator_status"] == DENOMINATOR_VALID
        ]
        numerator = sum(int(row["reported_lyme_cases"]) for row in valid_rows)
        denominator = sum(
            int(row["population_total_on_1_january"]) for row in valid_rows
        )
        aggregate_incidence, status = calculate_incidence_per_100000(
            numerator, denominator if denominator > 0 else None
        )
        period_row = next(row for row in cases_by_year_rows if row["issue_year"] == year)
        incidence_by_year_rows.append(
            {
                "issue_year": year,
                "numerator_period_start": period_row["period_start"],
                "numerator_period_end": period_row["period_end"],
                "reported_lyme_cases_with_valid_denominator": numerator,
                "summed_population_total_on_1_january": denominator,
                "incidence_per_100000": aggregate_incidence,
                "valid_denominator_municipalities": len(valid_rows),
                "excluded_denominator_municipalities": len(year_rows) - len(valid_rows),
                "denominator_status": status,
            }
        )

    zero_case_rows: list[dict[str, object]] = []
    for year in sorted(cases_by_year_group):
        rows = cases_by_year_group[year]
        zero_count = sum(row.lyme_cases == 0 for row in rows)
        zero_case_rows.append(
            {
                "period": str(year),
                "period_start": min(row.issue_week for row in rows),
                "period_end": max(row.issue_week for row in rows),
                "zero_case_municipality_weeks": zero_count,
                "observed_municipality_weeks": len(rows),
                "proportion_zero_cases": zero_count / len(rows),
            }
        )
    total_zero = sum(row.lyme_cases == 0 for row in development_weekly)
    zero_case_rows.append(
        {
            "period": f"{start_year}-{end_year}",
            "period_start": period_start,
            "period_end": period_end,
            "zero_case_municipality_weeks": total_zero,
            "observed_municipality_weeks": len(development_weekly),
            "proportion_zero_cases": total_zero / len(development_weekly),
        }
    )

    complete_development_targets = [
        row
        for row in development_targets
        if row.target_status == "complete" and row.target_training_eligible
    ]
    lockbox_window_excluded_targets = [
        row
        for row in complete_development_targets
        if row.target_window_end >= lockbox_start
    ]
    usable_targets = [
        row
        for row in complete_development_targets
        if row.target_window_end < lockbox_start and row.target_value is not None
    ]
    target_counts = Counter(int(row.target_value) for row in usable_targets)
    target_distribution_rows: list[dict[str, object]] = []
    cumulative_count = 0
    for target_value in sorted(target_counts):
        count = target_counts[target_value]
        cumulative_count += count
        target_distribution_rows.append(
            {
                "target_lyme_cases_next_4w": target_value,
                "municipality_week_count": count,
                "proportion": count / len(usable_targets),
                "cumulative_count": cumulative_count,
                "cumulative_proportion": cumulative_count / len(usable_targets),
                "issue_period_start": min(row.issue_week for row in usable_targets),
                "issue_period_end": max(row.issue_week for row in usable_targets),
                "target_window_end_max": max(
                    row.target_window_end for row in usable_targets
                ),
            }
        )

    target_status_counts = Counter(row.target_status for row in development_targets)
    supervised_summary_rows = [
        {
            "metric": "development_target_candidate_rows",
            "value": len(development_targets),
            "definition": "Rows with issue_week year inside the configured development period.",
            "period_start": min(row.issue_week for row in development_targets),
            "period_end": max(row.issue_week for row in development_targets),
        },
        {
            "metric": "target_complete_rows",
            "value": len(complete_development_targets),
            "definition": "Rows passing the Phase 5 target completeness rule.",
            "period_start": min(row.issue_week for row in development_targets),
            "period_end": max(row.issue_week for row in development_targets),
        },
        {
            "metric": "complete_rows_with_target_window_entering_lockbox",
            "value": len(lockbox_window_excluded_targets),
            "definition": "Target-complete rows excluded because target_window_end reaches 2025.",
            "period_start": min(row.issue_week for row in development_targets),
            "period_end": max(row.issue_week for row in development_targets),
        },
        {
            "metric": "usable_supervised_rows_after_completeness_and_lockbox_rules",
            "value": len(usable_targets),
            "definition": "Complete target rows whose entire target window ends before the lockbox.",
            "period_start": min(row.issue_week for row in usable_targets),
            "period_end": max(row.issue_week for row in usable_targets),
        },
        {
            "metric": "target_incomplete_rows",
            "value": len(development_targets) - len(complete_development_targets),
            "definition": "Development rows not passing target completeness.",
            "period_start": min(row.issue_week for row in development_targets),
            "period_end": max(row.issue_week for row in development_targets),
        },
    ]

    development_calendar = [
        row for row in calendar_rows if start_year <= row.issue_week.year <= end_year
    ]
    descriptive_period_text = f"{start_year}-{end_year} issue-week years"
    missing_rows: list[dict[str, object]] = []
    for column, values in {
        "municipality_code": [row.municipality_code for row in municipalities],
        "municipality_name": [row.municipality_name for row in municipalities],
    }.items():
        missing_rows.append(
            missing_summary_row("municipality", column, values, "canonical dimension")
        )
    for column, values in {
        "municipality_code": [
            row["municipality_code"] for row in population_output_rows
        ],
        "year": [row["year"] for row in population_output_rows],
        "population": [
            row["population_total_on_1_january"]
            for row in population_output_rows
        ],
    }.items():
        missing_rows.append(
            missing_summary_row(
                "population", column, values, descriptive_period_text
            )
        )
    for column, values in {
        "municipality_code": [row.municipality_code for row in development_weekly],
        "issue_week": [row.issue_week for row in development_weekly],
        "lyme_cases": [row.lyme_cases for row in development_weekly],
    }.items():
        missing_rows.append(
            missing_summary_row(
                "weekly_cases", column, values, descriptive_period_text
            )
        )
    for column, values in {
        "issue_week": [row.issue_week for row in development_calendar],
        "year": [row.iso_year for row in development_calendar],
        "iso_week": [row.iso_week for row in development_calendar],
    }.items():
        missing_rows.append(
            missing_summary_row("calendar", column, values, descriptive_period_text)
        )
    for column, values in {
        "municipality_code": [row.municipality_code for row in development_targets],
        "issue_week": [row.issue_week for row in development_targets],
        "target_window_start": [row.target_window_start for row in development_targets],
        "target_window_end": [row.target_window_end for row in development_targets],
        "target_status": [row.target_status for row in development_targets],
        "target_training_eligible": [
            row.target_training_eligible for row in development_targets
        ],
    }.items():
        missing_rows.append(
            missing_summary_row(
                "four_week_target_metadata", column, values, descriptive_period_text
            )
        )
    missing_rows.append(
        missing_summary_row(
            "lockbox_safe_four_week_target",
            "target_lyme_cases_next_4w",
            [row.target_value for row in usable_targets],
            descriptive_period_text,
        )
    )

    output_directory = resolve_repo_path(config["outputs"]["directory"])
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = {
        key: output_directory / filename
        for key, filename in config["outputs"].items()
        if key != "directory"
    }
    if any(path.parent != output_directory for path in output_paths.values()):
        raise DescriptiveEpidemiologyError(
            "Descriptive output filenames must not contain subdirectories."
        )

    table_specs: dict[str, tuple[Sequence[str], Sequence[Mapping[str, object]]]] = {
        "cases_by_year": (
            (
                "issue_year",
                "period_start",
                "period_end",
                "n_issue_weeks",
                "n_municipality_weeks",
                "reported_lyme_cases",
            ),
            cases_by_year_rows,
        ),
        "cases_by_week_of_year": (
            (
                "iso_week",
                "development_period_start",
                "development_period_end",
                "n_observed_issue_weeks",
                "n_municipality_weeks",
                "reported_lyme_cases",
            ),
            cases_by_week_rows,
        ),
        "cases_by_municipality": (
            (
                "municipality_code",
                "municipality_name",
                "period_start",
                "period_end",
                "n_issue_weeks",
                "n_municipality_weeks",
                "reported_lyme_cases",
            ),
            cases_by_municipality_rows,
        ),
        "population_by_municipality_year": (
            (
                "municipality_code",
                "municipality_name",
                "year",
                "population_total_on_1_january",
                "denominator_status",
            ),
            population_output_rows,
        ),
        "incidence_by_municipality_year": (
            (
                "municipality_code",
                "municipality_name",
                "issue_year",
                "numerator_period_start",
                "numerator_period_end",
                "reported_lyme_cases",
                "population_total_on_1_january",
                "incidence_per_100000",
                "denominator_status",
            ),
            incidence_rows,
        ),
        "incidence_by_year": (
            (
                "issue_year",
                "numerator_period_start",
                "numerator_period_end",
                "reported_lyme_cases_with_valid_denominator",
                "summed_population_total_on_1_january",
                "incidence_per_100000",
                "valid_denominator_municipalities",
                "excluded_denominator_municipalities",
                "denominator_status",
            ),
            incidence_by_year_rows,
        ),
        "zero_case_proportion": (
            (
                "period",
                "period_start",
                "period_end",
                "zero_case_municipality_weeks",
                "observed_municipality_weeks",
                "proportion_zero_cases",
            ),
            zero_case_rows,
        ),
        "target_distribution": (
            (
                "target_lyme_cases_next_4w",
                "municipality_week_count",
                "proportion",
                "cumulative_count",
                "cumulative_proportion",
                "issue_period_start",
                "issue_period_end",
                "target_window_end_max",
            ),
            target_distribution_rows,
        ),
        "missing_data_summary": (
            (
                "dataset",
                "column",
                "period",
                "n_rows",
                "n_missing",
                "missing_proportion",
            ),
            missing_rows,
        ),
        "supervised_row_summary": (
            ("metric", "value", "definition", "period_start", "period_end"),
            supervised_summary_rows,
        ),
    }
    for key, (columns, rows) in table_specs.items():
        write_csv_rows(output_paths[key], columns, rows)

    write_bar_plot(
        output_paths["cases_by_year_plot"],
        labels=[str(row["issue_year"]) for row in cases_by_year_rows],
        values=[float(row["reported_lyme_cases"]) for row in cases_by_year_rows],
        title="Reported Lyme cases by issue year",
        numerator="Canonical reported Lyme case counts",
        denominator="Not applicable; this plot shows case counts",
        period=period_label,
        x_label="Issue year (Gregorian year of issue_week Monday)",
        y_label="Reported Lyme cases",
    )
    write_bar_plot(
        output_paths["incidence_by_year_plot"],
        labels=[str(row["issue_year"]) for row in incidence_by_year_rows],
        values=[float(row["incidence_per_100000"]) for row in incidence_by_year_rows],
        title="Reported Lyme incidence per 100,000 by issue year",
        numerator="Reported Lyme cases in municipalities with valid population",
        denominator="Summed SURS population total on 1 January for those municipalities",
        period=period_label,
        x_label="Issue year (Gregorian year of issue_week Monday)",
        y_label="Reported Lyme incidence per 100,000",
    )
    target_period_label = (
        f"issue weeks {min(row.issue_week for row in usable_targets).isoformat()} "
        f"to {max(row.issue_week for row in usable_targets).isoformat()}; "
        f"target windows end by {max(row.target_window_end for row in usable_targets).isoformat()}"
    )
    write_ecdf_plot(
        output_paths["target_distribution_plot"],
        target_distribution=target_distribution_rows,
        denominator_count=len(usable_targets),
        period=target_period_label,
    )

    non_quality_output_records = {
        key: {
            **file_record(path),
            **(
                {"row_count": len(table_specs[key][1])}
                if key in table_specs
                else {"format": "svg"}
            ),
        }
        for key, path in output_paths.items()
        if key != "quality_summary"
    }
    total_reported_cases = sum(row.lyme_cases for row in development_weekly)
    valid_denominator_rows = sum(
        row["denominator_status"] == DENOMINATOR_VALID for row in incidence_rows
    )
    lockbox_case_rows_included = sum(
        row.issue_week.year >= lockbox_year for row in development_weekly
    )
    lockbox_target_values_used = sum(
        row.target_window_end >= lockbox_start for row in usable_targets
    )
    quality: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.evaluation.descriptive_epidemiology",
        "status": "pass",
        "sources": {
            **{key: file_record(path) for key, path in input_paths.items()},
            "config": file_record(config_path),
            "builder": file_record(Path(__file__).resolve()),
        },
        "period": {
            "development_start_year": start_year,
            "development_end_year": end_year,
            "actual_issue_week_start": period_start.isoformat(),
            "actual_issue_week_end": period_end.isoformat(),
            "year_definition": config["period"]["year_definition"],
            "week_of_year_definition": "canonical_iso_week",
            "excluded_lockbox_year": lockbox_year,
            "lockbox_input_rule": config["period"]["lockbox_input_rule"],
        },
        "summary": {
            "municipalities": len(municipalities),
            "development_municipality_week_rows": len(development_weekly),
            "reported_lyme_cases": total_reported_cases,
            "population_municipality_year_rows": len(population_output_rows),
            "valid_population_denominator_rows": valid_denominator_rows,
            "invalid_population_denominator_rows": len(incidence_rows)
            - valid_denominator_rows,
            "zero_case_municipality_weeks": total_zero,
            "observed_municipality_weeks_for_zero_proportion": len(
                development_weekly
            ),
            "proportion_zero_case_municipality_weeks": total_zero
            / len(development_weekly),
            "development_target_candidate_rows": len(development_targets),
            "target_status_counts": dict(sorted(target_status_counts.items())),
            "target_complete_rows": len(complete_development_targets),
            "complete_target_rows_entering_lockbox": len(
                lockbox_window_excluded_targets
            ),
            "usable_supervised_rows_after_completeness_and_lockbox_rules": len(
                usable_targets
            ),
            "target_distribution_minimum": min(target_counts),
            "target_distribution_maximum": max(target_counts),
        },
        "outputs": non_quality_output_records,
        "checks": {
            "all_weekly_case_codes_match_municipality": True,
            "all_population_codes_match_municipality": True,
            "all_target_codes_match_municipality": True,
            "all_weekly_dates_match_calendar": True,
            "missing_development_municipality_week_rows": len(
                missing_municipality_week_keys
            ),
            "incidence_uses_only_positive_present_population": True,
            "incidence_labelled_as_risk": False,
            "lockbox_case_rows_included": lockbox_case_rows_included,
            "lockbox_target_values_used": lockbox_target_values_used,
            "lockbox_rows_skipped_before_numeric_parsing": True,
            "causal_interpretations_created": False,
            "model_trained": False,
            "model_performance_computed": False,
        },
    }
    quality_path = output_paths["quality_summary"]
    quality_path.write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build reproducible development-period Lyme descriptive summaries."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the descriptive epidemiology configuration.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    quality = build_descriptive_epidemiology(config_path)
    summary = quality["summary"]
    print("Lyme descriptive epidemiology outputs built.")
    print(
        f"- period: {quality['period']['actual_issue_week_start']} to "
        f"{quality['period']['actual_issue_week_end']}"
    )
    print(f"- reported Lyme cases: {summary['reported_lyme_cases']}")
    print(
        "- zero-case municipality-weeks: "
        f"{summary['zero_case_municipality_weeks']} / "
        f"{summary['observed_municipality_weeks_for_zero_proportion']} "
        f"({summary['proportion_zero_case_municipality_weeks']:.6f})"
    )
    print(
        "- usable supervised rows after completeness and lockbox rules: "
        f"{summary['usable_supervised_rows_after_completeness_and_lockbox_rules']}"
    )
    print(f"- lockbox year excluded: {quality['period']['excluded_lockbox_year']}")
    print("No model was trained and no causal interpretation was made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
