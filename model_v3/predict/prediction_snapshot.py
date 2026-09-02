from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pyarrow as pa
import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "lyme_prediction_snapshot.json"

SNAPSHOT_COLUMNS = (
    "municipality_code",
    "municipality_name",
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
        pa.field("municipality_code", pa.string(), nullable=False),
        pa.field("municipality_name", pa.string(), nullable=False),
        pa.field("issue_date", pa.date32(), nullable=False),
        pa.field("horizon_weeks", pa.int16(), nullable=False),
        pa.field("predicted_cases", pa.float64(), nullable=False),
        pa.field("predicted_incidence_per_100k", pa.float64(), nullable=True),
        pa.field("lower_interval", pa.float64(), nullable=True),
        pa.field("upper_interval", pa.float64(), nullable=True),
        pa.field("model_version", pa.string(), nullable=False),
        pa.field("data_version", pa.string(), nullable=False),
        pa.field("generated_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("data_status", pa.string(), nullable=False),
    ]
)

FORBIDDEN_OUTPUT_COLUMNS = {
    "actual_target_lyme_cases_next_4w",
    "risk_score",
    "risk_category",
    "risk_level",
    "probability",
}


class PredictionSnapshotError(ValueError):
    """Raised when snapshot lineage, source data, or output schema is invalid."""


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
    if config.get("schema_version") != "1.0.0":
        raise PredictionSnapshotError("Unsupported prediction snapshot schema_version")
    return config


