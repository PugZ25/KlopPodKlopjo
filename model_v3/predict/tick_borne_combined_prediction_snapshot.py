from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from model_v3.models.kme_region_model import (
    annual_harmonic,
    read_mapping,
    read_population,
    read_regions,
    repository_path,
    resolve_repo_path,
    selected_region_population,
    sha256_file,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT
    / "model_v3"
    / "config"
    / "tick_borne_combined_prediction_snapshot.json"
)
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
FORBIDDEN_FIELDS = {
    "actual_target_reported_lyme_plus_kme_cases_next_8w",
    "risk_score",
    "risk_category",
    "probability",
}


class CombinedPredictionError(ValueError):
    """Raised when the combined prediction snapshot contract is violated."""


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "1.0.0":
        raise CombinedPredictionError("Unsupported combined snapshot schema_version")
    prediction = config.get("prediction", {})
    issue = date.fromisoformat(prediction["issue_week"])
    if issue.isocalendar().year != 2026 or issue.weekday() != 0:
        raise CombinedPredictionError("Combined snapshot issue must be an ISO-2026 Monday")
    if prediction.get("horizon_weeks") != 8:
        raise CombinedPredictionError("Combined snapshot horizon must be eight weeks")
    if prediction.get("past_case_offsets") != list(range(-8, 0)):
        raise CombinedPredictionError("Past-case window must be exactly t-8 through t-1")
    if config["selection"]["selected_model_id"] != "glm_past_combined_offset":
        raise CombinedPredictionError("Combined snapshot selected model changed")
    if FORBIDDEN_FIELDS.intersection(SNAPSHOT_COLUMNS):
        raise CombinedPredictionError("Forbidden field entered combined snapshot schema")
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
            raise CombinedPredictionError(
                f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
            )
        hashes[label] = actual
    return paths, hashes


def parse_generated_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CombinedPredictionError(f"Invalid generated_at: {value!r}") from exc
    if parsed.tzinfo is None:
        raise CombinedPredictionError("generated_at must have a timezone")
    return parsed.astimezone(timezone.utc)


