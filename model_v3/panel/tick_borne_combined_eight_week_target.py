from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from model_v3.models.kme_region_model import repository_path, resolve_repo_path, sha256_file


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "tick_borne_combined_eight_week_target.json"
)
OUTPUT_COLUMNS = (
    "statistical_region_code",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "target_reported_lyme_cases_next_8w",
    "target_reported_kme_cases_next_8w",
    "target_reported_lyme_plus_kme_cases_next_8w",
    "target_status",
    "target_training_eligible",
)


class CombinedTargetError(ValueError):
    """Raised when the combined Lyme-plus-KME target contract is violated."""


@dataclass(frozen=True)
class TargetRow:
    region_code: str
    issue_week: date
    target_start: date
    target_end: date
    lyme_target: int | None
    kme_target: int | None
    combined_target: int | None
    status: str
    training_eligible: bool


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    target = config.get("target", {})
    if config.get("schema_version") != 1:
        raise CombinedTargetError("Unsupported combined-target schema_version")
    if target.get("canonical_name") != "target_reported_lyme_plus_kme_cases_next_8w":
        raise CombinedTargetError("Combined target name changed")
    if target.get("included_week_offsets") != list(range(1, 9)):
        raise CombinedTargetError("Combined target must use exactly t+1 through t+8")
    if target.get("issue_week_included") is not False:
        raise CombinedTargetError("Combined target must exclude issue week")
    if target.get("does_not_represent_all_tick_borne_diseases") is not True:
        raise CombinedTargetError("Composite scope limitation must remain explicit")
    return config


def verify_inputs(
    config: Mapping[str, Any], repo_root: Path = REPO_ROOT
) -> tuple[dict[str, Path], dict[str, str]]:
    inputs = config["inputs"]
    labels = tuple(key[:-7] for key in inputs if key.endswith("_sha256"))
    paths = {label: resolve_repo_path(inputs[label], repo_root) for label in labels}
    hashes: dict[str, str] = {}
    for label, path in paths.items():
        actual = sha256_file(path)
        expected = inputs[f"{label}_sha256"]
        if actual != expected:
            raise CombinedTargetError(
                f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
            )
        hashes[label] = actual
    return paths, hashes


