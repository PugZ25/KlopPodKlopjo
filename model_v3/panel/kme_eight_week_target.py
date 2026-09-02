from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "kme_eight_week_target.json"
OUTPUT_COLUMNS = (
    "statistical_region_code",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "target_kme_cases_next_8w",
    "target_status",
    "target_training_eligible",
)


class KmeTargetError(ValueError):
    """Raised when the KME target contract cannot be satisfied."""


@dataclass(frozen=True)
class TargetRow:
    statistical_region_code: str
    issue_week: date
    target_window_start: date
    target_window_end: date
    target_value: int | None
    target_status: str
    training_eligible: bool


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
    target = config.get("target", {})
    if config.get("schema_version") != 1:
        raise KmeTargetError("Unsupported KME target schema_version")
    if target.get("horizon_weeks") != 8:
        raise KmeTargetError("KME target horizon must be exactly eight weeks")
    if target.get("included_week_offsets") != list(range(1, 9)):
        raise KmeTargetError("KME target offsets must be exactly t+1 through t+8")
    if target.get("issue_week_included") is not False:
        raise KmeTargetError("KME target must exclude the issue week")
    return config


def require_hash(path: Path, expected: str, label: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise KmeTargetError(
            f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def parse_monday(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise KmeTargetError(f"Invalid issue_week: {value!r}") from exc
    if parsed.weekday() != 0:
        raise KmeTargetError(f"issue_week is not Monday: {value!r}")
    return parsed


def read_region_codes(path: Path) -> tuple[str, ...]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "statistical_region_code" not in reader.fieldnames:
            raise KmeTargetError("Statistical-region schema is invalid")
        codes = [row["statistical_region_code"] for row in reader]
    if not codes or len(codes) != len(set(codes)):
        raise KmeTargetError("Statistical-region codes must be non-empty and unique")
    return tuple(sorted(codes))


def read_mapping(path: Path, region_codes: Sequence[str]) -> dict[str, str]:
    allowed_regions = set(region_codes)
    result: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "statistical_region_code"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeTargetError("Municipality-region mapping schema is invalid")
        for row in reader:
            code = row["municipality_code"]
            region = row["statistical_region_code"]
            if code in result:
                raise KmeTargetError(f"Duplicate municipality mapping: {code}")
            if region not in allowed_regions:
                raise KmeTargetError(f"Unknown statistical-region code: {region}")
            result[code] = region
    return result


def read_calendar(path: Path) -> tuple[date, ...]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "issue_week" not in reader.fieldnames:
            raise KmeTargetError("Calendar schema is invalid")
        weeks = sorted(parse_monday(row["issue_week"]) for row in reader)
    if len(weeks) != len(set(weeks)):
        raise KmeTargetError("Calendar issue weeks must be unique")
    if any(b - a != timedelta(weeks=1) for a, b in zip(weeks, weeks[1:])):
        raise KmeTargetError("Calendar contains a missing week")
    return tuple(weeks)


def read_region_weekly_cases(
    path: Path,
    mapping: Mapping[str, str],
    region_codes: Sequence[str],
    weeks: Sequence[date],
) -> dict[tuple[str, date], int]:
    expected_weeks = set(weeks)
    municipality_values: dict[tuple[str, date], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "issue_week", "kme_cases"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeTargetError("Weekly case schema is invalid")
        for row in reader:
            municipality = row["municipality_code"]
            if municipality not in mapping:
                raise KmeTargetError(f"Unmapped municipality code: {municipality}")
            week = parse_monday(row["issue_week"])
            if week not in expected_weeks:
                raise KmeTargetError(f"Case week is absent from calendar: {week}")
            key = (municipality, week)
            if key in municipality_values:
                raise KmeTargetError(f"Duplicate municipality-week: {key}")
            if row["kme_cases"] == "":
                raise KmeTargetError(f"Missing canonical KME case value: {key}")
            try:
                value = int(row["kme_cases"])
            except ValueError as exc:
                raise KmeTargetError(f"Invalid KME case value: {row['kme_cases']!r}") from exc
            if value < 0:
                raise KmeTargetError("KME case values must be non-negative")
            municipality_values[key] = value

    expected_municipality_keys = {
        (municipality, week) for municipality in mapping for week in weeks
    }
    if set(municipality_values) != expected_municipality_keys:
        raise KmeTargetError("Canonical municipality-week KME grid is incomplete")
    result = {(region, week): 0 for region in region_codes for week in weeks}
    for (municipality, week), value in municipality_values.items():
        result[(mapping[municipality], week)] += value
    return result


def construct_target_rows(
    region_codes: Sequence[str],
    weeks: Sequence[date],
    region_cases: Mapping[tuple[str, date], int],
    *,
    horizon_weeks: int = 8,
) -> list[TargetRow]:
    observed_weeks = set(weeks)
    rows: list[TargetRow] = []
    for region in sorted(region_codes):
        for issue_week in weeks:
            future_weeks = tuple(
                issue_week + timedelta(weeks=offset)
                for offset in range(1, horizon_weeks + 1)
            )
            missing_weeks = [week for week in future_weeks if week not in observed_weeks]
            target_start = future_weeks[0]
            target_end = future_weeks[-1]
            if missing_weeks:
                rows.append(
                    TargetRow(
                        region,
                        issue_week,
                        target_start,
                        target_end,
                        None,
                        "incomplete_future_window",
                        False,
                    )
                )
                continue
            values = [region_cases[(region, week)] for week in future_weeks]
            rows.append(
                TargetRow(
                    region,
                    issue_week,
                    target_start,
                    target_end,
                    sum(values),
                    "complete",
                    True,
                )
            )
    return rows


def target_row_dict(row: TargetRow) -> dict[str, Any]:
    return {
        "statistical_region_code": row.statistical_region_code,
        "issue_week": row.issue_week.isoformat(),
        "target_window_start": row.target_window_start.isoformat(),
        "target_window_end": row.target_window_end.isoformat(),
        "target_kme_cases_next_8w": "" if row.target_value is None else row.target_value,
        "target_status": row.target_status,
        "target_training_eligible": "true" if row.training_eligible else "false",
    }


def file_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": repository_path(path, repo_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    inputs = config["inputs"]
    paths = {
        key: resolve_repo_path(inputs[key], repo_root)
        for key in (
            "weekly_cases",
            "calendar",
            "statistical_region",
            "municipality_statistical_region",
        )
    }
    hashes = {
        key: require_hash(paths[key], inputs[f"{key}_sha256"], key) for key in paths
    }
    region_codes = read_region_codes(paths["statistical_region"])
    mapping = read_mapping(paths["municipality_statistical_region"], region_codes)
    weeks = read_calendar(paths["calendar"])
    region_cases = read_region_weekly_cases(
        paths["weekly_cases"], mapping, region_codes, weeks
    )
    rows = construct_target_rows(
        region_codes,
        weeks,
        region_cases,
        horizon_weeks=config["target"]["horizon_weeks"],
    )
    keys = [(row.statistical_region_code, row.issue_week) for row in rows]
    if len(keys) != len(set(keys)):
        raise KmeTargetError("Target region-week keys are not unique")

    output_directory = resolve_repo_path(config["outputs"]["directory"], repo_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    target_path = output_directory / config["outputs"]["target"]
    quality_path = output_directory / config["outputs"]["quality_summary"]
    with target_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(target_row_dict(row) for row in rows)
    complete_rows = [row for row in rows if row.training_eligible]
    quality = {
        "schema_version": 1,
        "pipeline": "model_v3.panel.kme_eight_week_target",
        "inputs": {
            key: {"path": repository_path(paths[key], repo_root), "sha256": hashes[key]}
            for key in paths
        },
        "target_contract": config["target"],
        "checks": {
            "region_week_unique": True,
            "issue_week_excluded": True,
            "included_offsets_exactly_t_plus_1_through_t_plus_8": True,
            "missing_future_weeks_converted_to_zero": False,
            "incomplete_rows_training_eligible": False,
            "kme_model_trained": False,
        },
        "summary": {
            "n_regions": len(region_codes),
            "n_weeks": len(weeks),
            "n_rows": len(rows),
            "n_complete_rows": len(complete_rows),
            "n_incomplete_rows": len(rows) - len(complete_rows),
            "n_nonzero_complete_targets": sum(
                row.target_value is not None and row.target_value > 0 for row in complete_rows
            ),
            "fraction_nonzero_complete_targets": sum(
                row.target_value is not None and row.target_value > 0 for row in complete_rows
            )
            / len(complete_rows),
            "maximum_complete_target": max(
                row.target_value for row in complete_rows if row.target_value is not None
            ),
        },
        "output": file_record(target_path, repo_root),
    }
    quality_path.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    quality["quality_summary"] = file_record(quality_path, repo_root)
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the KME next-eight-week target.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    quality = run(args.config)
    summary = quality["summary"]
    print(
        "Created KME eight-week target: "
        f"{summary['n_complete_rows']} complete rows, "
        f"{summary['n_nonzero_complete_targets']} non-zero"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
