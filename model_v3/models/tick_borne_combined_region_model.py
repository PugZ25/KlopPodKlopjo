from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import catboost
import numpy as np
import statsmodels

from model_v3.models import kme_region_model as engine
from model_v3.panel.tick_borne_combined_eight_week_target import (
    read_calendar,
    read_region_weekly_components,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "tick_borne_combined_region_model.json"
)

PUBLIC_ID = {
    engine.BASELINE_RATE: "baseline_region_historical_rate",
    engine.BASELINE_PERSISTENCE: "baseline_persistence_8w",
    engine.GLM_BASE: "glm_seasonal_region_offset",
    engine.GLM_PAST: "glm_past_combined_offset",
    engine.GLM_WEATHER_ONLY: "glm_weather_only_offset",
    engine.GLM_SEASONAL_WEATHER: "glm_seasonal_region_weather_offset",
    engine.GLM_FULL: "glm_combined_weather_offset",
    engine.CATBOOST_WEATHER: "catboost_combined_weather_offset",
}
PUBLIC_SYSTEM_IDS = tuple(PUBLIC_ID[candidate] for candidate in engine.SYSTEM_IDS)

FEATURE_PANEL_COLUMNS = (
    "statistical_region_code",
    "statistical_region_name",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "target_reported_lyme_plus_kme_cases_next_8w",
    "population_exposure",
    "population_year_min",
    "population_year_max",
    "population_exposure_per_100000",
    "offset_log_population_per_100000",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
    "past_8w_reported_lyme_plus_kme_cases",
    "past_8w_reported_lyme_plus_kme_incidence_per_100000",
    "past_case_window_start",
    "past_case_window_end",
    "latest_past_case_week_used",
    "weather_window_start",
    "latest_weather_week_used",
    "latest_weather_week_end",
) + engine.WEATHER_FEATURE_COLUMNS

FOLD_MANIFEST_COLUMNS = engine.FOLD_MANIFEST_COLUMNS
PREDICTION_COLUMNS = (
    "fold_id",
    "validation_iso_year",
    "system_type",
    "candidate_id",
    "statistical_region_code",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "actual_target_reported_lyme_plus_kme_cases_next_8w",
    "predicted_target_reported_lyme_plus_kme_cases_next_8w",
    "population_exposure",
    "population_year_min",
    "population_year_max",
    "past_8w_reported_lyme_plus_kme_cases",
    "past_8w_reported_lyme_plus_kme_incidence_per_100000",
    "latest_past_case_week_used",
    "latest_weather_week_used",
    "latest_weather_week_end",
    "fit_target_end_max",
    "absolute_error",
    "squared_error",
    "poisson_deviance_contribution",
    "poisson_deviance_status",
)
FOLD_METRIC_COLUMNS = engine.FOLD_METRIC_COLUMNS
AGGREGATE_METRIC_COLUMNS = engine.AGGREGATE_METRIC_COLUMNS
DIAGNOSTIC_COLUMNS = engine.DIAGNOSTIC_COLUMNS
COEFFICIENT_COLUMNS = engine.COEFFICIENT_COLUMNS
IMPORTANCE_COLUMNS = engine.IMPORTANCE_COLUMNS


class CombinedModelError(ValueError):
    """Raised when the combined Lyme-plus-KME model contract is violated."""


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    design = config.get("design", {})
    if config.get("schema_version") != 1:
        raise CombinedModelError("Unsupported combined model schema_version")
    if design.get("target") != "target_reported_lyme_plus_kme_cases_next_8w":
        raise CombinedModelError("Combined model target changed")
    if design.get("target_offsets") != list(range(1, 9)):
        raise CombinedModelError("Combined model target must be t+1 through t+8")
    if design.get("issue_week_included") is not False:
        raise CombinedModelError("Combined model target must exclude issue week")
    if design.get("composite_scope") != "reported_Lyme_plus_KME_only_not_all_tick_borne_diseases":
        raise CombinedModelError("Combined disease scope must remain explicit")
    configured = tuple(system["candidate_id"] for system in config.get("systems", ()))
    if configured != PUBLIC_SYSTEM_IDS:
        raise CombinedModelError("Combined model candidate list changed")
    return config


