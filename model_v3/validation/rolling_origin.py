from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "lyme_rolling_origin_validation.json"
)

STATUS_COMPLETE = "complete"
SPLIT_TRAIN = "train"
SPLIT_VALIDATION = "validation"

MANIFEST_COLUMNS = (
    "fold_id",
    "train_issue_start",
    "train_issue_end",
    "train_target_end_max",
    "validation_start",
    "validation_end",
    "n_train",
    "n_validation",
    "number_of_purged_rows",
    "n_train_boundary_purged",
    "n_validation_boundary_purged",
    "n_ineligible_excluded",
)


class RollingOriginValidationError(ValueError):
    """Raised when target metadata or fold policy violates its contract."""


@dataclass(frozen=True, order=True)
class TargetWindowRow:
    municipality_code: str
    issue_week: date
    target_window_start: date
    target_window_end: date
    target_status: str
    target_training_eligible: bool


@dataclass(frozen=True)
class RollingOriginFold:
    fold_id: str
    train_rows: tuple[TargetWindowRow, ...]
    validation_rows: tuple[TargetWindowRow, ...]
    train_boundary_purged_rows: tuple[TargetWindowRow, ...]
    validation_boundary_purged_rows: tuple[TargetWindowRow, ...]
    n_ineligible_excluded: int
    validation_start: date
    validation_end: date

    def manifest_record(self) -> dict[str, object]:
        if not self.train_rows or not self.validation_rows:
            raise RollingOriginValidationError(
                f"{self.fold_id} cannot produce a manifest with an empty split."
            )
        train_issue_dates = [row.issue_week for row in self.train_rows]
        train_target_ends = [row.target_window_end for row in self.train_rows]
        return {
            "fold_id": self.fold_id,
            "train_issue_start": min(train_issue_dates),
            "train_issue_end": max(train_issue_dates),
            "train_target_end_max": max(train_target_ends),
            "validation_start": self.validation_start,
            "validation_end": self.validation_end,
            "n_train": len(self.train_rows),
            "n_validation": len(self.validation_rows),
            "number_of_purged_rows": len(self.train_boundary_purged_rows)
            + len(self.validation_boundary_purged_rows),
            "n_train_boundary_purged": len(self.train_boundary_purged_rows),
            "n_validation_boundary_purged": len(
                self.validation_boundary_purged_rows
            ),
            "n_ineligible_excluded": self.n_ineligible_excluded,
        }