def require_file_hash(path: Path, expected_sha256: str, label: str) -> str:
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise PredictionSnapshotError(
            f"{label} SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    return actual_sha256


def parse_iso_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise PredictionSnapshotError(f"Invalid {label}: {value!r}") from exc


def parse_utc_datetime(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise PredictionSnapshotError(f"Invalid {label}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise PredictionSnapshotError(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def parse_nonnegative_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise PredictionSnapshotError(f"Invalid numeric {label}: {value!r}") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise PredictionSnapshotError(f"{label} must be finite and non-negative")
    return parsed


def parse_population_denominator(value: str) -> int | None:
    if value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise PredictionSnapshotError(
            f"Invalid population_exposure denominator: {value!r}"
        ) from exc
    return parsed if parsed > 0 else None


def read_municipalities(path: Path) -> dict[str, str]:
    required = {"municipality_code", "municipality_name"}
    municipalities: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise PredictionSnapshotError(
                f"Municipality input must contain {sorted(required)}"
            )
        for row in reader:
            code = row["municipality_code"]
            name = row["municipality_name"]
            if not code or not name:
                raise PredictionSnapshotError("Municipality code and name must be non-empty")
            if code in municipalities:
                raise PredictionSnapshotError(f"Duplicate municipality code: {code}")
            municipalities[code] = name
    return municipalities


def read_receipt(path: Path, config: Mapping[str, Any]) -> tuple[datetime, dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        receipt = json.load(handle)
    if receipt.get("status") != "completed":
        raise PredictionSnapshotError("The lockbox evaluation receipt is not completed")
    if receipt.get("protected_parse_count") != 1:
        raise PredictionSnapshotError("The receipt does not record exactly one protected parse")
    if receipt.get("rerun_allowed") is not False:
        raise PredictionSnapshotError("The sealed lockbox receipt unexpectedly permits reruns")

    prediction_record = receipt.get("output_records", {}).get("predictions", {})
    inputs = config["inputs"]
    if prediction_record.get("path") != inputs["selected_model_predictions"]:
        raise PredictionSnapshotError("Receipt prediction path does not match snapshot config")
    if prediction_record.get("sha256") != inputs["selected_model_predictions_sha256"]:
        raise PredictionSnapshotError("Receipt prediction hash does not match snapshot config")
    return parse_utc_datetime(receipt.get("completed_at_utc", ""), "completed_at_utc"), receipt


def read_selected_prediction_rows(
    path: Path, selection: Mapping[str, Any]
) -> tuple[list[dict[str, str]], date]:
    required_columns = {
        "system_type",
        "candidate_id",
        "municipality_code",
        "issue_week",
        "target_window_start",
        "target_window_end",
        "predicted_target_lyme_cases_next_4w",
        "prediction_status",
        "interval_lower",
        "interval_upper",
        "interval_status",
        "population_exposure",
    }
    selected_rows: list[dict[str, str]] = []
    selected_dates: list[date] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            missing = sorted(required_columns - set(reader.fieldnames or ()))
            raise PredictionSnapshotError(f"Prediction source is missing columns: {missing}")
        for row in reader:
            if row["candidate_id"] != selection["selected_model_id"]:
                continue
            issue_date = parse_iso_date(row["issue_week"], "issue_week")
            selected_rows.append(row)
            selected_dates.append(issue_date)

    if not selected_rows:
        raise PredictionSnapshotError("No rows exist for the selected model")
    latest_issue_date = max(selected_dates)
    latest_rows = [
        row
        for row in selected_rows
        if parse_iso_date(row["issue_week"], "issue_week") == latest_issue_date
    ]
    return latest_rows, latest_issue_date


def validate_source_row(
    row: Mapping[str, str], issue_date: date, selection: Mapping[str, Any]
) -> None:
    if row["system_type"] != selection["required_system_type"]:
        raise PredictionSnapshotError(
            f"Unexpected system_type for {row['municipality_code']}: {row['system_type']}"
        )
    if row["prediction_status"] != selection["required_prediction_status"]:
        raise PredictionSnapshotError(
            f"Prediction is unavailable for municipality {row['municipality_code']}"
        )
    target_start = parse_iso_date(row["target_window_start"], "target_window_start")
    target_end = parse_iso_date(row["target_window_end"], "target_window_end")
    horizon = int(selection["horizon_weeks"])
    if target_start != issue_date + timedelta(weeks=1):
        raise PredictionSnapshotError("Source target window does not begin at t+1")
    if target_end != issue_date + timedelta(weeks=horizon):
        raise PredictionSnapshotError("Source target window does not end at t+4")
    if row["interval_status"] != selection["required_interval_status"]:
        raise PredictionSnapshotError("Unexpected predictive interval status")
    if row["interval_lower"] != "" or row["interval_upper"] != "":
        raise PredictionSnapshotError(
            "Frozen model declares no intervals but source interval values are present"
        )


def build_snapshot_table(
    config: Mapping[str, Any], repo_root: Path = REPO_ROOT
) -> tuple[pa.Table, dict[str, Any]]:
    inputs = config["inputs"]
    selection = config["selection"]
    if int(selection["horizon_weeks"]) != 4:
        raise PredictionSnapshotError("The v1 Lyme snapshot horizon must be exactly 4 weeks")

    resolved = {
        key: resolve_repo_path(inputs[key], repo_root)
        for key in (
            "selected_model_predictions",
            "lockbox_receipt",
            "municipality",
            "selected_model_config",
        )
    }
    actual_hashes = {
        "selected_model_predictions": require_file_hash(
            resolved["selected_model_predictions"],
            inputs["selected_model_predictions_sha256"],
            "selected-model prediction source",
        ),
        "lockbox_receipt": require_file_hash(
            resolved["lockbox_receipt"],
            inputs["lockbox_receipt_sha256"],
            "lockbox receipt",
        ),
        "municipality": require_file_hash(
            resolved["municipality"],
            inputs["municipality_sha256"],
            "municipality dimension",
        ),
        "selected_model_config": require_file_hash(
            resolved["selected_model_config"],
            inputs["selected_model_config_sha256"],
            "selected-model config",
        ),
    }

    generated_at, _receipt = read_receipt(resolved["lockbox_receipt"], config)
    municipalities = read_municipalities(resolved["municipality"])
    expected_count = int(selection["expected_municipality_count"])
    if len(municipalities) != expected_count:
        raise PredictionSnapshotError(
            f"Expected {expected_count} municipalities, found {len(municipalities)}"
        )

    source_rows, issue_date = read_selected_prediction_rows(
        resolved["selected_model_predictions"], selection
    )
    if issue_date.weekday() != 0:
        raise PredictionSnapshotError("The selected issue_date must be a Monday")
    model_version = (
        f"{selection['selected_model_id']}@sha256:"
        f"{actual_hashes['selected_model_config']}"
    )
    data_version = (
        "sealed_selected_model_predictions@sha256:"
        f"{actual_hashes['selected_model_predictions']}"
    )

    records: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for row in source_rows:
        validate_source_row(row, issue_date, selection)
        code = row["municipality_code"]
        if code in seen_codes:
            raise PredictionSnapshotError(
                f"Duplicate selected-model row for {code} on {issue_date.isoformat()}"
            )
        seen_codes.add(code)
        if code not in municipalities:
            raise PredictionSnapshotError(f"Unmatched municipality code: {code}")

        predicted_cases = parse_nonnegative_float(
            row["predicted_target_lyme_cases_next_4w"], "predicted_cases"
        )
        denominator = parse_population_denominator(row["population_exposure"])
        if denominator is None:
            incidence = None
            data_status = config["data_status"]["invalid_denominator"]
        else:
            incidence = predicted_cases / denominator * 100_000.0
            data_status = config["data_status"]["valid_denominator"]

        records.append(
            {
                "municipality_code": code,
                "municipality_name": municipalities[code],
                "issue_date": issue_date,
                "horizon_weeks": int(selection["horizon_weeks"]),
                "predicted_cases": predicted_cases,
                "predicted_incidence_per_100k": incidence,
                "lower_interval": None,
                "upper_interval": None,
                "model_version": model_version,
                "data_version": data_version,
                "generated_at": generated_at,
                "data_status": data_status,
            }
        )

    if seen_codes != set(municipalities):
        missing = sorted(set(municipalities) - seen_codes)
        unexpected = sorted(seen_codes - set(municipalities))
        raise PredictionSnapshotError(
            f"Snapshot municipality coverage mismatch; missing={missing}, unexpected={unexpected}"
        )

    records.sort(key=lambda row: row["municipality_code"])
    metadata = {
        b"schema_version": config["schema_version"].encode("utf-8"),
        b"analysis_unit": b"municipality_code_x_issue_date",
        b"horizon": b"reported_Lyme_cases_t_plus_1_through_t_plus_4",
        b"interval_availability": b"not_available_for_frozen_selected_model",
        b"snapshot_scope": b"retrospective_lockbox_evaluation_not_live_prediction",
    }
    table = pa.Table.from_pylist(records, schema=SNAPSHOT_SCHEMA.with_metadata(metadata))
    validate_snapshot_table(table, config)

    lineage = {
        "issue_date": issue_date.isoformat(),
        "generated_at": utc_isoformat(generated_at),
        "model_version": model_version,
        "data_version": data_version,
        "source_hashes": actual_hashes,
        "source_paths": {
            key: repository_path(path, repo_root) for key, path in resolved.items()
        },
    }
    return table, lineage


def validate_snapshot_table(table: pa.Table, config: Mapping[str, Any]) -> None:
    if tuple(table.column_names) != SNAPSHOT_COLUMNS:
        raise PredictionSnapshotError("Snapshot columns do not match the v1 contract")
    if not table.schema.remove_metadata().equals(SNAPSHOT_SCHEMA):
        raise PredictionSnapshotError("Snapshot Arrow schema does not match the v1 contract")
    metadata = table.schema.metadata or {}
    if metadata.get(b"schema_version") != config["schema_version"].encode("utf-8"):
        raise PredictionSnapshotError("Snapshot schema_version metadata is missing or wrong")
    if FORBIDDEN_OUTPUT_COLUMNS.intersection(table.column_names):
        raise PredictionSnapshotError("Snapshot contains a forbidden output column")

    rows = table.to_pylist()
    expected_count = int(config["selection"]["expected_municipality_count"])
    if len(rows) != expected_count:
        raise PredictionSnapshotError(
            f"Expected {expected_count} snapshot rows, found {len(rows)}"
        )
    codes = [row["municipality_code"] for row in rows]
    if codes != sorted(codes) or len(codes) != len(set(codes)):
        raise PredictionSnapshotError("Municipality codes must be unique and sorted")

    allowed_statuses = set(config["data_status"].values())
    expected_horizon = int(config["selection"]["horizon_weeks"])
    issue_dates = {row["issue_date"] for row in rows}
    model_versions = {row["model_version"] for row in rows}
    data_versions = {row["data_version"] for row in rows}
    generated_times = {row["generated_at"] for row in rows}
    if any(len(values) != 1 for values in (issue_dates, model_versions, data_versions, generated_times)):
        raise PredictionSnapshotError("Snapshot version/date fields must be constant")

    for row in rows:
        predicted = row["predicted_cases"]
        incidence = row["predicted_incidence_per_100k"]
        lower = row["lower_interval"]
        upper = row["upper_interval"]
        if row["horizon_weeks"] != expected_horizon:
            raise PredictionSnapshotError("Unexpected prediction horizon")
        if not math.isfinite(predicted) or predicted < 0:
            raise PredictionSnapshotError("Predicted cases must be finite and non-negative")
        if incidence is not None and (not math.isfinite(incidence) or incidence < 0):
            raise PredictionSnapshotError("Predicted incidence must be null or non-negative")
        if (lower is None) != (upper is None):
            raise PredictionSnapshotError("Prediction intervals must be both present or both null")
        if lower is not None and not (0 <= lower <= predicted <= upper):
            raise PredictionSnapshotError("Prediction interval ordering is invalid")
        if row["data_status"] not in allowed_statuses:
            raise PredictionSnapshotError("Unexpected data_status")
        if incidence is None and row["data_status"] != config["data_status"]["invalid_denominator"]:
            raise PredictionSnapshotError("Null incidence requires invalid-denominator data_status")
        if incidence is not None and row["data_status"] != config["data_status"]["valid_denominator"]:
            raise PredictionSnapshotError("Present incidence requires valid-denominator data_status")


def utc_isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def json_records_from_table(table: pa.Table) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in table.to_pylist():
        converted: dict[str, Any] = {}
        for column in SNAPSHOT_COLUMNS:
            value = row[column]
            if isinstance(value, datetime):
                converted[column] = utc_isoformat(value)
            elif isinstance(value, date):
                converted[column] = value.isoformat()
            else:
                converted[column] = value
        records.append(converted)
    return records


def output_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": repository_path(path, repo_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_snapshot_outputs(
    table: pa.Table,
    config: Mapping[str, Any],
    lineage: Mapping[str, Any],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    validate_snapshot_table(table, config)
    output_config = config["outputs"]
    output_directory = resolve_repo_path(output_config["directory"], repo_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    parquet_path = output_directory / output_config["parquet"]
    json_path = output_directory / output_config["json"]
    quality_path = output_directory / output_config["quality_summary"]

    pq.write_table(table, parquet_path, compression="zstd", version="2.6")
    canonical_json_records = json_records_from_table(table)
    json_payload = {
        "schema_version": config["schema_version"],
        "predictions": canonical_json_records,
    }
    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    parquet_round_trip = pq.read_table(parquet_path)
    validate_snapshot_table(parquet_round_trip, config)
    with json_path.open(encoding="utf-8") as handle:
        json_round_trip = json.load(handle)
    if json_round_trip.get("schema_version") != config["schema_version"]:
        raise PredictionSnapshotError("JSON schema_version does not match the contract")
    if json_round_trip.get("predictions") != json_records_from_table(parquet_round_trip):
        raise PredictionSnapshotError("JSON and Parquet rows are not identical")

    rows = table.to_pylist()
    quality = {
        "schema_version": config["schema_version"],
        "pipeline": "model_v3.predict.prediction_snapshot",
        "snapshot_scope": "retrospective_lockbox_evaluation_not_live_prediction",
        "lineage": dict(lineage),
        "canonical_table": {
            "row_count": table.num_rows,
            "columns": list(table.column_names),
            "issue_date": lineage["issue_date"],
            "horizon_weeks": int(config["selection"]["horizon_weeks"]),
            "municipality_count": len({row["municipality_code"] for row in rows}),
            "null_counts": {
                name: table.column(name).null_count for name in table.column_names
            },
            "data_status_counts": {
                status: sum(row["data_status"] == status for row in rows)
                for status in sorted({row["data_status"] for row in rows})
            },
        },
        "checks": {
            "explicit_arrow_schema_valid": True,
            "one_row_per_municipality": True,
            "municipality_dimension_exact_coverage": True,
            "prediction_values_nonnegative_and_finite": True,
            "incidence_only_when_denominator_valid": True,
            "predictive_intervals_not_fabricated": all(
                row["lower_interval"] is None and row["upper_interval"] is None
                for row in rows
            ),
            "json_generated_from_canonical_arrow_table": True,
            "json_parquet_round_trip_parity": True,
            "outcomes_excluded": "actual_target_lyme_cases_next_4w" not in table.column_names,
            "risk_scores_categories_probabilities_excluded": not bool(
                FORBIDDEN_OUTPUT_COLUMNS.intersection(table.column_names)
            ),
        },
        "outputs": {
            "parquet": output_record(parquet_path, repo_root),
            "json": output_record(json_path, repo_root),
        },
    }
    quality_path.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    quality["quality_summary"] = output_record(quality_path, repo_root)
    return quality


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    table, lineage = build_snapshot_table(config, repo_root=repo_root)
    return write_snapshot_outputs(table, config, lineage, repo_root=repo_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the validated v1 Lyme prediction snapshot."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    quality = run(args.config)
    print(
        "Created prediction snapshot: "
        f"{quality['canonical_table']['row_count']} municipalities, "
        f"issue_date={quality['canonical_table']['issue_date']}, "
        f"horizon_weeks={quality['canonical_table']['horizon_weeks']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
