from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import warnings
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import statsmodels
import statsmodels.api as sm

from model_v3.models.kme_region_model import (
    KmeModelError,
    annual_harmonic,
    read_mapping,
    read_population,
    read_regions,
    repository_path,
    resolve_repo_path,
    selected_region_population,
    sha256_file,
)
from model_v3.models.tick_borne_combined_region_model import read_targets
from model_v3.panel.tick_borne_combined_eight_week_target import (
    read_calendar,
    read_region_weekly_components,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "tick_borne_combined_model_freeze.json"
)
COEFFICIENT_COLUMNS = ("feature", "coefficient", "standard_error")
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
    "offset_log_population_per_100000",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
    "past_8w_reported_lyme_plus_kme_cases",
    "past_8w_reported_lyme_plus_kme_incidence_per_100000",
    "latest_past_case_week_used",
    "weather_required_by_selected_model",
)


class CombinedFreezeError(ValueError):
    """Raised when the combined-model freeze contract is violated."""


@dataclass(frozen=True)
class FinalRow:
    region_code: str
    region_name: str
    issue_week: date
    target_start: date
    target_end: date
    target: int
    population: int
    population_year_min: int
    population_year_max: int
    seasonal_sin: float
    seasonal_cos: float
    past_cases: int
    past_incidence: float
    latest_past_case_week: date

    @property
    def offset(self) -> float:
        return math.log(self.population / 100_000.0)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or config.get("freeze", {}).get("status") != "FROZEN":
        raise CombinedFreezeError("Combined model freeze is not valid")
    if config["task"]["target_offsets"] != list(range(1, 9)):
        raise CombinedFreezeError("Frozen target must remain t+1 through t+8")
    if config["task"]["issue_week_included"] is not False:
        raise CombinedFreezeError("Frozen target must exclude issue week")
    if config["selected_model"]["candidate_id"] != "glm_past_combined_offset":
        raise CombinedFreezeError("Frozen selected model changed")
    if config["protected_period"]["pipeline_outcome_access"] is not False:
        raise CombinedFreezeError("Protected-period outcome access changed")
    return config


def file_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": repository_path(path, repo_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


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
            raise CombinedFreezeError(
                f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
            )
        hashes[label] = actual
    return paths, hashes