def verify_inputs(
    config: Mapping[str, Any], repo_root: Path = REPO_ROOT
) -> tuple[dict[str, Path], dict[str, str]]:
    inputs = config["inputs"]
    labels = tuple(key[:-7] for key in inputs if key.endswith("_sha256"))
    paths = {label: engine.resolve_repo_path(inputs[label], repo_root) for label in labels}
    hashes: dict[str, str] = {}
    for label, path in paths.items():
        actual = engine.sha256_file(path)
        expected = inputs[f"{label}_sha256"]
        if actual != expected:
            raise CombinedModelError(
                f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
            )
        hashes[label] = actual
    return paths, hashes


def read_targets(
    path: Path, regions: Mapping[str, str]
) -> tuple[list[engine.TargetObservation], dict[str, int]]:
    required = {
        "statistical_region_code",
        "issue_week",
        "target_window_start",
        "target_window_end",
        "target_reported_lyme_cases_next_8w",
        "target_reported_kme_cases_next_8w",
        "target_reported_lyme_plus_kme_cases_next_8w",
        "target_status",
        "target_training_eligible",
    }
    result: list[engine.TargetObservation] = []
    seen: set[tuple[str, date]] = set()
    component_totals = Counter()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise CombinedModelError("Combined target schema is invalid")
        for row in reader:
            if row["target_training_eligible"] != "true":
                continue
            if row["target_status"] != "complete":
                raise CombinedModelError("Training-eligible combined target is not complete")
            region = row["statistical_region_code"]
            if region not in regions:
                raise CombinedModelError(f"Unknown target region: {region}")
            issue = engine.parse_monday(row["issue_week"])
            target_start = engine.parse_monday(row["target_window_start"])
            target_end = engine.parse_monday(row["target_window_end"])
            if target_start != issue + timedelta(weeks=1):
                raise CombinedModelError("Combined target does not begin at t+1")
            if target_end != issue + timedelta(weeks=8):
                raise CombinedModelError("Combined target does not end at t+8")
            try:
                lyme = int(row["target_reported_lyme_cases_next_8w"])
                kme = int(row["target_reported_kme_cases_next_8w"])
                combined = int(row["target_reported_lyme_plus_kme_cases_next_8w"])
            except ValueError as exc:
                raise CombinedModelError("Complete combined target must be integer-valued") from exc
            if lyme < 0 or kme < 0 or combined < 0:
                raise CombinedModelError("Combined target components must be non-negative")
            if combined != lyme + kme:
                raise CombinedModelError("Combined target differs from Lyme plus KME")
            key = (region, issue)
            if key in seen:
                raise CombinedModelError(f"Duplicate combined target key: {key}")
            seen.add(key)
            result.append(
                engine.TargetObservation(region, issue, target_start, target_end, combined)
            )
            component_totals.update(lyme=lyme, kme=kme, combined=combined)
    if not result:
        raise CombinedModelError("No complete combined targets")
    return sorted(result, key=lambda row: (row.issue_week, row.region_code)), dict(component_totals)


def public_feature(value: str) -> str:
    return value.replace(
        "past_8w_kme_incidence_per_100000",
        "past_8w_reported_lyme_plus_kme_incidence_per_100000",
    ).replace(
        "past_8w_kme_cases",
        "past_8w_reported_lyme_plus_kme_cases",
    )


def public_candidate(candidate_id: str) -> str:
    try:
        return PUBLIC_ID[candidate_id]
    except KeyError as exc:
        raise CombinedModelError(f"Unknown internal candidate: {candidate_id}") from exc


def public_fold(fold: engine.Fold) -> engine.Fold:
    return engine.Fold(
        f"tick_borne_{fold.validation_iso_year}",
        fold.validation_iso_year,
        fold.validation_start,
        fold.validation_end,
        fold.train_rows,
        fold.validation_rows,
        fold.n_purged,
    )


