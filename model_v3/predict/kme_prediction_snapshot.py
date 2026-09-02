from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from model_v3.models.kme_region_model import (
    GLM_BASE,
    repository_path,
    resolve_repo_path,
    sha256_file,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "kme_prediction_snapshot.json"

SNAPSHOT_COLUMNS = (
    "statistical_region_code",
    "statistical_region_name",
    "issue_date",
    "horizon_weeks",
    "predicted_cases",
    "predicted_incidence_per_100k",
    "lower_interval",
    "upper_interval",
    "model_version",
    "data_version",
    "generated_at",
    "data_status",
)
SNAPSHOT_SCHEMA = pa.schema(
    [
        pa.field("statistical_region_code", pa.string(), nullable=False),
        pa.field("statistical_region_name", pa.string(), nullable=False),
        pa.field("issue_date", pa.date32(), nullable=False),
        pa.field("horizon_weeks", pa.int16(), nullable=False),
        pa.field("predicted_cases", pa.float64(), nullable=False),
        pa.field("predicted_incidence_per_100k", pa.float64(), nullable=False),
        pa.field("lower_interval", pa.float64(), nullable=True),
        pa.field("upper_interval", pa.float64(), nullable=True),
        pa.field("model_version", pa.string(), nullable=False),
        pa.field("data_version", pa.string(), nullable=False),
        pa.field("generated_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("data_status", pa.string(), nullable=False),
    ]
)
FORBIDDEN_OUTPUT_COLUMNS = {
    "actual_target_kme_cases_next_8w",
    "target_kme_cases_next_8w",
    "risk_score",
    "risk_category",
    "risk_level",
    "probability",
}


class KmePredictionSnapshotError(ValueError):
    """Raised when the selected KME snapshot contract is violated."""


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("schema_version") != "1.0.0":
        raise KmePredictionSnapshotError("Unsupported KME snapshot schema_version")
    selection = config.get("selection", {})
    if selection.get("selected_model_id") != GLM_BASE:
        raise KmePredictionSnapshotError("KME snapshot selected model changed")
    if selection.get("horizon_weeks") != 8:
        raise KmePredictionSnapshotError("KME snapshot horizon must remain eight weeks")
    if tuple(SNAPSHOT_SCHEMA.names) != SNAPSHOT_COLUMNS:
        raise KmePredictionSnapshotError("KME snapshot schema columns are inconsistent")
    if FORBIDDEN_OUTPUT_COLUMNS.intersection(SNAPSHOT_COLUMNS):
        raise KmePredictionSnapshotError("Forbidden field entered KME snapshot schema")
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
            raise KmePredictionSnapshotError(
                f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
            )
        hashes[label] = actual
    return paths, hashes


def parse_date(value: str, label: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise KmePredictionSnapshotError(f"Invalid {label}: {value!r}") from exc
    return parsed


def parse_nonnegative_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise KmePredictionSnapshotError(f"Invalid {label}: {value!r}") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise KmePredictionSnapshotError(f"{label} must be finite and non-negative")
    return parsed


def parse_positive_integer(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise KmePredictionSnapshotError(f"Invalid {label}: {value!r}") from exc
    if parsed <= 0:
        raise KmePredictionSnapshotError(f"{label} must be positive")
    return parsed


def read_regions(path: Path) -> dict[str, str]:
    required = {"statistical_region_code", "statistical_region_name"}
    result: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmePredictionSnapshotError("Statistical-region schema is invalid")
        for row in reader:
            code = row["statistical_region_code"]
            name = row["statistical_region_name"]
            if not code or not name:
                raise KmePredictionSnapshotError("Region code and name must be non-empty")
            if code in result:
                raise KmePredictionSnapshotError(f"Duplicate region code: {code}")
            result[code] = name
    if not result:
        raise KmePredictionSnapshotError("Statistical-region dimension is empty")
    return result


def read_and_validate_manifest(
    path: Path, config: Mapping[str, Any], input_hashes: Mapping[str, str]
) -> tuple[date, Mapping[str, Any]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "SEALED_2026_PREDICTIONS_NO_2026_KME_OUTCOME_ACCESS":
        raise KmePredictionSnapshotError("KME prediction seal is not in the expected state")
    checks = manifest.get("checks", {})
    if checks.get("2026_KME_outcomes_read") is not False:
        raise KmePredictionSnapshotError("Seal does not prove pipeline outcome protection")
    if checks.get("2026_KME_targets_created") is not False:
        raise KmePredictionSnapshotError("Seal unexpectedly records 2026 targets")
    if manifest.get("selected_model", {}).get("candidate_id") != GLM_BASE:
        raise KmePredictionSnapshotError("Seal selected model differs from snapshot model")
    source_record = manifest.get("outputs", {}).get("prediction_csv", {})
    if source_record.get("path") != config["inputs"]["sealed_predictions"]:
        raise KmePredictionSnapshotError("Seal prediction path differs from snapshot input")
    if source_record.get("sha256") != input_hashes["sealed_predictions"]:
        raise KmePredictionSnapshotError("Seal prediction hash differs from snapshot input")
    seal_date = parse_date(manifest.get("seal", {}).get("sealed_date", ""), "sealed_date")
    return seal_date, manifest


def read_selected_source_rows(
    path: Path,
    selection: Mapping[str, Any],
    seal_date: date,
) -> tuple[list[dict[str, str]], date]:
    required = {
        "statistical_region_code",
        "statistical_region_name",
        "issue_week",
        "target_window_start",
        "target_window_end",
        "horizon_weeks",
        "candidate_id",
        "system_role",
        "predicted_cases",
        "predicted_incidence_per_100000",
        "population_exposure",
        "population_year_min",
        "population_year_max",
        "lower_interval",
        "upper_interval",
        "model_version",
        "data_version",
        "data_status",
    }
    candidates: list[tuple[date, dict[str, str]]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or ()))
            raise KmePredictionSnapshotError(f"Sealed prediction columns missing: {missing}")
        for row in reader:
            if row["candidate_id"] != selection["selected_model_id"]:
                continue
            issue = parse_date(row["issue_week"], "issue_week")
            if issue <= seal_date:
                candidates.append((issue, row))
    if not candidates:
        raise KmePredictionSnapshotError("No selected-model issue week exists by seal date")
    issue_date = max(item[0] for item in candidates)
    return [row for issue, row in candidates if issue == issue_date], issue_date


def build_snapshot_table(
    config: Mapping[str, Any], repo_root: Path = REPO_ROOT
) -> tuple[pa.Table, dict[str, Any]]:
    paths, hashes = verify_inputs(config, repo_root)
    seal_date, manifest = read_and_validate_manifest(
        paths["seal_manifest"], config, hashes
    )
    regions = read_regions(paths["statistical_region"])
    expected = int(config["selection"]["expected_statistical_region_count"])
    if len(regions) != expected:
        raise KmePredictionSnapshotError(
            f"Expected {expected} statistical regions, found {len(regions)}"
        )
    source_rows, issue_date = read_selected_source_rows(
        paths["sealed_predictions"], config["selection"], seal_date
    )
    if issue_date.weekday() != 0:
        raise KmePredictionSnapshotError("KME snapshot issue date must be Monday")
    generated_at = datetime.combine(seal_date, time.min, tzinfo=timezone.utc)
    horizon = int(config["selection"]["horizon_weeks"])
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in source_rows:
        code = source["statistical_region_code"]
        if code in seen:
            raise KmePredictionSnapshotError(f"Duplicate selected prediction for region {code}")
        seen.add(code)
        if code not in regions:
            raise KmePredictionSnapshotError(f"Unmatched statistical region: {code}")
        if source["statistical_region_name"] != regions[code]:
            raise KmePredictionSnapshotError(f"Region name mismatch for {code}")
        if source["system_role"] != config["selection"]["required_system_role"]:
            raise KmePredictionSnapshotError(f"Unexpected system role for region {code}")
        if source["data_status"] != config["selection"]["required_data_status"]:
            raise KmePredictionSnapshotError(f"Unexpected source data status for region {code}")
        if int(source["horizon_weeks"]) != horizon:
            raise KmePredictionSnapshotError("Source horizon differs from snapshot horizon")
        if parse_date(source["target_window_start"], "target_window_start") != issue_date + timedelta(weeks=1):
            raise KmePredictionSnapshotError("KME target window does not begin at t+1")
        if parse_date(source["target_window_end"], "target_window_end") != issue_date + timedelta(weeks=horizon):
            raise KmePredictionSnapshotError("KME target window does not end at t+8")
        if source["lower_interval"] != "" or source["upper_interval"] != "":
            raise KmePredictionSnapshotError("Unfrozen predictive intervals are present")
        predicted = parse_nonnegative_float(source["predicted_cases"], "predicted_cases")
        incidence = parse_nonnegative_float(
            source["predicted_incidence_per_100000"],
            "predicted_incidence_per_100000",
        )
        population = parse_positive_integer(source["population_exposure"], "population_exposure")
        population_year_min = int(source["population_year_min"])
        population_year_max = int(source["population_year_max"])
        if population_year_min > population_year_max or population_year_max >= issue_date.year:
            raise KmePredictionSnapshotError("Population is not strictly earlier than issue time")
        expected_incidence = predicted / population * 100_000.0
        if not math.isclose(incidence, expected_incidence, rel_tol=1e-12, abs_tol=1e-12):
            raise KmePredictionSnapshotError("Prediction and incidence denominator disagree")
        if not source["model_version"] or not source["data_version"]:
            raise KmePredictionSnapshotError("Prediction lineage version is empty")
        records.append(
            {
                "statistical_region_code": code,
                "statistical_region_name": regions[code],
                "issue_date": issue_date,
                "horizon_weeks": horizon,
                "predicted_cases": predicted,
                "predicted_incidence_per_100k": incidence,
                "lower_interval": None,
                "upper_interval": None,
                "model_version": source["model_version"],
                "data_version": source["data_version"],
                "generated_at": generated_at,
                "data_status": config["data_status"],
            }
        )
    if seen != set(regions):
        raise KmePredictionSnapshotError(
            f"Snapshot region coverage mismatch; missing={sorted(set(regions) - seen)}"
        )
    records.sort(key=lambda row: row["statistical_region_code"])
    table = pa.Table.from_pylist(records, schema=SNAPSHOT_SCHEMA)
    model_versions = Counter(row["model_version"] for row in records)
    data_versions = Counter(row["data_version"] for row in records)
    if len(model_versions) != 1 or len(data_versions) != 1:
        raise KmePredictionSnapshotError("Snapshot contains mixed model or data versions")
    context = {
        "paths": paths,
        "input_hashes": hashes,
        "manifest": manifest,
        "seal_date": seal_date,
        "issue_date": issue_date,
        "generated_at": generated_at,
        "model_version": next(iter(model_versions)),
        "data_version": next(iter(data_versions)),
    }
    return table, context


def json_compatible(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return value


def write_snapshot(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    table, context = build_snapshot_table(config, repo_root)
    outputs = config["outputs"]
    output_directory = resolve_repo_path(outputs["directory"], repo_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    parquet_path = output_directory / outputs["parquet"]
    json_path = output_directory / outputs["json"]
    quality_path = output_directory / outputs["quality_summary"]
    pq.write_table(table, parquet_path, compression="snappy")
    json_records = [
        {key: json_compatible(value) for key, value in row.items()}
        for row in table.to_pylist()
    ]
    json_path.write_text(
        json.dumps(json_records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    parquet_round_trip = pq.read_table(parquet_path).to_pylist()
    if parquet_round_trip != table.to_pylist():
        raise KmePredictionSnapshotError("Parquet round trip changed canonical records")
    if json.loads(json_path.read_text(encoding="utf-8")) != json_records:
        raise KmePredictionSnapshotError("JSON round trip changed canonical records")
    null_counts = {
        column: table[column].null_count for column in SNAPSHOT_COLUMNS
    }
    quality = {
        "schema_version": config["schema_version"],
        "pipeline": "model_v3.predict.kme_prediction_snapshot",
        "snapshot_scope": "repository_controlled_2026_prediction_not_observed_performance",
        "configuration": {
            "path": repository_path(config_path.resolve(), repo_root),
            "bytes": config_path.resolve().stat().st_size,
            "sha256": sha256_file(config_path.resolve()),
        },
        "code": {
            "path": repository_path(Path(__file__).resolve(), repo_root),
            "bytes": Path(__file__).resolve().stat().st_size,
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "canonical_table": {
            "columns": list(SNAPSHOT_COLUMNS),
            "row_count": table.num_rows,
            "statistical_region_count": table.num_rows,
            "issue_date": context["issue_date"].isoformat(),
            "horizon_weeks": config["selection"]["horizon_weeks"],
            "null_counts": null_counts,
            "data_status_counts": dict(Counter(table["data_status"].to_pylist())),
        },
        "lineage": {
            "source_paths": {
                key: repository_path(path, repo_root)
                for key, path in context["paths"].items()
            },
            "source_hashes": context["input_hashes"],
            "model_version": context["model_version"],
            "data_version": context["data_version"],
            "seal_date": context["seal_date"].isoformat(),
            "generated_at": json_compatible(context["generated_at"]),
            "issue_date": context["issue_date"].isoformat(),
        },
        "checks": {
            "explicit_arrow_schema_valid": table.schema == SNAPSHOT_SCHEMA,
            "one_row_per_statistical_region": table.num_rows
            == len(set(table["statistical_region_code"].to_pylist())),
            "statistical_region_dimension_exact_coverage": True,
            "selected_model_only": True,
            "target_exactly_t_plus_1_through_t_plus_8": True,
            "issue_week_excluded": True,
            "population_strictly_earlier_than_issue_time": True,
            "incidence_uses_same_denominator_as_offset": True,
            "prediction_values_nonnegative_and_finite": True,
            "predictive_intervals_not_fabricated": True,
            "outcomes_excluded": True,
            "2026_KME_outcomes_read": False,
            "risk_scores_categories_probabilities_excluded": True,
            "json_generated_from_canonical_arrow_table": True,
            "json_parquet_round_trip_parity": True,
        },
        "outputs": {
            "parquet": {
                "path": repository_path(parquet_path, repo_root),
                "bytes": parquet_path.stat().st_size,
                "sha256": sha256_file(parquet_path),
            },
            "json": {
                "path": repository_path(json_path, repo_root),
                "bytes": json_path.stat().st_size,
                "sha256": sha256_file(json_path),
            },
        },
    }
    quality_path.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the selected-model KME regional prediction snapshot."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    quality = write_snapshot(args.config)
    table = quality["canonical_table"]
    print(
        "Created KME prediction snapshot: "
        f"issue_date={table['issue_date']}, regions={table['row_count']}, "
        "outcomes_read=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