def parse_monday(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise CombinedTargetError(f"Invalid issue_week: {value!r}") from exc
    if parsed.weekday() != 0:
        raise CombinedTargetError(f"issue_week is not Monday: {value!r}")
    return parsed


def read_regions(path: Path) -> tuple[str, ...]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "statistical_region_code" not in reader.fieldnames:
            raise CombinedTargetError("Statistical-region schema is invalid")
        codes = [row["statistical_region_code"] for row in reader]
    if len(codes) != 12 or len(codes) != len(set(codes)):
        raise CombinedTargetError("Expected 12 unique statistical-region codes")
    return tuple(sorted(codes))


def read_mapping(path: Path, regions: Sequence[str]) -> dict[str, str]:
    allowed = set(regions)
    result: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "statistical_region_code"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise CombinedTargetError("Municipality-region mapping schema is invalid")
        for row in reader:
            municipality = row["municipality_code"]
            region = row["statistical_region_code"]
            if municipality in result:
                raise CombinedTargetError(f"Duplicate municipality mapping: {municipality}")
            if region not in allowed:
                raise CombinedTargetError(f"Unknown mapped region: {region}")
            result[municipality] = region
    if len(result) != 212:
        raise CombinedTargetError(f"Expected 212 municipality mappings, found {len(result)}")
    return result


def read_calendar(path: Path) -> tuple[date, ...]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "issue_week" not in reader.fieldnames:
            raise CombinedTargetError("Calendar schema is invalid")
        weeks = sorted(parse_monday(row["issue_week"]) for row in reader)
    if len(weeks) != len(set(weeks)):
        raise CombinedTargetError("Calendar contains duplicate weeks")
    if any(second - first != timedelta(weeks=1) for first, second in zip(weeks, weeks[1:])):
        raise CombinedTargetError("Calendar contains a missing week")
    return tuple(weeks)


def parse_case(value: str, label: str, key: tuple[str, date]) -> int:
    if value == "":
        raise CombinedTargetError(f"Missing canonical {label} value: {key}")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise CombinedTargetError(f"Invalid canonical {label} value: {value!r}") from exc
    if parsed < 0:
        raise CombinedTargetError(f"Canonical {label} value must be non-negative")
    return parsed


def read_region_weekly_components(
    path: Path,
    mapping: Mapping[str, str],
    regions: Sequence[str],
    weeks: Sequence[date],
) -> dict[tuple[str, date], tuple[int, int]]:
    expected_weeks = set(weeks)
    municipality_rows: dict[tuple[str, date], tuple[int, int]] = {}
    regional: defaultdict[tuple[str, date], list[int]] = defaultdict(lambda: [0, 0])
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "issue_week", "lyme_cases", "kme_cases"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise CombinedTargetError("Canonical weekly-case schema is invalid")
        for row in reader:
            municipality = row["municipality_code"]
            if municipality not in mapping:
                raise CombinedTargetError(f"Unmapped municipality: {municipality}")
            week = parse_monday(row["issue_week"])
            if week not in expected_weeks:
                raise CombinedTargetError(f"Case week is absent from calendar: {week}")
            key = (municipality, week)
            if key in municipality_rows:
                raise CombinedTargetError(f"Duplicate municipality-week: {key}")
            lyme = parse_case(row["lyme_cases"], "Lyme", key)
            kme = parse_case(row["kme_cases"], "KME", key)
            municipality_rows[key] = (lyme, kme)
            values = regional[(mapping[municipality], week)]
            values[0] += lyme
            values[1] += kme
    expected_grid = {(municipality, week) for municipality in mapping for week in weeks}
    if set(municipality_rows) != expected_grid:
        raise CombinedTargetError("Canonical municipality-week case grid is incomplete")
    return {
        (region, week): tuple(regional[(region, week)])
        for region in regions
        for week in weeks
    }


def construct_target_rows(
    regions: Sequence[str],
    weeks: Sequence[date],
    components: Mapping[tuple[str, date], tuple[int, int]],
    horizon_weeks: int = 8,
) -> list[TargetRow]:
    observed_weeks = set(weeks)
    rows: list[TargetRow] = []
    for region in sorted(regions):
        for issue in weeks:
            future = tuple(
                issue + timedelta(weeks=offset)
                for offset in range(1, horizon_weeks + 1)
            )
            if any(week not in observed_weeks for week in future):
                rows.append(
                    TargetRow(
                        region,
                        issue,
                        future[0],
                        future[-1],
                        None,
                        None,
                        None,
                        "incomplete_future_window",
                        False,
                    )
                )
                continue
            lyme = sum(components[(region, week)][0] for week in future)
            kme = sum(components[(region, week)][1] for week in future)
            rows.append(
                TargetRow(
                    region,
                    issue,
                    future[0],
                    future[-1],
                    lyme,
                    kme,
                    lyme + kme,
                    "complete",
                    True,
                )
            )
    return rows


def row_dict(row: TargetRow) -> dict[str, Any]:
    return {
        "statistical_region_code": row.region_code,
        "issue_week": row.issue_week.isoformat(),
        "target_window_start": row.target_start.isoformat(),
        "target_window_end": row.target_end.isoformat(),
        "target_reported_lyme_cases_next_8w": "" if row.lyme_target is None else row.lyme_target,
        "target_reported_kme_cases_next_8w": "" if row.kme_target is None else row.kme_target,
        "target_reported_lyme_plus_kme_cases_next_8w": ""
        if row.combined_target is None
        else row.combined_target,
        "target_status": row.status,
        "target_training_eligible": "true" if row.training_eligible else "false",
    }


def file_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": repository_path(path, repo_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def render_dictionary() -> str:
    return """# Combined Lyme + KME eight-week target data dictionary

This target is a composite count of **reported Lyme disease cases plus reported KME/TBE cases**. The project label `tick_borne_diseases` refers only to this two-disease composite and does not represent every tick-borne disease.

| Column | Meaning |
|---|---|
| `statistical_region_code` | Verified statistical-region code. |
| `issue_week` | Monday issue date t. |
| `target_window_start` | t+1 week. |
| `target_window_end` | t+8 weeks. |
| `target_reported_lyme_cases_next_8w` | Reported Lyme cases summed over t+1..t+8. |
| `target_reported_kme_cases_next_8w` | Reported KME/TBE cases summed over t+1..t+8. |
| `target_reported_lyme_plus_kme_cases_next_8w` | Exact sum of the preceding two component targets. |
| `target_status` | `complete` or `incomplete_future_window`. |
| `target_training_eligible` | True only when all eight future weeks exist. |

Issue week is excluded. Missing future weeks and missing component values are never converted to zero. The target is a surveillance count, not personal risk and not a causal measure.
"""


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    paths, hashes = verify_inputs(config, repo_root)
    regions = read_regions(paths["statistical_region"])
    mapping = read_mapping(paths["municipality_statistical_region"], regions)
    weeks = read_calendar(paths["calendar"])
    components = read_region_weekly_components(
        paths["weekly_cases"], mapping, regions, weeks
    )
    rows = construct_target_rows(regions, weeks, components)
    output = config["outputs"]
    target_path = resolve_repo_path(output["target"], repo_root)
    quality_path = resolve_repo_path(output["quality_summary"], repo_root)
    dictionary_path = resolve_repo_path(output["data_dictionary"], repo_root)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(row_dict(row) for row in rows)
    dictionary_path.write_text(render_dictionary(), encoding="utf-8")
    complete = [row for row in rows if row.training_eligible]
    if any(row.combined_target != row.lyme_target + row.kme_target for row in complete):
        raise CombinedTargetError("Combined target does not equal component sum")
    quality = {
        "schema_version": 1,
        "pipeline": "model_v3.panel.tick_borne_combined_eight_week_target",
        "composite_scope": "reported_Lyme_plus_KME_only_not_all_tick_borne_diseases",
        "configuration": file_record(config_path.resolve(), repo_root),
        "code": file_record(Path(__file__).resolve(), repo_root),
        "inputs": {
            key: {"path": repository_path(paths[key], repo_root), "sha256": hashes[key]}
            for key in paths
        },
        "counts": {
            "n_regions": len(regions),
            "n_calendar_weeks": len(weeks),
            "n_rows": len(rows),
            "n_complete": len(complete),
            "n_incomplete_future_window": len(rows) - len(complete),
            "sum_complete_lyme_component": sum(row.lyme_target for row in complete),
            "sum_complete_kme_component": sum(row.kme_target for row in complete),
            "sum_complete_combined_target": sum(row.combined_target for row in complete),
        },
        "checks": {
            "target_exactly_t_plus_1_through_t_plus_8": True,
            "issue_week_excluded": True,
            "year_boundaries_use_date_arithmetic": True,
            "municipality_week_grid_complete": True,
            "region_week_grid_complete": True,
            "combined_equals_lyme_plus_kme": True,
            "missing_component_converted_to_zero": False,
            "incomplete_future_window_converted_to_zero": False,
            "negative_cases_present": False,
            "risk_or_classification_target_created": False,
        },
        "outputs": {
            "target": file_record(target_path, repo_root),
            "data_dictionary": file_record(dictionary_path, repo_root),
        },
    }
    quality_path.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    quality["quality_summary"] = file_record(quality_path, repo_root)
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the regional eight-week reported Lyme-plus-KME target."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    quality = run(args.config)
    counts = quality["counts"]
    print(
        "Created combined tick-borne target: "
        f"rows={counts['n_rows']}, complete={counts['n_complete']}, "
        f"incomplete={counts['n_incomplete_future_window']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
