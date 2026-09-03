from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import statistics
import warnings
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import statsmodels
import statsmodels.api as sm

from model_v3.models.kme_region_model import (
    annual_harmonic,
    read_mapping,
    read_population,
    read_region_weekly_cases,
    read_regions,
    require_hash,
    selected_region_population,
    sha256_file,
)
from model_v3.models.non_ml_baselines import file_record, resolve_repo_path, write_csv_rows


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3/config/kme_precaution_proxy.json"

BASELINE_ID = "baseline_global_historical_rate"
MODEL_ID = "glm_current_week_seasonal_region_offset"
CANDIDATE_IDS = (BASELINE_ID, MODEL_ID)

PREDICTION_COLUMNS = (
    "evaluation_scope",
    "fold_id",
    "validation_year",
    "candidate_id",
    "statistical_region_code",
    "issue_week",
    "signal_week_start",
    "signal_week_end",
    "actual_reported_kme_cases_current_week",
    "predicted_reported_kme_cases_current_week",
    "population_exposure",
    "population_year_min",
    "population_year_max",
    "actual_incidence_per_100000",
    "predicted_incidence_per_100000",
)
METRIC_COLUMNS = (
    "evaluation_scope",
    "fold_id",
    "validation_year",
    "candidate_id",
    "n_predictions",
    "mae",
    "rmse",
    "mean_poisson_deviance",
)
AGGREGATE_COLUMNS = (
    "evaluation_scope",
    "candidate_id",
    "n_folds",
    "n_predictions",
    "pooled_mae",
    "pooled_rmse",
    "pooled_mean_poisson_deviance",
)
COEFFICIENT_COLUMNS = ("feature", "coefficient", "standard_error")


class KmePrecautionProxyError(ValueError):
    """Raised when the current-week KME proxy contract is violated."""