def resolve_repo_path(raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise RollingOriginValidationError(
            f"Configured path must be a non-empty string: {raw_path!r}"
        )
    relative = Path(raw_path)
    if relative.is_absolute():
        raise RollingOriginValidationError(
            f"Configured path must be repository-relative: {raw_path}"
        )
    resolved = (REPO_ROOT / relative).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise RollingOriginValidationError(
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
        raise RollingOriginValidationError(
            f"Validation configuration must be inside the repository: {path}"
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise RollingOriginValidationError(
            "Validation configuration schema_version must equal 1."
        )
    input_config = config.get("input")
    policy_config = config.get("policy")
    output_config = config.get("output")
    if not all(
        isinstance(value, dict)
        for value in (input_config, policy_config, output_config)
    ):
        raise RollingOriginValidationError(
            "Validation input, policy, and output configuration are required."
        )

    expected_input_columns = {
        "municipality_code_column": "municipality_code",
        "issue_week_column": "issue_week",
        "target_window_start_column": "target_window_start",
        "target_window_end_column": "target_window_end",
        "target_status_column": "target_status",
        "target_training_eligibility_column": "target_training_eligible",
    }
    for key, expected in expected_input_columns.items():
        if input_config.get(key) != expected:
            raise RollingOriginValidationError(
                f"Validation input {key} must equal {expected!r}."
            )
    if not isinstance(input_config.get("path"), str) or not input_config["path"]:
        raise RollingOriginValidationError(
            "Validation input path must be a non-empty string."
        )

    expected_policy_values = {
        "fold_strategy": "expanding_window_next_available_year",
        "required_target_status": STATUS_COMPLETE,
        "train_target_end_rule": "strictly_before_validation_start",
        "validation_target_window_rule": "fully_contained_in_validation_period",
    }
    for key, expected in expected_policy_values.items():
        if policy_config.get(key) != expected:
            raise RollingOriginValidationError(
                f"Validation policy {key} must equal {expected!r}."
            )
    for key in (
        "development_start_year",
        "development_end_year",
        "lockbox_year",
    ):
        value = policy_config.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise RollingOriginValidationError(
                f"Validation policy {key} must be an integer."
            )
    if policy_config["development_start_year"] > policy_config[
        "development_end_year"
    ]:
        raise RollingOriginValidationError(
            "development_start_year must not exceed development_end_year."
        )
    if policy_config["development_end_year"] >= policy_config["lockbox_year"]:
        raise RollingOriginValidationError(
            "Development years must end before the lockbox year."
        )

    for key in ("directory", "fold_manifest", "quality_summary"):
        if not isinstance(output_config.get(key), str) or not output_config[key]:
            raise RollingOriginValidationError(
                f"Validation output {key} must be a non-empty string."
            )
    return config


def parse_monday(value: object, *, context: str) -> date:
    if isinstance(value, date):
        result = value
    elif isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as exc:
            raise RollingOriginValidationError(
                f"{context} is not an ISO date: {value!r}"
            ) from exc
    else:
        raise RollingOriginValidationError(f"{context} is not a date: {value!r}")
    if result.weekday() != 0:
        raise RollingOriginValidationError(
            f"{context} must be a Monday: {result.isoformat()}"
        )
    return result


def parse_boolean(value: object, *, context: str) -> bool:
    if isinstance(value, bool):
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    raise RollingOriginValidationError(
        f"{context} must be true or false: {value!r}"
    )


def normalize_target_metadata_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[TargetWindowRow]:
    normalized: list[TargetWindowRow] = []
    for row_index, row in enumerate(rows, start=1):
        raw_code = row.get("municipality_code")
        municipality_code = str(raw_code).strip() if raw_code is not None else ""
        if not re.fullmatch(r"\d{3}", municipality_code):
            raise RollingOriginValidationError(
                f"target row {row_index} municipality_code must be three digits: "
                f"{raw_code!r}"
            )
        issue_week = parse_monday(
            row.get("issue_week"), context=f"target row {row_index} issue_week"
        )
        target_window_start = parse_monday(
            row.get("target_window_start"),
            context=f"target row {row_index} target_window_start",
        )
        target_window_end = parse_monday(
            row.get("target_window_end"),
            context=f"target row {row_index} target_window_end",
        )
        if target_window_start != issue_week + timedelta(weeks=1):
            raise RollingOriginValidationError(
                f"target row {row_index} target_window_start is not exactly t+1."
            )
        if target_window_end != issue_week + timedelta(weeks=4):
            raise RollingOriginValidationError(
                f"target row {row_index} target_window_end is not exactly t+4."
            )
        raw_status = row.get("target_status")
        target_status = str(raw_status).strip() if raw_status is not None else ""
        if not target_status:
            raise RollingOriginValidationError(
                f"target row {row_index} target_status must be present."
            )
        target_training_eligible = parse_boolean(
            row.get("target_training_eligible"),
            context=f"target row {row_index} target_training_eligible",
        )
        expected_eligible = target_status == STATUS_COMPLETE
        if target_training_eligible is not expected_eligible:
            raise RollingOriginValidationError(
                f"target row {row_index} status and eligibility disagree."
            )
        normalized.append(
            TargetWindowRow(
                municipality_code=municipality_code,
                issue_week=issue_week,
                target_window_start=target_window_start,
                target_window_end=target_window_end,
                target_status=target_status,
                target_training_eligible=target_training_eligible,
            )
        )
    if not normalized:
        raise RollingOriginValidationError("Lyme target metadata input is empty.")

    key_counts = Counter(
        (row.municipality_code, row.issue_week) for row in normalized
    )
    duplicates = [
        (municipality_code, issue_week.isoformat())
        for (municipality_code, issue_week), count in sorted(key_counts.items())
        if count > 1
    ]
    if duplicates:
        raise RollingOriginValidationError(
            "Lyme target metadata has duplicate municipality-week rows: "
            f"{duplicates[:20]}"
        )
    return sorted(normalized)


def read_target_metadata(path: Path) -> list[TargetWindowRow]:
    required_columns = {
        "municipality_code",
        "issue_week",
        "target_window_start",
        "target_window_end",
        "target_status",
        "target_training_eligible",
    }
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        observed_columns = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - observed_columns)
        if missing_columns:
            raise RollingOriginValidationError(
                f"Lyme target metadata is missing columns: {missing_columns}"
            )
        rows = [
            {column: row[column] for column in required_columns}
            for row in reader
        ]
    return normalize_target_metadata_rows(rows)


def generate_rolling_origin_folds(
    target_rows: Sequence[Mapping[str, object]] | Sequence[TargetWindowRow],
    *,
    development_start_year: int,
    development_end_year: int,
    lockbox_year: int,
) -> list[RollingOriginFold]:
    if development_start_year > development_end_year:
        raise RollingOriginValidationError(
            "development_start_year must not exceed development_end_year."
        )
    if development_end_year >= lockbox_year:
        raise RollingOriginValidationError(
            "Development years must end before the lockbox year."
        )
    if all(isinstance(row, TargetWindowRow) for row in target_rows):
        rows = sorted(target_rows)  # type: ignore[arg-type]
    else:
        rows = normalize_target_metadata_rows(target_rows)  # type: ignore[arg-type]

    development_rows = [
        row
        for row in rows
        if development_start_year <= row.issue_week.year <= development_end_year
    ]
    available_years = sorted({row.issue_week.year for row in development_rows})
    if len(available_years) < 2:
        raise RollingOriginValidationError(
            "At least two actually available development years are required."
        )

    folds: list[RollingOriginFold] = []
    for fold_number, validation_year in enumerate(available_years[1:], start=1):
        validation_year_rows = [
            row for row in development_rows if row.issue_week.year == validation_year
        ]
        validation_start = min(row.issue_week for row in validation_year_rows)
        validation_end = max(row.issue_week for row in validation_year_rows)

        raw_train_candidates = [
            row for row in development_rows if row.issue_week < validation_start
        ]
        raw_validation_candidates = validation_year_rows
        eligible_train_candidates = [
            row for row in raw_train_candidates if row.target_training_eligible
        ]
        eligible_validation_candidates = [
            row for row in raw_validation_candidates if row.target_training_eligible
        ]

        train_rows = tuple(
            row
            for row in eligible_train_candidates
            if row.target_window_end < validation_start
        )
        train_boundary_purged_rows = tuple(
            row
            for row in eligible_train_candidates
            if row.target_window_end >= validation_start
        )
        validation_rows = tuple(
            row
            for row in eligible_validation_candidates
            if row.target_window_start >= validation_start
            and row.target_window_end <= validation_end
        )
        validation_boundary_purged_rows = tuple(
            row
            for row in eligible_validation_candidates
            if row.target_window_start < validation_start
            or row.target_window_end > validation_end
        )
        n_ineligible_excluded = (
            len(raw_train_candidates)
            - len(eligible_train_candidates)
            + len(raw_validation_candidates)
            - len(eligible_validation_candidates)
        )

        fold = RollingOriginFold(
            fold_id=f"fold_{fold_number:02d}_validate_{validation_year}",
            train_rows=train_rows,
            validation_rows=validation_rows,
            train_boundary_purged_rows=train_boundary_purged_rows,
            validation_boundary_purged_rows=validation_boundary_purged_rows,
            n_ineligible_excluded=n_ineligible_excluded,
            validation_start=validation_start,
            validation_end=validation_end,
        )
        validate_fold(fold, lockbox_year=lockbox_year)
        folds.append(fold)
    return folds


def validate_fold(fold: RollingOriginFold, *, lockbox_year: int) -> None:
    if not fold.train_rows:
        raise RollingOriginValidationError(f"{fold.fold_id} has no training rows.")
    if not fold.validation_rows:
        raise RollingOriginValidationError(
            f"{fold.fold_id} has no contained validation target windows."
        )
    if any(
        row.target_window_end >= fold.validation_start for row in fold.train_rows
    ):
        raise RollingOriginValidationError(
            f"{fold.fold_id} has a training target overlapping validation."
        )
    if any(
        row.target_window_start < fold.validation_start
        or row.target_window_end > fold.validation_end
        for row in fold.validation_rows
    ):
        raise RollingOriginValidationError(
            f"{fold.fold_id} has a validation target outside its period."
        )
    selected_rows = fold.train_rows + fold.validation_rows
    if any(row.issue_week.year >= lockbox_year for row in selected_rows):
        raise RollingOriginValidationError(
            f"{fold.fold_id} contains a lockbox issue week."
        )
    if any(row.target_window_end.year >= lockbox_year for row in selected_rows):
        raise RollingOriginValidationError(
            f"{fold.fold_id} contains a target window entering the lockbox."
        )


def csv_value(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    return value


def write_manifest(path: Path, folds: Sequence[RollingOriginFold]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(MANIFEST_COLUMNS), lineterminator="\n"
        )
        writer.writeheader()
        for fold in folds:
            record = fold.manifest_record()
            writer.writerow(
                {column: csv_value(record[column]) for column in MANIFEST_COLUMNS}
            )


def build_rolling_origin_validation(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    input_path = resolve_repo_path(config["input"]["path"])
    if not input_path.is_file():
        raise RollingOriginValidationError(
            f"Lyme target metadata input does not exist: {input_path}"
        )

    output_directory = resolve_repo_path(config["output"]["directory"])
    manifest_path = output_directory / config["output"]["fold_manifest"]
    quality_path = output_directory / config["output"]["quality_summary"]
    if manifest_path.parent != output_directory or quality_path.parent != output_directory:
        raise RollingOriginValidationError(
            "Validation output filenames must not contain subdirectories."
        )

    policy = config["policy"]
    target_rows = read_target_metadata(input_path)
    folds = generate_rolling_origin_folds(
        target_rows,
        development_start_year=policy["development_start_year"],
        development_end_year=policy["development_end_year"],
        lockbox_year=policy["lockbox_year"],
    )
    write_manifest(manifest_path, folds)

    development_rows = [
        row
        for row in target_rows
        if policy["development_start_year"]
        <= row.issue_week.year
        <= policy["development_end_year"]
    ]
    available_years = sorted({row.issue_week.year for row in development_rows})
    manifest_records = [fold.manifest_record() for fold in folds]
    selected_rows = [
        row
        for fold in folds
        for row in fold.train_rows + fold.validation_rows
    ]
    lockbox_issue_rows_returned = sum(
        row.issue_week.year >= policy["lockbox_year"] for row in selected_rows
    )
    target_windows_entering_lockbox_returned = sum(
        row.target_window_end.year >= policy["lockbox_year"]
        for row in selected_rows
    )
    quality: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.validation.rolling_origin",
        "status": "pass",
        "sources": {
            "target_metadata": file_record(input_path),
            "config": file_record(config_path),
            "builder": file_record(Path(__file__).resolve()),
        },
        "policy": {
            "configured_development_years": [
                policy["development_start_year"],
                policy["development_end_year"],
            ],
            "available_development_years": available_years,
            "lockbox_year": policy["lockbox_year"],
            "fold_strategy": policy["fold_strategy"],
            "training_rule": "target_window_end < validation_start",
            "validation_rule": (
                "target_window_start >= validation_start and "
                "target_window_end <= validation_end"
            ),
        },
        "dataset": {
            "manifest_path": str(manifest_path.relative_to(REPO_ROOT)),
            "manifest_columns": list(MANIFEST_COLUMNS),
            "fold_count": len(folds),
            "validation_years": [fold.validation_start.year for fold in folds],
            "manifest_sha256": sha256_file(manifest_path),
            "manifest_bytes": manifest_path.stat().st_size,
        },
        "folds": [
            {key: csv_value(value) for key, value in record.items()}
            for record in manifest_records
        ],
        "checks": {
            "all_train_target_windows_end_before_validation": all(
                row.target_window_end < fold.validation_start
                for fold in folds
                for row in fold.train_rows
            ),
            "all_validation_target_windows_contained": all(
                row.target_window_start >= fold.validation_start
                and row.target_window_end <= fold.validation_end
                for fold in folds
                for row in fold.validation_rows
            ),
            "lockbox_issue_rows_returned": lockbox_issue_rows_returned,
            "target_windows_entering_lockbox_returned": (
                target_windows_entering_lockbox_returned
            ),
            "lockbox_rows_used_for_fold_boundaries": False,
            "numeric_target_values_used": False,
            "lockbox_target_values_used": False,
            "lockbox_performance_computed": False,
            "model_trained": False,
            "features_created": False,
        },
    }
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return quality


def print_fold_manifest(folds: Sequence[Mapping[str, object]]) -> None:
    print("Lyme rolling-origin development folds:")
    for fold in folds:
        print(
            f"- {fold['fold_id']}: train {fold['train_issue_start']}.."
            f"{fold['train_issue_end']} (n={fold['n_train']}, "
            f"target_end_max={fold['train_target_end_max']}), validate "
            f"{fold['validation_start']}..{fold['validation_end']} "
            f"(n={fold['n_validation']}), purged="
            f"{fold['number_of_purged_rows']}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate leakage-safe rolling-origin Lyme development folds."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the rolling-origin validation configuration.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    quality = build_rolling_origin_validation(config_path)
    print("Rolling-origin validation manifest built.")
    print(f"- folds: {quality['dataset']['fold_count']}")
    print(f"- development years: {quality['policy']['available_development_years']}")
    print(f"- lockbox year excluded: {quality['policy']['lockbox_year']}")
    print(f"- output: {quality['dataset']['manifest_path']}")
    print_fold_manifest(quality["folds"])
    print("No model was trained and no lockbox performance was computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