def feature_panel_row(row: engine.PreparedRow) -> dict[str, Any]:
    return {
        "statistical_region_code": row.region_code,
        "statistical_region_name": row.region_name,
        "issue_week": row.issue_week,
        "target_window_start": row.target_start,
        "target_window_end": row.target_end,
        "target_reported_lyme_plus_kme_cases_next_8w": row.target_value,
        "population_exposure": row.population,
        "population_year_min": row.population_year_min,
        "population_year_max": row.population_year_max,
        "population_exposure_per_100000": row.exposure_per_100000,
        "offset_log_population_per_100000": row.offset,
        "seasonal_sin_annual": row.seasonal_sin,
        "seasonal_cos_annual": row.seasonal_cos,
        "past_8w_reported_lyme_plus_kme_cases": row.past_cases,
        "past_8w_reported_lyme_plus_kme_incidence_per_100000": row.past_incidence,
        "past_case_window_start": row.past_window_start,
        "past_case_window_end": row.past_window_end,
        "latest_past_case_week_used": row.past_window_end,
        "weather_window_start": row.weather_window_start,
        "latest_weather_week_used": row.latest_weather_week,
        "latest_weather_week_end": row.latest_weather_week_end,
        **row.weather_values,
    }


def transform_results(
    internal: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    predictions = []
    for source in internal["predictions"]:
        row = dict(source)
        row["candidate_id"] = public_candidate(row["candidate_id"])
        row["actual_target_reported_lyme_plus_kme_cases_next_8w"] = row.pop(
            "actual_target_kme_cases_next_8w"
        )
        row["predicted_target_reported_lyme_plus_kme_cases_next_8w"] = row.pop(
            "predicted_target_kme_cases_next_8w"
        )
        row["past_8w_reported_lyme_plus_kme_cases"] = row.pop("past_8w_kme_cases")
        row["past_8w_reported_lyme_plus_kme_incidence_per_100000"] = row.pop(
            "past_8w_kme_incidence_per_100000"
        )
        predictions.append(row)

    def candidate_rows(name: str) -> list[dict[str, Any]]:
        rows = []
        for source in internal[name]:
            row = dict(source)
            row["candidate_id"] = public_candidate(row["candidate_id"])
            if "feature" in row:
                row["feature"] = public_feature(str(row["feature"]))
            for key in (
                "training_scaler_means",
                "training_scaler_standard_deviations",
            ):
                if key in row:
                    row[key] = public_feature(str(row[key]))
            rows.append(row)
        return rows

    return {
        "predictions": predictions,
        "fold_metrics": candidate_rows("fold_metrics"),
        "aggregate_metrics": candidate_rows("aggregate_metrics"),
        "diagnostics": candidate_rows("diagnostics"),
        "coefficients": candidate_rows("coefficients"),
        "importance": candidate_rows("importance"),
    }


def public_selection(internal: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(internal)
    result["selected_candidate_id"] = public_candidate(
        str(internal["selected_candidate_id"])
    )
    result["best_non_ml_candidate_id"] = public_candidate(
        str(internal["best_non_ml_candidate_id"])
    )
    result["approval_status"] = "combined_development_system_ready_for_freeze"
    result["composite_scope"] = "reported_Lyme_plus_KME_only_not_all_tick_borne_diseases"
    return result


def file_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": engine.repository_path(path, repo_root),
        "bytes": path.stat().st_size,
        "sha256": engine.sha256_file(path),
    }


def render_report(
    rows: Sequence[engine.PreparedRow],
    folds: Sequence[engine.Fold],
    results: Mapping[str, Sequence[Mapping[str, Any]]],
    selection: Mapping[str, Any],
    component_totals: Mapping[str, int],
) -> str:
    metric_lines = []
    for row in results["aggregate_metrics"]:
        deviance = (
            "INVALID"
            if row["poisson_deviance_status"] != "valid"
            else f"{float(row['pooled_mean_poisson_deviance']):.6f}"
        )
        metric_lines.append(
            f"| `{row['candidate_id']}` | {float(row['pooled_mae']):.6f} | "
            f"{float(row['pooled_rmse']):.6f} | {deviance} |"
        )
    kme_share = component_totals["kme"] / component_totals["combined"]
    return f"""# Combined reported Lyme + KME regional model

## Interpretation

The project label **tick-borne diseases** in this experiment means one composite surveillance count: reported Lyme disease cases plus reported KME/TBE cases. It does not cover every tick-borne disease, does not estimate personal risk, and should not replace disease-specific forecasts.

The target is dominated by Lyme: KME contributes {kme_share:.2%} of summed complete overlapping target counts. This model is therefore mainly a combined service-demand/surveillance forecast, not evidence that Lyme and KME share one biological process.

## Design

- Analysis unit: statistical region × issue week.
- Target: reported Lyme + KME cases in exactly t+1..t+8; issue week excluded.
- Population: mandatory log exposure offset and incidence denominator.
- Features evaluated: annual seasonality, region, previous eight completed weeks, and four lagged ERA5-Land summaries.
- Weather aggregation: the existing verified municipality polygon-overlay weekly data, then municipality-area-weighted aggregation to region.
- Validation: expanding rolling origin with target-window containment and an eight-week boundary purge.
- Feature-complete rows: {len(rows)}; folds: {len(folds)} ({min(fold.validation_iso_year for fold in folds)}–{max(fold.validation_iso_year for fold in folds)}).

## Development results

| Candidate | Pooled MAE | RMSE | Poisson deviance |
|---|---:|---:|---:|
{chr(10).join(metric_lines)}

Selected candidate: **`{selection['selected_candidate_id']}`**.

CatBoost is promoted only when it beats the best non-ML model on pooled MAE and in every validation fold. No extensive hyperparameter search, classification target, thresholds, or risk categories were used.

These are development results through 2025. ISO year 2026 remains unavailable in canonical outcomes and is not evaluated here.
"""


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    paths, hashes = verify_inputs(config, repo_root)
    regions = engine.read_regions(paths["statistical_region"])
    mapping = engine.read_mapping(paths["municipality_statistical_region"], regions)
    targets, component_totals = read_targets(paths["target"], regions)
    weeks = read_calendar(paths["calendar"])
    components = read_region_weekly_components(
        paths["weekly_cases"], mapping, tuple(regions), weeks
    )
    combined_cases = {
        key: values[0] + values[1] for key, values in components.items()
    }
    population = engine.read_population(paths["population"])
    areas = engine.read_areas(paths["municipality_area"], mapping)
    development_weather = engine.read_weather_file(paths["development_weather"])
    extension_weather = engine.read_weather_file(paths["weather_extension"])
    weather = engine.combine_weather_sources(development_weather, extension_weather)
    region_weather = engine.aggregate_region_weather(weather, mapping, areas)
    rows, exclusions = engine.prepare_rows(
        targets, regions, mapping, combined_cases, population, region_weather
    )
    folds = [public_fold(fold) for fold in engine.generate_folds(rows, config)]
    internal_results = engine.evaluate(rows, folds, config)
    results = transform_results(internal_results)
    selection = public_selection(
        engine.select_system(
            internal_results["aggregate_metrics"], internal_results["fold_metrics"]
        )
    )

    output = config["outputs"]
    output_directory = engine.resolve_repo_path(output["directory"], repo_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = {
        key: output_directory / output[key]
        for key in (
            "feature_panel",
            "fold_manifest",
            "fold_predictions",
            "fold_metrics",
            "aggregate_metrics",
            "fit_diagnostics",
            "coefficients",
            "feature_importance",
            "selection",
            "quality_summary",
        )
    }
    report_path = engine.resolve_repo_path(output["report"], repo_root)
    engine.write_csv(
        output_paths["feature_panel"],
        FEATURE_PANEL_COLUMNS,
        [feature_panel_row(row) for row in rows],
    )
    engine.write_csv(
        output_paths["fold_manifest"],
        FOLD_MANIFEST_COLUMNS,
        [
            engine.fold_manifest_row(fold, int(config["validation"]["target_embargo_weeks"]))
            for fold in folds
        ],
    )
    engine.write_csv(output_paths["fold_predictions"], PREDICTION_COLUMNS, results["predictions"])
    engine.write_csv(output_paths["fold_metrics"], FOLD_METRIC_COLUMNS, results["fold_metrics"])
    engine.write_csv(
        output_paths["aggregate_metrics"],
        AGGREGATE_METRIC_COLUMNS,
        results["aggregate_metrics"],
    )
    engine.write_csv(output_paths["fit_diagnostics"], DIAGNOSTIC_COLUMNS, results["diagnostics"])
    engine.write_csv(output_paths["coefficients"], COEFFICIENT_COLUMNS, results["coefficients"])
    engine.write_csv(
        output_paths["feature_importance"], IMPORTANCE_COLUMNS, results["importance"]
    )
    output_paths["selection"].write_text(
        json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(
        render_report(rows, folds, results, selection, component_totals),
        encoding="utf-8",
    )
    material_outputs = {
        key: file_record(path, repo_root)
        for key, path in output_paths.items()
        if key != "quality_summary"
    }
    material_outputs["report"] = file_record(report_path, repo_root)
    kme_share = component_totals["kme"] / component_totals["combined"]
    quality = {
        "schema_version": 1,
        "pipeline": "model_v3.models.tick_borne_combined_region_model",
        "status": "complete_development_evaluation_ready_for_freeze",
        "composite_scope": "reported_Lyme_plus_KME_only_not_all_tick_borne_diseases",
        "configuration": file_record(config_path.resolve(), repo_root),
        "code": file_record(Path(__file__).resolve(), repo_root),
        "engine": file_record(Path(engine.__file__).resolve(), repo_root),
        "library_versions": {
            "catboost": catboost.__version__,
            "numpy": np.__version__,
            "statsmodels": statsmodels.__version__,
        },
        "inputs": {
            key: {"path": engine.repository_path(paths[key], repo_root), "sha256": hashes[key]}
            for key in paths
        },
        "component_target_mass": {
            **component_totals,
            "lyme_share": component_totals["lyme"] / component_totals["combined"],
            "kme_share": kme_share,
            "interpretation": "overlapping_complete_eight_week_target_rows_not_unique_cases",
        },
        "data_support": {
            "n_feature_complete_rows": len(rows),
            "first_issue_week": min(row.issue_week for row in rows).isoformat(),
            "last_issue_week": max(row.issue_week for row in rows).isoformat(),
            "excluded_target_rows": exclusions,
            "n_folds": len(folds),
            "validation_iso_years": [fold.validation_iso_year for fold in folds],
            "n_validation_predictions_per_system": sum(
                len(fold.validation_rows) for fold in folds
            ),
        },
        "checks": {
            "combined_target_equals_Lyme_plus_KME": True,
            "target_exactly_t_plus_1_through_t_plus_8": True,
            "issue_week_excluded": True,
            "train_target_end_strictly_before_validation": True,
            "validation_target_windows_contained": True,
            "eight_week_boundary_purge_applied": True,
            "past_cases_latest_t_minus_1": True,
            "weather_latest_completed_week_t_minus_1": True,
            "current_or_future_weather_used": False,
            "population_issue_or_future_year_used": False,
            "population_as_ordinary_feature": False,
            "weather_scaling_fit_on_validation": False,
            "catboost_hyperparameter_search": False,
            "2026_outcomes_accessed": False,
            "classification_logic_used": False,
            "risk_categories_created": False,
            "personal_risk_output_created": False,
        },
        "feature_contract": config["feature_contract"],
        "aggregate_metrics": results["aggregate_metrics"],
        "selection": selection,
        "outputs": material_outputs,
    }
    output_paths["quality_summary"].write_text(
        json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True, default=engine.json_value)
        + "\n",
        encoding="utf-8",
    )
    quality["quality_summary"] = file_record(output_paths["quality_summary"], repo_root)
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the combined reported Lyme-plus-KME regional model."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    quality = run(args.config)
    print(
        "Created combined tick-borne model evaluation: "
        f"selected={quality['selection']['selected_candidate_id']}, "
        f"folds={quality['data_support']['n_folds']}, "
        f"validation_rows_per_system={quality['data_support']['n_validation_predictions_per_system']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