@dataclass(frozen=True)
class CurrentWeekRow:
    region_code: str
    issue_week: date
    target_value: int
    population: int
    population_year_min: int
    population_year_max: int
    seasonal_sin: float
    seasonal_cos: float

    @property
    def exposure_per_100000(self) -> float:
        return self.population / 100_000.0

    @property
    def offset(self) -> float:
        return math.log(self.exposure_per_100000)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise KmePrecautionProxyError("Configuration must remain inside the repository")
    config = json.loads(resolved.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise KmePrecautionProxyError("Configuration schema_version must equal 1")
    purpose = config.get("purpose", {})
    design = config.get("design", {})
    if (
        purpose.get("training_target")
        != "reported_kme_cases_in_current_signal_week_t"
        or purpose.get("runtime_case_inputs_allowed") is not False
        or design.get("target_timing") != "signal_week_t"
        or design.get("target_embargo_weeks") != 0
        or design.get("runtime_recent_cases_required") is not False
        or design.get("runtime_weather_used_by_ai_score") is not False
    ):
        raise KmePrecautionProxyError("Current-week no-runtime-cases contract changed")
    ids = tuple(row["candidate_id"] for row in config.get("candidates", ()))
    if ids != CANDIDATE_IDS:
        raise KmePrecautionProxyError("Candidate comparison changed")
    if config.get("selection_rule", {}).get("selected_candidate") != MODEL_ID:
        raise KmePrecautionProxyError("Selected candidate changed")
    return config


def _prepare_rows(
    region_cases: Mapping[tuple[str, date], int],
    regions: Mapping[str, str],
    mapping: Mapping[str, str],
    population: Mapping[str, Mapping[int, int | None]],
    *,
    first_year: int,
    last_year: int,
) -> list[CurrentWeekRow]:
    weeks = sorted(
        week
        for week in {week for _, week in region_cases}
        if first_year <= week.year <= last_year
    )
    rows: list[CurrentWeekRow] = []
    for issue_week in weeks:
        for region_code in sorted(regions):
            key = (region_code, issue_week)
            if key not in region_cases:
                raise KmePrecautionProxyError(f"Incomplete region-week KME grid: {key}")
            target = region_cases[key]
            if target < 0:
                raise KmePrecautionProxyError(f"Negative current-week KME target: {key}")
            exposure, year_min, year_max = selected_region_population(
                region_code, issue_week, mapping, population
            )
            seasonal_sin, seasonal_cos = annual_harmonic(issue_week)
            rows.append(
                CurrentWeekRow(
                    region_code,
                    issue_week,
                    target,
                    exposure,
                    year_min,
                    year_max,
                    seasonal_sin,
                    seasonal_cos,
                )
            )
    if not rows or len(rows) != len(weeks) * 12:
        raise KmePrecautionProxyError("Current-week region panel is incomplete")
    return rows


def _design_matrix(
    rows: Sequence[CurrentWeekRow], region_levels: Sequence[str]
) -> tuple[np.ndarray, tuple[str, ...]]:
    reference = region_levels[0]
    columns = (
        "intercept",
        "seasonal_sin_annual",
        "seasonal_cos_annual",
        *(f"region[{code}]" for code in region_levels if code != reference),
    )
    values = [
        [
            1.0,
            row.seasonal_sin,
            row.seasonal_cos,
            *(float(row.region_code == code) for code in region_levels if code != reference),
        ]
        for row in rows
    ]
    return np.asarray(values, dtype=np.float64), columns


def _fit_glm(
    rows: Sequence[CurrentWeekRow], region_levels: Sequence[str], config: Mapping[str, Any]
) -> tuple[Any, tuple[str, ...], list[str]]:
    matrix, columns = _design_matrix(rows, region_levels)
    model = sm.GLM(
        np.asarray([row.target_value for row in rows], dtype=np.float64),
        matrix,
        family=sm.families.Poisson(),
        offset=np.asarray([row.offset for row in rows], dtype=np.float64),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = model.fit(
            maxiter=int(config["glm"]["maxiter"]),
            tol=float(config["glm"]["tol"]),
        )
    if not result.converged:
        raise KmePrecautionProxyError("Current-week KME GLM did not converge")
    return result, columns, [str(item.message) for item in caught]


def _predict_glm(result: Any, rows: Sequence[CurrentWeekRow], levels: Sequence[str]) -> np.ndarray:
    matrix, _ = _design_matrix(rows, levels)
    predicted = np.asarray(
        result.predict(matrix, offset=np.asarray([row.offset for row in rows])),
        dtype=np.float64,
    )
    if predicted.shape != (len(rows),) or np.any(predicted <= 0) or not np.isfinite(predicted).all():
        raise KmePrecautionProxyError("Current-week KME GLM returned invalid predictions")
    return predicted


def _predict_baseline(
    train_rows: Sequence[CurrentWeekRow], validation_rows: Sequence[CurrentWeekRow]
) -> np.ndarray:
    rate = sum(row.target_value for row in train_rows) / sum(
        row.exposure_per_100000 for row in train_rows
    )
    if not math.isfinite(rate) or rate <= 0:
        raise KmePrecautionProxyError("Historical KME baseline rate is invalid")
    return np.asarray(
        [rate * row.exposure_per_100000 for row in validation_rows],
        dtype=np.float64,
    )


def _summarize(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | int]:
    if actual.shape != predicted.shape or actual.ndim != 1 or len(actual) == 0:
        raise KmePrecautionProxyError("Metric arrays are invalid")
    positive = actual > 0
    contributions = predicted.copy()
    contributions[positive] = (
        actual[positive] * np.log(actual[positive] / predicted[positive])
        - actual[positive]
        + predicted[positive]
    )
    return {
        "n_predictions": len(actual),
        "mae": float(np.mean(np.abs(actual - predicted))),
        "rmse": float(np.sqrt(np.mean(np.square(actual - predicted)))),
        "mean_poisson_deviance": float(np.mean(2.0 * contributions)),
    }


def _prediction_records(
    rows: Sequence[CurrentWeekRow],
    predicted: np.ndarray,
    *,
    scope: str,
    fold_id: str,
    year: int,
    candidate_id: str,
) -> list[dict[str, Any]]:
    return [
        {
            "evaluation_scope": scope,
            "fold_id": fold_id,
            "validation_year": year,
            "candidate_id": candidate_id,
            "statistical_region_code": row.region_code,
            "issue_week": row.issue_week.isoformat(),
            "signal_week_start": row.issue_week.isoformat(),
            "signal_week_end": (row.issue_week + timedelta(days=6)).isoformat(),
            "actual_reported_kme_cases_current_week": row.target_value,
            "predicted_reported_kme_cases_current_week": float(value),
            "population_exposure": row.population,
            "population_year_min": row.population_year_min,
            "population_year_max": row.population_year_max,
            "actual_incidence_per_100000": row.target_value / row.population * 100_000.0,
            "predicted_incidence_per_100000": float(value) / row.population * 100_000.0,
        }
        for row, value in zip(rows, predicted, strict=True)
    ]


def _quantiles(values: Sequence[float], count: int) -> list[dict[str, float]]:
    array = np.asarray(values, dtype=np.float64)
    probabilities = np.linspace(0.0, 1.0, count)
    return [
        {"percentile": float(p * 100.0), "value": float(value)}
        for p, value in zip(probabilities, np.quantile(array, probabilities), strict=True)
    ]


def _empirical_score(value: float, sorted_reference: np.ndarray) -> float:
    return bisect.bisect_right(sorted_reference, value) / len(sorted_reference) * 100.0


def build_kme_precaution_proxy(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    input_keys = (
        "weekly_cases",
        "population",
        "statistical_region",
        "municipality_statistical_region",
    )
    paths = {key: resolve_repo_path(config["inputs"][key]) for key in input_keys}
    for key, path in paths.items():
        if not path.is_file():
            raise KmePrecautionProxyError(f"Required input is missing: {path}")
        require_hash(path, config["inputs"][f"{key}_sha256"], key)

    regions = read_regions(paths["statistical_region"])
    mapping = read_mapping(paths["municipality_statistical_region"], regions)
    region_cases = read_region_weekly_cases(paths["weekly_cases"], mapping)
    population = read_population(paths["population"])
    evaluation = config["evaluation"]
    audit_year = int(evaluation["opened_retrospective_audit_year"])
    rows = _prepare_rows(
        region_cases,
        regions,
        mapping,
        population,
        first_year=int(evaluation["training_start_year"]),
        last_year=audit_year,
    )
    levels = tuple(sorted(regions))

    records: list[dict[str, Any]] = []
    fold_metrics: list[dict[str, Any]] = []
    validation_years = tuple(evaluation["development_validation_years"])
    folds = [
        (
            "development_rolling_origin",
            f"fold_{index:02d}_validate_{year}",
            year,
        )
        for index, year in enumerate(validation_years, start=1)
    ] + [("opened_2025_retrospective_audit", "opened_2025", audit_year)]
    warning_messages: list[str] = []
    for scope, fold_id, year in folds:
        train = tuple(row for row in rows if row.issue_week.year < year)
        validation = tuple(row for row in rows if row.issue_week.year == year)
        if not train or not validation or len({row.region_code for row in validation}) != 12:
            raise KmePrecautionProxyError(f"Incomplete rolling-origin fold: {fold_id}")
        if max(row.issue_week for row in train) >= min(row.issue_week for row in validation):
            raise KmePrecautionProxyError(f"Training reaches validation in {fold_id}")
        result, _, caught = _fit_glm(train, levels, config)
        warning_messages.extend(caught)
        predictions = {
            BASELINE_ID: _predict_baseline(train, validation),
            MODEL_ID: _predict_glm(result, validation, levels),
        }
        actual = np.asarray([row.target_value for row in validation], dtype=np.float64)
        for candidate_id, predicted in predictions.items():
            summary = _summarize(actual, predicted)
            fold_metrics.append(
                {
                    "evaluation_scope": scope,
                    "fold_id": fold_id,
                    "validation_year": year,
                    "candidate_id": candidate_id,
                    **summary,
                }
            )
            records.extend(
                _prediction_records(
                    validation,
                    predicted,
                    scope=scope,
                    fold_id=fold_id,
                    year=year,
                    candidate_id=candidate_id,
                )
            )

    aggregate_metrics: list[dict[str, Any]] = []
    for scope in ("development_rolling_origin", "opened_2025_retrospective_audit"):
        for candidate_id in CANDIDATE_IDS:
            selected = [
                row
                for row in records
                if row["evaluation_scope"] == scope and row["candidate_id"] == candidate_id
            ]
            summary = _summarize(
                np.asarray(
                    [row["actual_reported_kme_cases_current_week"] for row in selected],
                    dtype=np.float64,
                ),
                np.asarray(
                    [row["predicted_reported_kme_cases_current_week"] for row in selected],
                    dtype=np.float64,
                ),
            )
            aggregate_metrics.append(
                {
                    "evaluation_scope": scope,
                    "candidate_id": candidate_id,
                    "n_folds": len({row["fold_id"] for row in selected}),
                    "n_predictions": summary["n_predictions"],
                    "pooled_mae": summary["mae"],
                    "pooled_rmse": summary["rmse"],
                    "pooled_mean_poisson_deviance": summary["mean_poisson_deviance"],
                }
            )
    aggregate_index = {
        (row["evaluation_scope"], row["candidate_id"]): row
        for row in aggregate_metrics
    }
    metric_names = ("pooled_mae", "pooled_rmse", "pooled_mean_poisson_deviance")
    evidence_passed = all(
        float(aggregate_index[(scope, MODEL_ID)][metric])
        < float(aggregate_index[(scope, BASELINE_ID)][metric])
        for scope in ("development_rolling_origin", "opened_2025_retrospective_audit")
        for metric in metric_names
    )
    if not evidence_passed:
        raise KmePrecautionProxyError("Selected current-week KME model failed its evidence rule")
    selection = {
        "selected_candidate_id": MODEL_ID,
        "baseline_candidate_id": BASELINE_ID,
        "evidence_rule_passed": True,
        "runtime_recent_cases_required": False,
        "runtime_weather_used_by_ai_score": False,
        "rule": config["selection_rule"],
    }

    development_model_records = [
        row
        for row in records
        if row["evaluation_scope"] == "development_rolling_origin"
        and row["candidate_id"] == MODEL_ID
    ]
    reference = np.sort(
        np.asarray(
            [row["predicted_incidence_per_100000"] for row in development_model_records],
            dtype=np.float64,
        )
    )
    display = config["display_calibration"]
    low_upper = float(display["low_upper_percentile"])
    medium_upper = float(display["medium_upper_percentile"])
    bands: dict[str, list[dict[str, Any]]] = {label: [] for label in display["labels"]}
    for row in development_model_records:
        score = _empirical_score(float(row["predicted_incidence_per_100000"]), reference)
        label = "Nizko" if score <= low_upper else "Srednje" if score <= medium_upper else "Visoko"
        bands[label].append(row)
    band_summary = [
        {
            "label": label,
            "n": len(bands[label]),
            "mean_actual_incidence_per_100000": statistics.fmean(
                float(row["actual_incidence_per_100000"]) for row in bands[label]
            ),
            "mean_predicted_incidence_per_100000": statistics.fmean(
                float(row["predicted_incidence_per_100000"]) for row in bands[label]
            ),
        }
        for label in display["labels"]
    ]
    observed = [row["mean_actual_incidence_per_100000"] for row in band_summary]
    if observed != sorted(observed) or len(set(observed)) != 3:
        raise KmePrecautionProxyError("KME display bands are not monotonic")
    calibration = {
        "schema_version": 1,
        "interpretation": "relative_percentile_not_absolute_or_personal_risk",
        "kme": {
            "reference_scope": display["reference"],
            "reference_n": len(reference),
            "quantiles": _quantiles(reference, int(display["quantile_grid_points"])),
            "low_upper_percentile": low_upper,
            "medium_upper_percentile": medium_upper,
            "spatial_scope": "statistical_region_not_municipality",
            "development_band_summary": band_summary,
        },
    }

    final_result, columns, final_warnings = _fit_glm(rows, levels, config)
    warning_messages.extend(final_warnings)
    output_directory = resolve_repo_path(config["outputs"]["directory"])
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = {
        key: output_directory / filename
        for key, filename in config["outputs"].items()
        if key not in {"directory", "report"}
    }
    coefficients = [
        {
            "feature": feature,
            "coefficient": float(coefficient),
            "standard_error": float(standard_error),
        }
        for feature, coefficient, standard_error in zip(
            columns, final_result.params, final_result.bse, strict=True
        )
    ]
    write_csv_rows(output_paths["coefficients"], COEFFICIENT_COLUMNS, coefficients)
    write_csv_rows(output_paths["fold_predictions"], PREDICTION_COLUMNS, records)
    write_csv_rows(output_paths["fold_metrics"], METRIC_COLUMNS, fold_metrics)
    write_csv_rows(output_paths["aggregate_metrics"], AGGREGATE_COLUMNS, aggregate_metrics)
    _write_json(output_paths["selection"], selection)
    _write_json(output_paths["display_calibration"], calibration)

    manifest = {
        "schema_version": 1,
        "status": "sealed_for_current_week_no_runtime_case_inference",
        "selected_candidate_id": MODEL_ID,
        "coefficient_sha256": sha256_file(output_paths["coefficients"]),
        "feature_names": list(columns),
        "population_offset": "log(statistical_region_population/100000)",
        "training_period": {
            "first_issue_week": min(row.issue_week for row in rows).isoformat(),
            "last_issue_week": max(row.issue_week for row in rows).isoformat(),
            "rows": len(rows),
            "target": "reported_kme_cases_in_current_signal_week",
        },
        "runtime_contract": {
            "recent_cases_required": False,
            "weather_used_by_ai_score": False,
            "output_target_timing": "current_signal_week",
            "spatial_scope": "statistical_region",
            "output_is_personal_risk": False,
        },
        "statsmodels_version": statsmodels.__version__,
        "code": file_record(Path(__file__).resolve()),
        "configuration": file_record(config_path),
        "input_sources": {key: file_record(path) for key, path in paths.items()},
    }
    _write_json(output_paths["model_manifest"], manifest)
    quality = {
        "schema_version": 1,
        "status": "pass",
        "checks": {
            "current_week_target_used": True,
            "rolling_origin_used": True,
            "runtime_case_features_absent": True,
            "runtime_weather_features_absent": True,
            "fixed_twelve_region_support": True,
            "strictly_earlier_population_used": all(
                row.population_year_max < row.issue_week.year for row in rows
            ),
            "selected_model_beats_baseline_on_all_declared_metrics": evidence_passed,
            "display_bands_monotonic_in_development_evidence": True,
            "personal_risk_output_absent": True,
            "fit_warning_count_is_zero": len(warning_messages) == 0,
        },
        "outputs": {
            key: file_record(path)
            for key, path in output_paths.items()
            if key != "quality_summary" and path.is_file()
        },
    }
    if not all(quality["checks"].values()):
        raise KmePrecautionProxyError("One or more KME proxy quality checks failed")
    _write_json(output_paths["quality_summary"], quality)

    dev_base = aggregate_index[("development_rolling_origin", BASELINE_ID)]
    dev_model = aggregate_index[("development_rolling_origin", MODEL_ID)]
    audit_base = aggregate_index[("opened_2025_retrospective_audit", BASELINE_ID)]
    audit_model = aggregate_index[("opened_2025_retrospective_audit", MODEL_ID)]
    report_path = resolve_repo_path(config["outputs"]["report"])
    report_path.write_text(
        "# KME current-week precaution proxy\n\n"
        "The model target is the reported KME case count in the current signal week t at statistical-region level. "
        "Runtime inference uses region, annual seasonality and strictly earlier population; it uses neither recent case reports nor weather. "
        "The 0-100 display is the percentile of predicted current-week incidence against rolling-origin predictions from 2018-2024, not personal risk.\n\n"
        f"Development pooled MAE: model {float(dev_model['pooled_mae']):.4f}, baseline {float(dev_base['pooled_mae']):.4f}. "
        f"Opened 2025 retrospective MAE: model {float(audit_model['pooled_mae']):.4f}, baseline {float(audit_base['pooled_mae']):.4f}.\n",
        encoding="utf-8",
    )
    return quality


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the current-week regional KME proxy")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()
    print(json.dumps(build_kme_precaution_proxy(args.config), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
