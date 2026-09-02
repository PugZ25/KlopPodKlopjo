from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "lyme_four_week_target.json"

TARGET_COLUMN = "target_lyme_cases_next_4w"
TARGET_WINDOW_START_COLUMN = "target_window_start"
TARGET_WINDOW_END_COLUMN = "target_window_end"
TARGET_STATUS_COLUMN = "target_status"
TARGET_TRAINING_ELIGIBILITY_COLUMN = "target_training_eligible"
TARGET_WEEK_OFFSETS = (1, 2, 3, 4)

STATUS_COMPLETE = "complete"
STATUS_INCOMPLETE_FUTURE_HORIZON = "incomplete_future_horizon"
STATUS_MISSING_FUTURE_WEEK = "missing_future_week"
TARGET_STATUSES = (
    STATUS_COMPLETE,
    STATUS_INCOMPLETE_FUTURE_HORIZON,
    STATUS_MISSING_FUTURE_WEEK,
)

OUTPUT_COLUMNS = (
    "municipality_code",
    "issue_week",
    TARGET_COLUMN,
    TARGET_WINDOW_START_COLUMN,
    TARGET_WINDOW_END_COLUMN,
    TARGET_STATUS_COLUMN,
    TARGET_TRAINING_ELIGIBILITY_COLUMN,
)


class TargetValidationError(ValueError):
    """Raised when the target input or output violates its contract."""


def resolve_repo_path(raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise TargetValidationError(f"Configured path must be a non-empty string: {raw_path!r}")
    relative = Path(raw_path)
    if relative.is_absolute():
        raise TargetValidationError(f"Configured path must be repository-relative: {raw_path}")
    resolved = (REPO_ROOT / relative).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise TargetValidationError(f"Configured path leaves repository root: {raw_path}")
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
        raise TargetValidationError(f"Target configuration must be inside the repository: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise TargetValidationError("Target configuration schema_version must equal 1.")
    input_config = config.get("input")
    target_config = config.get("target")
    lockbox_config = config.get("lockbox")
    output_config = config.get("output")
    if not all(
        isinstance(value, dict)
        for value in (input_config, target_config, lockbox_config, output_config)
    ):
        raise TargetValidationError(
            "Target input, target, lockbox, and output configuration are required."
        )

    expected_input_columns = {
        "municipality_code_column": "municipality_code",
        "issue_week_column": "issue_week",
        "lyme_cases_column": "lyme_cases",
    }
    for key, expected in expected_input_columns.items():
        if input_config.get(key) != expected:
            raise TargetValidationError(f"Target input {key} must equal {expected!r}.")

    expected_target_fields = {
        "column": TARGET_COLUMN,
        "window_start_column": TARGET_WINDOW_START_COLUMN,
        "window_end_column": TARGET_WINDOW_END_COLUMN,
        "status_column": TARGET_STATUS_COLUMN,
        "training_eligibility_column": TARGET_TRAINING_ELIGIBILITY_COLUMN,
    }
    for key, expected in expected_target_fields.items():
        if target_config.get(key) != expected:
            raise TargetValidationError(f"Target configuration {key} must equal {expected!r}.")
    if target_config.get("included_week_offsets") != list(TARGET_WEEK_OFFSETS):
        raise TargetValidationError(
            "The Lyme target must include exactly week offsets [1, 2, 3, 4]."
        )

    expected_lockbox = {
        "year": 2025,
        "input_row_rule": "skip_at_or_after_lockbox_start_before_numeric_parsing",
        "target_materialization_rule": "issue_week_strictly_before_lockbox_start",
    }
    if lockbox_config != expected_lockbox:
        raise TargetValidationError(
            "Target lockbox configuration does not match the sealed 2025 policy."
        )

    for key in ("path",):
        if not isinstance(input_config.get(key), str) or not input_config[key]:
            raise TargetValidationError(f"Target input {key} must be a non-empty string.")
    for key in ("directory", "target_dataset", "quality_summary"):
        if not isinstance(output_config.get(key), str) or not output_config[key]:
            raise TargetValidationError(f"Target output {key} must be a non-empty string.")
    return config


def parse_issue_week(value: object, *, context: str) -> date:
    if isinstance(value, date):
        result = value
    elif isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as exc:
            raise TargetValidationError(f"{context} is not an ISO date: {value!r}") from exc
    else:
        raise TargetValidationError(f"{context} is not a date: {value!r}")
    if result.weekday() != 0:
        raise TargetValidationError(f"{context} must be a Monday: {result.isoformat()}")
    return result


def parse_lyme_cases(value: object, *, context: str) -> int:
    if isinstance(value, bool):
        raise TargetValidationError(f"{context} must not be boolean: {value!r}")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(r"\d+", value):
        result = int(value)
    else:
        raise TargetValidationError(
            f"{context} must be a present non-negative integer: {value!r}"
        )
    if result < 0:
        raise TargetValidationError(f"{context} must not be negative: {result}")
    return result


def normalize_weekly_lyme_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row_index, row in enumerate(rows, start=1):
        raw_code = row.get("municipality_code")
        code = str(raw_code).strip() if raw_code is not None else ""
        if not re.fullmatch(r"\d{3}", code):
            raise TargetValidationError(
                f"weekly_cases row {row_index} municipality_code must be three digits: {raw_code!r}"
            )
        issue_week = parse_issue_week(
            row.get("issue_week"), context=f"weekly_cases row {row_index} issue_week"
        )
        lyme_cases = parse_lyme_cases(
            row.get("lyme_cases"), context=f"weekly_cases[{code}, {issue_week}] lyme_cases"
        )
        normalized.append(
            {
                "municipality_code": code,
                "issue_week": issue_week,
                "lyme_cases": lyme_cases,
            }
        )
    if not normalized:
        raise TargetValidationError("Canonical weekly Lyme input is empty.")

    key_counts = Counter(
        (str(row["municipality_code"]), row["issue_week"]) for row in normalized
    )
    duplicates = [
        {"municipality_code": code, "issue_week": issue_week.isoformat()}
        for (code, issue_week), count in sorted(key_counts.items())
        if count > 1
    ]
    if duplicates:
        raise TargetValidationError(
            f"Canonical weekly Lyme input has duplicate municipality-week rows: {duplicates[:20]}"
        )
    normalized.sort(key=lambda row: (str(row["municipality_code"]), row["issue_week"]))
    return normalized


def read_canonical_weekly_lyme(
    path: Path, *, lockbox_year: int
) -> tuple[list[dict[str, object]], int]:
    lockbox_start = date(lockbox_year, 1, 1)
    rows: list[dict[str, object]] = []
    skipped_lockbox_rows = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"municipality_code", "issue_week", "lyme_cases"}
        observed_columns = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - observed_columns)
        if missing_columns:
            raise TargetValidationError(
                f"Canonical weekly Lyme input is missing columns: {missing_columns}"
            )
        for row_index, row in enumerate(reader, start=1):
            issue_week = parse_issue_week(
                row["issue_week"], context=f"weekly_cases row {row_index} issue_week"
            )
            if issue_week >= lockbox_start:
                skipped_lockbox_rows += 1
                continue
            rows.append(
                {
                    "municipality_code": row["municipality_code"],
                    "issue_week": issue_week,
                    "lyme_cases": row["lyme_cases"],
                }
            )
    return normalize_weekly_lyme_rows(rows), skipped_lockbox_rows