def parse_monday(value: str, label: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise CombinedFreezeError(f"Invalid {label}: {value!r}") from exc
    if parsed.weekday() != 0:
        raise CombinedFreezeError(f"{label} is not Monday: {value!r}")
    return parsed


def read_feature_panel(path: Path, protected_year: int = 2026) -> list[FinalRow]:
    required = {
        "statistical_region_code",
        "issue_week",
        "target_window_start",
        "target_window_end",
        "target_reported_lyme_plus_kme_cases_next_8w",
        "population_exposure",
        "population_year_min",
        "population_year_max",
        "offset_log_population_per_100000",
        "seasonal_sin_annual",
        "seasonal_cos_annual",
        "past_8w_reported_lyme_plus_kme_cases",
        "past_8w_reported_lyme_plus_kme_incidence_per_100000",
        "latest_past_case_week_used",
    }
    result: list[FinalRow] = []
    seen: set[tuple[str, date]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise CombinedFreezeError("Frozen feature-panel schema is invalid")
        for source in reader:
            issue = parse_monday(source["issue_week"], "issue_week")
            target_start = parse_monday(source["target_window_start"], "target_window_start")
            target_end = parse_monday(source["target_window_end"], "target_window_end")
            if issue.isocalendar().year >= protected_year or target_end.isocalendar().year >= protected_year:
                raise CombinedFreezeError("Protected 2026 row entered frozen feature panel")
            if target_start != issue + timedelta(weeks=1) or target_end != issue + timedelta(weeks=8):
                raise CombinedFreezeError("Frozen target window is not exactly t+1..t+8")
            key = (source["statistical_region_code"], issue)
            if key in seen:
                raise CombinedFreezeError(f"Duplicate frozen feature row: {key}")
            seen.add(key)
            try:
                target = int(source["target_reported_lyme_plus_kme_cases_next_8w"])
                population = int(source["population_exposure"])
                year_min = int(source["population_year_min"])
                year_max = int(source["population_year_max"])
                offset = float(source["offset_log_population_per_100000"])
                seasonal_sin = float(source["seasonal_sin_annual"])
                seasonal_cos = float(source["seasonal_cos_annual"])
                past_cases = int(source["past_8w_reported_lyme_plus_kme_cases"])
                past_incidence = float(
                    source["past_8w_reported_lyme_plus_kme_incidence_per_100000"]
                )
            except ValueError as exc:
                raise CombinedFreezeError("Frozen feature panel has invalid numeric value") from exc
            latest_past = parse_monday(
                source["latest_past_case_week_used"], "latest_past_case_week_used"
            )
            if target < 0 or population <= 0 or past_cases < 0 or past_incidence < 0:
                raise CombinedFreezeError("Frozen count, incidence, or exposure is invalid")
            if year_min > year_max or year_max >= issue.year:
                raise CombinedFreezeError("Population is not strictly earlier than issue time")
            if latest_past != issue - timedelta(weeks=1):
                raise CombinedFreezeError("Past epidemiological feature does not end at t-1")
            if not math.isclose(offset, math.log(population / 100_000.0), abs_tol=1e-12):
                raise CombinedFreezeError("Population and frozen offset disagree")
            if not math.isclose(
                past_incidence,
                past_cases / population * 100_000.0,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise CombinedFreezeError("Past incidence and denominator disagree")
            result.append(
                FinalRow(
                    key[0],
                    source.get("statistical_region_name", key[0]),
                    issue,
                    target_start,
                    target_end,
                    target,
                    population,
                    year_min,
                    year_max,
                    seasonal_sin,
                    seasonal_cos,
                    past_cases,
                    past_incidence,
                    latest_past,
                )
            )
    if not result:
        raise CombinedFreezeError("Frozen feature panel is empty")
    return sorted(result, key=lambda row: (row.issue_week, row.region_code))


def prepare_final_rows(
    targets: Sequence[Any],
    regions: Mapping[str, str],
    mapping: Mapping[str, str],
    combined_cases: Mapping[tuple[str, date], int],
    population: Mapping[str, Mapping[int, int | None]],
) -> tuple[list[FinalRow], dict[str, int]]:
    rows: list[FinalRow] = []
    exclusions = Counter()
    for target in targets:
        if target.issue_week.isocalendar().year >= 2026 or target.target_end.isocalendar().year >= 2026:
            raise CombinedFreezeError("Protected 2026 target entered finalization support")
        try:
            population_value, year_min, year_max = selected_region_population(
                target.region_code, target.issue_week, mapping, population
            )
        except KmeModelError as exc:
            if not str(exc).startswith("No safely earlier population"):
                raise
            exclusions["missing_safe_population"] += 1
            continue
        past_weeks = tuple(
            target.issue_week - timedelta(weeks=offset) for offset in range(8, 0, -1)
        )
        if any((target.region_code, week) not in combined_cases for week in past_weeks):
            exclusions["incomplete_past_case_window"] += 1
            continue
        past_cases = sum(combined_cases[(target.region_code, week)] for week in past_weeks)
        seasonal_sin, seasonal_cos = annual_harmonic(target.issue_week)
        rows.append(
            FinalRow(
                target.region_code,
                regions[target.region_code],
                target.issue_week,
                target.target_start,
                target.target_end,
                target.target_value,
                population_value,
                year_min,
                year_max,
                seasonal_sin,
                seasonal_cos,
                past_cases,
                past_cases / population_value * 100_000.0,
                past_weeks[-1],
            )
        )
    if not rows:
        raise CombinedFreezeError("No rows satisfy final selected-model support")
    return sorted(rows, key=lambda row: (row.issue_week, row.region_code)), dict(exclusions)


def feature_panel_row(row: FinalRow) -> dict[str, Any]:
    return {
        "statistical_region_code": row.region_code,
        "statistical_region_name": row.region_name,
        "issue_week": row.issue_week.isoformat(),
        "target_window_start": row.target_start.isoformat(),
        "target_window_end": row.target_end.isoformat(),
        "target_reported_lyme_plus_kme_cases_next_8w": row.target,
        "population_exposure": row.population,
        "population_year_min": row.population_year_min,
        "population_year_max": row.population_year_max,
        "offset_log_population_per_100000": row.offset,
        "seasonal_sin_annual": row.seasonal_sin,
        "seasonal_cos_annual": row.seasonal_cos,
        "past_8w_reported_lyme_plus_kme_cases": row.past_cases,
        "past_8w_reported_lyme_plus_kme_incidence_per_100000": row.past_incidence,
        "latest_past_case_week_used": row.latest_past_case_week.isoformat(),
        "weather_required_by_selected_model": "false",
    }


def design_matrix(
    rows: Sequence[FinalRow],
    region_levels: Sequence[str],
    past_mean: float,
    past_standard_deviation: float,
) -> tuple[np.ndarray, tuple[str, ...]]:
    if past_standard_deviation <= 0:
        raise CombinedFreezeError("Past-incidence standard deviation must be positive")
    reference = region_levels[0]
    columns = (
        "intercept",
        "seasonal_sin_annual",
        "seasonal_cos_annual",
    ) + tuple(
        f"region[{region}]" for region in region_levels if region != reference
    ) + ("z_past_8w_reported_lyme_plus_kme_incidence_per_100000",)
    matrix = []
    for row in rows:
        if row.region_code not in region_levels:
            raise CombinedFreezeError(f"Unknown region level: {row.region_code}")
        matrix.append(
            [
                1.0,
                row.seasonal_sin,
                row.seasonal_cos,
                *(float(row.region_code == region) for region in region_levels if region != reference),
                (row.past_incidence - past_mean) / past_standard_deviation,
            ]
        )
    return np.asarray(matrix, dtype=float), columns


def fit_model(
    rows: Sequence[FinalRow], config: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, float]]:
    region_levels = tuple(sorted({row.region_code for row in rows}))
    if len(region_levels) != 12:
        raise CombinedFreezeError("Final fit does not contain 12 regions")
    past_values = [row.past_incidence for row in rows]
    past_mean = statistics.fmean(past_values)
    past_standard_deviation = statistics.pstdev(past_values)
    matrix, columns = design_matrix(
        rows, region_levels, past_mean, past_standard_deviation
    )
    model = sm.GLM(
        np.asarray([row.target for row in rows], dtype=float),
        matrix,
        family=sm.families.Poisson(),
        offset=np.asarray([row.offset for row in rows], dtype=float),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fitted = model.fit(
            maxiter=int(config["selected_model"]["maxiter"]),
            tol=float(config["selected_model"]["tol"]),
        )
    if not fitted.converged:
        raise CombinedFreezeError("Final combined GLM did not converge")
    coefficients = [
        {
            "feature": feature,
            "coefficient": float(coefficient),
            "standard_error": float(standard_error),
        }
        for feature, coefficient, standard_error in zip(
            columns, fitted.params, fitted.bse
        )
    ]
    scaler = {
        "feature": "past_8w_reported_lyme_plus_kme_incidence_per_100000",
        "mean": past_mean,
        "standard_deviation": past_standard_deviation,
        "fit_scope": "all_frozen_feature_panel_rows",
    }
    diagnostics = {
        "candidate_id": "glm_past_combined_offset",
        "n_training_rows": len(rows),
        "n_parameters": len(columns),
        "region_levels": list(region_levels),
        "reference_region": region_levels[0],
        "design_columns": list(columns),
        "converged": bool(fitted.converged),
        "iterations": int(fitted.fit_history.get("iteration", -1)),
        "warning_count": len(caught),
        "warning_messages": [str(item.message) for item in caught],
        "deviance": float(fitted.deviance),
        "pearson_chi2": float(fitted.pearson_chi2),
        "statsmodels_version": statsmodels.__version__,
    }
    return coefficients, diagnostics, scaler


def read_metrics(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def render_report(
    config: Mapping[str, Any],
    metrics: Sequence[Mapping[str, str]],
    diagnostics: Mapping[str, Any],
    exclusions: Mapping[str, int],
) -> str:
    rows = []
    for metric in metrics:
        deviance = metric["pooled_mean_poisson_deviance"] or "INVALID"
        rows.append(
            f"| `{metric['candidate_id']}` | {float(metric['pooled_mae']):.6f} | "
            f"{float(metric['pooled_rmse']):.6f} | {deviance} |"
        )
    return f"""# Combined reported Lyme + KME model-selection freeze

## Frozen task

- Composite: reported Lyme disease cases + reported KME/TBE cases only; not every tick-borne disease.
- Analysis unit: statistical region × issue week.
- Target: exactly t+1..t+8, excluding issue week.
- Output: expected reported combined case count, not personal risk.

## Frozen selected model

Selected candidate: **`glm_past_combined_offset`**.

`{config['selected_model']['formula']}`

Population is an explicit offset and incidence denominator. The past-case feature uses exactly the eight completed weeks t−8..t−1. Weather was evaluated but is not in the selected model. CatBoost had better pooled MAE but failed the predeclared every-fold stability rule, improving 7/8 folds, so it was not promoted after results were observed.

Final fit: {diagnostics['n_training_rows']} rows, {diagnostics['n_parameters']} parameters, converged={str(diagnostics['converged']).lower()}, iterations={diagnostics['iterations']}, warnings={diagnostics['warning_count']}.

Finalization support uses only inputs required by the selected formula. Weather remains in the development ablation but does not exclude final-fit rows. Selected-model exclusions: `{json.dumps(dict(exclusions), sort_keys=True)}`.

## Development evidence

| Candidate | Pooled MAE | RMSE | Poisson deviance |
|---|---:|---:|---:|
{chr(10).join(rows)}

These metrics are rolling-origin development evidence through 2025. No 2026 outcome was used. The composite is strongly dominated by Lyme counts and must not be interpreted as a shared biological disease mechanism.

## Deployment rule

Predictions require the eight most recent completed regional combined case weeks. A prediction is unavailable when any required past week is unavailable; missing weeks are never zero-filled. The first ISO-2026 issue week can be generated from verified late-2025 observations. Later 2026 issues require sequential verified 2026 observations.
"""


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    paths, hashes = verify_inputs(config, repo_root)
    selection = json.loads(paths["development_selection"].read_text(encoding="utf-8"))
    if selection.get("selected_candidate_id") != config["selected_model"]["candidate_id"]:
        raise CombinedFreezeError("Development selection and freeze candidate differ")
    regions = read_regions(paths["statistical_region"])
    mapping = read_mapping(paths["municipality_statistical_region"], regions)
    targets, _component_totals = read_targets(paths["target"], regions)
    weeks = read_calendar(paths["calendar"])
    components = read_region_weekly_components(
        paths["weekly_cases"], mapping, tuple(regions), weeks
    )
    combined_cases = {
        key: values[0] + values[1] for key, values in components.items()
    }
    population = read_population(paths["population"])
    rows, exclusions = prepare_final_rows(
        targets, regions, mapping, combined_cases, population
    )
    coefficients, diagnostics, scaler = fit_model(rows, config)
    output = config["outputs"]
    output_directory = resolve_repo_path(output["directory"], repo_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    feature_panel_path = output_directory / output["feature_panel"]
    coefficient_path = output_directory / output["coefficients"]
    scaler_path = output_directory / output["scaler"]
    diagnostics_path = output_directory / output["fit_diagnostics"]
    manifest_path = output_directory / output["manifest"]
    report_path = resolve_repo_path(output["report"], repo_root)
    with feature_panel_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=FEATURE_PANEL_COLUMNS, extrasaction="raise"
        )
        writer.writeheader()
        writer.writerows(feature_panel_row(row) for row in rows)
    with coefficient_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COEFFICIENT_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(coefficients)
    scaler_path.write_text(
        json.dumps(scaler, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    diagnostics_path.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = read_metrics(paths["development_metrics"])
    report_path.write_text(
        render_report(config, metrics, diagnostics, exclusions), encoding="utf-8"
    )
    outputs = {
        "feature_panel": file_record(feature_panel_path, repo_root),
        "coefficients": file_record(coefficient_path, repo_root),
        "scaler": file_record(scaler_path, repo_root),
        "fit_diagnostics": file_record(diagnostics_path, repo_root),
        "report": file_record(report_path, repo_root),
    }
    manifest = {
        "schema_version": 1,
        "status": "FROZEN_COMBINED_MODEL_2026_OUTCOMES_UNOPENED",
        "freeze": config["freeze"],
        "task": config["task"],
        "selected_model": config["selected_model"],
        "selection": config["selection"],
        "finalization_support": config["finalization_support"],
        "population": config["population"],
        "protected_period": config["protected_period"],
        "configuration": file_record(config_path.resolve(), repo_root),
        "code": file_record(Path(__file__).resolve(), repo_root),
        "inputs": {
            key: {"path": repository_path(paths[key], repo_root), "sha256": hashes[key]}
            for key in paths
        },
        "fit": diagnostics,
        "support": {
            "n_rows": len(rows),
            "first_issue_week": min(row.issue_week for row in rows).isoformat(),
            "last_issue_week": max(row.issue_week for row in rows).isoformat(),
            "exclusions": exclusions,
        },
        "scaler": scaler,
        "checks": {
            "combined_scope_explicit": True,
            "target_exactly_t_plus_1_through_t_plus_8": True,
            "issue_week_excluded": True,
            "past_case_window_exactly_t_minus_8_through_t_minus_1": True,
            "population_strictly_earlier": True,
            "population_is_offset_not_feature": True,
            "weather_in_selected_model": False,
            "weather_required_for_final_fit_row": False,
            "catboost_in_selected_model": False,
            "2026_outcomes_accessed": False,
            "classification_logic_used": False,
            "risk_categories_created": False,
        },
        "outputs": outputs,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest["manifest"] = file_record(manifest_path, repo_root)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze the combined Lyme-plus-KME model.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = run(args.config)
    fit = manifest["fit"]
    print(
        "Frozen combined tick-borne model: "
        f"rows={fit['n_training_rows']}, parameters={fit['n_parameters']}, "
        f"converged={str(fit['converged']).lower()}, outcomes_2026_read=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