def verify_freeze(
    path: Path, config: Mapping[str, Any], hashes: Mapping[str, str]
) -> Mapping[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_COMBINED_MODEL_2026_OUTCOMES_UNOPENED":
        raise CombinedPredictionError("Combined model freeze status is invalid")
    if manifest.get("selected_model", {}).get("candidate_id") != config["selection"]["selected_model_id"]:
        raise CombinedPredictionError("Freeze and prediction selected models differ")
    if manifest.get("checks", {}).get("2026_outcomes_accessed") is not False:
        raise CombinedPredictionError("Freeze does not retain 2026 outcome protection")
    outputs = manifest.get("outputs", {})
    for label in ("coefficients", "scaler"):
        if outputs.get(label, {}).get("sha256") != hashes[label]:
            raise CombinedPredictionError(f"Freeze {label} hash differs from snapshot input")
    return manifest


def read_coefficients(path: Path) -> dict[str, float]:
    result: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"feature", "coefficient"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise CombinedPredictionError("Coefficient schema is invalid")
        for row in reader:
            feature = row["feature"]
            if feature in result:
                raise CombinedPredictionError(f"Duplicate coefficient: {feature}")
            value = float(row["coefficient"])
            if not math.isfinite(value):
                raise CombinedPredictionError("Coefficient must be finite")
            result[feature] = value
    if not result:
        raise CombinedPredictionError("Coefficient artifact is empty")
    return result


def read_scaler(path: Path) -> Mapping[str, Any]:
    scaler = json.loads(path.read_text(encoding="utf-8"))
    if scaler.get("feature") != "past_8w_reported_lyme_plus_kme_incidence_per_100000":
        raise CombinedPredictionError("Scaler feature changed")
    if float(scaler.get("standard_deviation", 0)) <= 0:
        raise CombinedPredictionError("Scaler standard deviation must be positive")
    return scaler


def read_required_past_cases(
    path: Path,
    mapping: Mapping[str, str],
    issue_week: date,
    protected_year: int = 2026,
) -> tuple[dict[str, int], int]:
    required_weeks = tuple(issue_week + timedelta(weeks=offset) for offset in range(-8, 0))
    required_week_set = set(required_weeks)
    municipality_values: dict[tuple[str, date], int] = {}
    skipped_protected = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "issue_week", "lyme_cases", "kme_cases"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise CombinedPredictionError("Canonical weekly-case schema is invalid")
        for source in reader:
            week = date.fromisoformat(source["issue_week"])
            if week.isocalendar().year >= protected_year:
                skipped_protected += 1
                continue
            if week not in required_week_set:
                continue
            municipality = source["municipality_code"]
            if municipality not in mapping:
                raise CombinedPredictionError(f"Unmapped municipality: {municipality}")
            key = (municipality, week)
            if key in municipality_values:
                raise CombinedPredictionError(f"Duplicate past municipality-week: {key}")
            if source["lyme_cases"] == "" or source["kme_cases"] == "":
                raise CombinedPredictionError(f"Missing past component value: {key}")
            try:
                lyme = int(source["lyme_cases"])
                kme = int(source["kme_cases"])
            except ValueError as exc:
                raise CombinedPredictionError(f"Invalid past component value: {key}") from exc
            if lyme < 0 or kme < 0:
                raise CombinedPredictionError("Past component values must be non-negative")
            municipality_values[key] = lyme + kme
    expected = {
        (municipality, week) for municipality in mapping for week in required_weeks
    }
    if set(municipality_values) != expected:
        missing = sorted(expected - set(municipality_values))
        raise CombinedPredictionError(
            f"Past eight-week combined case window is incomplete; missing_count={len(missing)}"
        )
    regional: defaultdict[str, int] = defaultdict(int)
    for (municipality, _week), value in municipality_values.items():
        regional[mapping[municipality]] += value
    return dict(regional), skipped_protected


def stable_data_version(hashes: Mapping[str, str]) -> str:
    labels = (
        "weekly_cases",
        "population",
        "statistical_region",
        "municipality_statistical_region",
    )
    digest = hashlib.sha256(
        "|".join(hashes[label] for label in labels).encode("ascii")
    ).hexdigest()
    return f"reported_lyme_plus_kme_data@sha256:{digest}"


def predict_rows(
    config: Mapping[str, Any], paths: Mapping[str, Path], hashes: Mapping[str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    freeze = verify_freeze(paths["freeze_manifest"], config, hashes)
    coefficients = read_coefficients(paths["coefficients"])
    scaler = read_scaler(paths["scaler"])
    regions = read_regions(paths["statistical_region"])
    mapping = read_mapping(paths["municipality_statistical_region"], regions)
    population = read_population(paths["population"])
    prediction = config["prediction"]
    issue = date.fromisoformat(prediction["issue_week"])
    target_start = date.fromisoformat(prediction["target_window_start"])
    target_end = date.fromisoformat(prediction["target_window_end"])
    if target_start != issue + timedelta(weeks=1) or target_end != issue + timedelta(weeks=8):
        raise CombinedPredictionError("Configured target window is not exactly t+1..t+8")
    past_start = date.fromisoformat(prediction["past_case_window_start"])
    past_end = date.fromisoformat(prediction["past_case_window_end"])
    if past_start != issue - timedelta(weeks=8) or past_end != issue - timedelta(weeks=1):
        raise CombinedPredictionError("Configured past window is not exactly t-8..t-1")
    past_cases, skipped_protected = read_required_past_cases(
        paths["weekly_cases"], mapping, issue
    )
    seasonal_sin, seasonal_cos = annual_harmonic(issue)
    generated_at = parse_generated_at(prediction["generated_at"])
    data_version = stable_data_version(hashes)
    model_version = (
        f"glm_past_combined_offset@sha256:{hashes['coefficients']}"
    )
    scaler_mean = float(scaler["mean"])
    scaler_sd = float(scaler["standard_deviation"])
    rows = []
    for region in sorted(regions):
        population_value, year_min, year_max = selected_region_population(
            region, issue, mapping, population
        )
        if year_max >= issue.year:
            raise CombinedPredictionError("Population is not strictly earlier than issue time")
        past_incidence = past_cases[region] / population_value * 100_000.0
        linear_predictor = (
            math.log(population_value / 100_000.0)
            + coefficients["intercept"]
            + coefficients["seasonal_sin_annual"] * seasonal_sin
            + coefficients["seasonal_cos_annual"] * seasonal_cos
            + coefficients.get(f"region[{region}]", 0.0)
            + coefficients[
                "z_past_8w_reported_lyme_plus_kme_incidence_per_100000"
            ]
            * ((past_incidence - scaler_mean) / scaler_sd)
        )
        predicted = math.exp(linear_predictor)
        if not math.isfinite(predicted) or predicted < 0:
            raise CombinedPredictionError(f"Invalid prediction for region {region}")
        rows.append(
            {
                "statistical_region_code": region,
                "statistical_region_name": regions[region],
                "issue_date": issue,
                "horizon_weeks": 8,
                "predicted_cases": predicted,
                "predicted_incidence_per_100k": predicted / population_value * 100_000.0,
                "lower_interval": None,
                "upper_interval": None,
                "model_version": model_version,
                "data_version": data_version,
                "generated_at": generated_at,
                "data_status": config["data_status"],
            }
        )
    context = {
        "freeze": freeze,
        "issue_week": issue,
        "target_start": target_start,
        "target_end": target_end,
        "past_start": past_start,
        "past_end": past_end,
        "skipped_protected_rows_before_numeric_parsing": skipped_protected,
        "model_version": model_version,
        "data_version": data_version,
        "generated_at": generated_at,
    }
    return rows, context


def json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return value


def file_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": repository_path(path, repo_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def render_contract(config: Mapping[str, Any]) -> str:
    prediction = config["prediction"]
    return f"""# Combined Lyme + KME prediction snapshot contract

This snapshot forecasts the **combined reported count of Lyme disease and KME/TBE cases**. The project label “tick-borne diseases” refers only to those two components, not every tick-borne disease.

- Analysis unit: statistical region × issue date.
- Issue date: `{prediction['issue_week']}`.
- Target window: `{prediction['target_window_start']}` through `{prediction['target_window_end']}` (exactly t+1..t+8).
- Past epidemiological input: `{prediction['past_case_window_start']}` through `{prediction['past_case_window_end']}` (exactly t−8..t−1).
- Model: frozen Poisson GLM with seasonality, region, past combined incidence, and population offset.
- Weather: evaluated during development but not selected.
- Predictive intervals: unavailable and therefore null.

The JSON and Parquet outputs are generated from one canonical Arrow table. They contain no observed outcomes, risk scores, categories, probabilities, or personal-risk statements. Because this snapshot was sealed during 2026 for a target window that has already elapsed in calendar time, it is repository-controlled retrospective output, not a fully prospective experiment.
"""


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    paths, hashes = verify_inputs(config, repo_root)
    rows, context = predict_rows(config, paths, hashes)
    if len(rows) != int(config["selection"]["expected_statistical_region_count"]):
        raise CombinedPredictionError("Prediction region count is incomplete")
    table = pa.Table.from_pylist(rows, schema=SNAPSHOT_SCHEMA)
    output = config["outputs"]
    directory = resolve_repo_path(output["directory"], repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    parquet_path = directory / output["parquet"]
    json_path = directory / output["json"]
    quality_path = directory / output["quality_summary"]
    contract_path = resolve_repo_path(output["contract"], repo_root)
    pq.write_table(table, parquet_path, compression="snappy")
    json_rows = [
        {key: json_value(value) for key, value in row.items()}
        for row in table.to_pylist()
    ]
    json_path.write_text(
        json.dumps(json_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    contract_path.write_text(render_contract(config), encoding="utf-8")
    if pq.read_table(parquet_path).to_pylist() != table.to_pylist():
        raise CombinedPredictionError("Parquet round trip changed snapshot")
    if json.loads(json_path.read_text(encoding="utf-8")) != json_rows:
        raise CombinedPredictionError("JSON round trip changed snapshot")
    output_records = {
        "parquet": file_record(parquet_path, repo_root),
        "json": file_record(json_path, repo_root),
        "contract": file_record(contract_path, repo_root),
    }
    quality = {
        "schema_version": config["schema_version"],
        "pipeline": "model_v3.predict.tick_borne_combined_prediction_snapshot",
        "snapshot_scope": config["prediction"]["temporal_classification"],
        "composite_scope": config["selection"]["composite_scope"],
        "configuration": file_record(config_path.resolve(), repo_root),
        "code": file_record(Path(__file__).resolve(), repo_root),
        "inputs": {
            key: {"path": repository_path(paths[key], repo_root), "sha256": hashes[key]}
            for key in paths
        },
        "canonical_table": {
            "columns": list(SNAPSHOT_COLUMNS),
            "row_count": table.num_rows,
            "statistical_region_count": len(set(table["statistical_region_code"].to_pylist())),
            "issue_date": context["issue_week"].isoformat(),
            "target_window_start": context["target_start"].isoformat(),
            "target_window_end": context["target_end"].isoformat(),
            "past_case_window_start": context["past_start"].isoformat(),
            "past_case_window_end": context["past_end"].isoformat(),
            "horizon_weeks": 8,
            "null_counts": {column: table[column].null_count for column in SNAPSHOT_COLUMNS},
        },
        "lineage": {
            "model_version": context["model_version"],
            "data_version": context["data_version"],
            "generated_at": json_value(context["generated_at"]),
        },
        "checks": {
            "explicit_arrow_schema_valid": table.schema == SNAPSHOT_SCHEMA,
            "one_row_per_statistical_region": table.num_rows
            == len(set(table["statistical_region_code"].to_pylist())),
            "target_exactly_t_plus_1_through_t_plus_8": True,
            "issue_week_excluded": True,
            "past_cases_exactly_t_minus_8_through_t_minus_1": True,
            "population_strictly_earlier_than_issue_time": True,
            "population_is_offset_and_incidence_denominator": True,
            "weather_used_by_selected_model": False,
            "predictions_nonnegative_and_finite": True,
            "predictive_intervals_not_fabricated": True,
            "2026_outcomes_read": False,
            "2026_targets_created": False,
            "protected_rows_skipped_before_numeric_parsing": context[
                "skipped_protected_rows_before_numeric_parsing"
            ],
            "outcomes_excluded_from_snapshot": True,
            "risk_scores_categories_probabilities_excluded": True,
            "json_and_parquet_same_canonical_table": True,
        },
        "outputs": output_records,
    }
    quality_path.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    quality["quality_summary"] = file_record(quality_path, repo_root)
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the frozen combined Lyme-plus-KME prediction snapshot."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    quality = run(args.config)
    table = quality["canonical_table"]
    print(
        "Created combined tick-borne prediction snapshot: "
        f"issue_date={table['issue_date']}, regions={table['row_count']}, "
        "outcomes_2026_read=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