def calculate_lyme_four_week_targets(
    weekly_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Calculate exactly t+1 through t+4 independently within municipality."""

    normalized = normalize_weekly_lyme_rows(weekly_rows)
    municipality_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in normalized:
        municipality_groups[str(row["municipality_code"])].append(row)

    target_rows: list[dict[str, object]] = []
    for municipality_code in sorted(municipality_groups):
        municipality_rows = sorted(
            municipality_groups[municipality_code], key=lambda row: row["issue_week"]
        )
        cases_by_week = {
            row["issue_week"]: int(row["lyme_cases"]) for row in municipality_rows
        }
        final_observed_week = municipality_rows[-1]["issue_week"]
        for row in municipality_rows:
            issue_week = row["issue_week"]
            required_future_weeks = [
                issue_week + timedelta(weeks=offset) for offset in TARGET_WEEK_OFFSETS
            ]
            missing_future_weeks = [
                future_week
                for future_week in required_future_weeks
                if future_week not in cases_by_week
            ]
            if not missing_future_weeks:
                status = STATUS_COMPLETE
                target_value: int | None = sum(
                    cases_by_week[future_week] for future_week in required_future_weeks
                )
                training_eligible = True
            elif any(
                future_week <= final_observed_week
                for future_week in missing_future_weeks
            ):
                status = STATUS_MISSING_FUTURE_WEEK
                target_value = None
                training_eligible = False
            else:
                status = STATUS_INCOMPLETE_FUTURE_HORIZON
                target_value = None
                training_eligible = False

            target_rows.append(
                {
                    "municipality_code": municipality_code,
                    "issue_week": issue_week,
                    TARGET_COLUMN: target_value,
                    TARGET_WINDOW_START_COLUMN: required_future_weeks[0],
                    TARGET_WINDOW_END_COLUMN: required_future_weeks[-1],
                    TARGET_STATUS_COLUMN: status,
                    TARGET_TRAINING_ELIGIBILITY_COLUMN: training_eligible,
                }
            )

    target_rows.sort(
        key=lambda row: (str(row["municipality_code"]), row["issue_week"])
    )
    validate_target_rows(target_rows)
    return target_rows


def validate_target_rows(rows: Sequence[Mapping[str, object]]) -> None:
    key_counts = Counter(
        (str(row["municipality_code"]), row["issue_week"]) for row in rows
    )
    duplicates = [key for key, count in key_counts.items() if count > 1]
    if duplicates:
        raise TargetValidationError(
            f"Target output has duplicate municipality-week rows: {duplicates[:20]}"
        )
    for row in rows:
        status = row[TARGET_STATUS_COLUMN]
        target_value = row[TARGET_COLUMN]
        eligible = row[TARGET_TRAINING_ELIGIBILITY_COLUMN]
        issue_week = row["issue_week"]
        if status not in TARGET_STATUSES:
            raise TargetValidationError(f"Unknown target status: {status!r}")
        if row[TARGET_WINDOW_START_COLUMN] != issue_week + timedelta(weeks=1):
            raise TargetValidationError("target_window_start is not exactly t+1.")
        if row[TARGET_WINDOW_END_COLUMN] != issue_week + timedelta(weeks=4):
            raise TargetValidationError("target_window_end is not exactly t+4.")
        if status == STATUS_COMPLETE:
            if not isinstance(target_value, int) or target_value < 0 or eligible is not True:
                raise TargetValidationError(
                    "Complete target rows require a non-negative integer target and eligibility=true."
                )
        elif target_value is not None or eligible is not False:
            raise TargetValidationError(
                "Incomplete target rows require a missing target and eligibility=false."
            )


def csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_target_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OUTPUT_COLUMNS), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row[column]) for column in OUTPUT_COLUMNS})


def build_calculation_example(
    weekly_rows: Sequence[Mapping[str, object]],
    target_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    cases_by_key = {
        (str(row["municipality_code"]), row["issue_week"]): int(row["lyme_cases"])
        for row in weekly_rows
    }
    complete_rows = [
        row for row in target_rows if row[TARGET_STATUS_COLUMN] == STATUS_COMPLETE
    ]
    if not complete_rows:
        raise TargetValidationError("No complete target row is available for the example.")
    selected = next(
        (row for row in complete_rows if int(row[TARGET_COLUMN]) > 0),
        complete_rows[0],
    )
    municipality_code = str(selected["municipality_code"])
    issue_week = selected["issue_week"]
    included_weeks = [
        issue_week + timedelta(weeks=offset) for offset in TARGET_WEEK_OFFSETS
    ]
    included_values = [
        cases_by_key[(municipality_code, future_week)]
        for future_week in included_weeks
    ]
    if sum(included_values) != selected[TARGET_COLUMN]:
        raise TargetValidationError("Calculation example does not reproduce its target.")
    return {
        "municipality_code": municipality_code,
        "issue_week": issue_week.isoformat(),
        "included_week_offsets": list(TARGET_WEEK_OFFSETS),
        "included_weeks": [value.isoformat() for value in included_weeks],
        "included_lyme_cases": included_values,
        "calculation": " + ".join(str(value) for value in included_values),
        "target": selected[TARGET_COLUMN],
        "issue_week_t_included": False,
        "weeks_after_t_plus_4_included": False,
    }


def build_lyme_four_week_target(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    input_path = resolve_repo_path(config["input"]["path"])
    if not input_path.is_file():
        raise TargetValidationError(f"Canonical weekly Lyme input does not exist: {input_path}")

    output_directory = resolve_repo_path(config["output"]["directory"])
    target_path = output_directory / config["output"]["target_dataset"]
    quality_path = output_directory / config["output"]["quality_summary"]
    if target_path.parent != output_directory or quality_path.parent != output_directory:
        raise TargetValidationError("Target output filenames must not contain subdirectories.")

    lockbox_year = config["lockbox"]["year"]
    lockbox_start = date(lockbox_year, 1, 1)
    weekly_rows, skipped_lockbox_rows = read_canonical_weekly_lyme(
        input_path, lockbox_year=lockbox_year
    )
    target_rows = calculate_lyme_four_week_targets(weekly_rows)
    if any(row["issue_week"] >= lockbox_start for row in target_rows):
        raise TargetValidationError("Target output contains a lockbox issue week.")
    complete_windows_entering_lockbox = sum(
        row[TARGET_STATUS_COLUMN] == STATUS_COMPLETE
        and row[TARGET_WINDOW_END_COLUMN] >= lockbox_start
        for row in target_rows
    )
    if complete_windows_entering_lockbox:
        raise TargetValidationError(
            "A complete target window enters the sealed lockbox."
        )
    write_target_csv(target_path, target_rows)

    status_counts = Counter(str(row[TARGET_STATUS_COLUMN]) for row in target_rows)
    complete_targets = [
        int(row[TARGET_COLUMN])
        for row in target_rows
        if row[TARGET_STATUS_COLUMN] == STATUS_COMPLETE
    ]
    example = build_calculation_example(weekly_rows, target_rows)
    quality: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.panel.lyme_four_week_target",
        "status": "pass",
        "sources": {
            "canonical_weekly_cases": file_record(input_path),
            "config": file_record(config_path),
            "builder": file_record(Path(__file__).resolve()),
        },
        "target_definition": {
            "analysis_unit": ["municipality_code", "issue_week"],
            "target_column": TARGET_COLUMN,
            "included_week_offsets": list(TARGET_WEEK_OFFSETS),
            "issue_week_t_included": False,
            "weeks_after_t_plus_4_included": False,
            "calculation_is_within_municipality": True,
            "chronological_order_is_explicit": True,
        },
        "dataset": {
            "path": str(target_path.relative_to(REPO_ROOT)),
            "columns": list(OUTPUT_COLUMNS),
            "primary_key": ["municipality_code", "issue_week"],
            "row_count": len(target_rows),
            "status_counts": {
                status: status_counts.get(status, 0) for status in TARGET_STATUSES
            },
            "training_eligible_row_count": status_counts.get(STATUS_COMPLETE, 0),
            "training_ineligible_row_count": len(target_rows)
            - status_counts.get(STATUS_COMPLETE, 0),
            "missing_target_value_count": sum(
                row[TARGET_COLUMN] is None for row in target_rows
            ),
            "minimum_complete_target": min(complete_targets),
            "maximum_complete_target": max(complete_targets),
            "unexpected_duplicate_rows": [],
            "sha256": sha256_file(target_path),
            "bytes": target_path.stat().st_size,
        },
        "checks": {
            "current_week_excluded": True,
            "exactly_t_plus_1_through_t_plus_4_included": True,
            "missing_future_weeks_imputed_as_zero": False,
            "incomplete_rows_training_eligible": False,
            "year_boundaries_use_date_arithmetic": True,
            "iso_week_edges_use_date_arithmetic": True,
            "feature_columns_created": False,
            "eight_week_target_created": False,
            "kme_target_created": False,
            "predictive_model_created": False,
        },
        "lockbox": {
            "year": lockbox_year,
            "start": lockbox_start.isoformat(),
            "input_rows_skipped_before_numeric_parsing": skipped_lockbox_rows,
            "numeric_case_values_parsed_from_lockbox": 0,
            "target_issue_rows_materialized": 0,
            "complete_target_windows_entering_lockbox": (
                complete_windows_entering_lockbox
            ),
            "late_development_rows_remain_explicitly_incomplete": True,
            "used_for_target_definition_or_selection": False,
        },
        "calculation_example": example,
    }
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return quality


def print_calculation_example(example: Mapping[str, object]) -> None:
    print("Example four-week Lyme target calculation:")
    print(f"- municipality_code: {example['municipality_code']}")
    print(f"- issue_week t: {example['issue_week']} (excluded)")
    print(
        "- included weeks t+1..t+4: "
        + ", ".join(str(value) for value in example["included_weeks"])
    )
    print(
        f"- calculation: {example['calculation']} = {example['target']}"
    )
    print("- t+5 and later: excluded")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the primary Lyme t+1 through t+4 target."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the Lyme four-week target configuration.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    quality = build_lyme_four_week_target(config_path)
    dataset = quality["dataset"]
    print("Lyme four-week forecast target built.")
    print(f"- rows: {dataset['row_count']}")
    print(f"- status_counts: {dataset['status_counts']}")
    print(f"- training_eligible_rows: {dataset['training_eligible_row_count']}")
    print(f"- output: {dataset['path']}")
    print_calculation_example(quality["calculation_example"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
