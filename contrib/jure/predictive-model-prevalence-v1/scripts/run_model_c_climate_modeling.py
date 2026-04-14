from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pipeline_utils import PROJECT_ROOT, copy_file, timestamp_utc, write_json


PROCESSING_MODEL_C_DIR = (
    PROJECT_ROOT
    / "data processing - copernicus_forecast_data"
    / "outputs"
    / "model_c"
)
WORKSPACE_DIR = PROJECT_ROOT / "modeling - model_c_climate_effect"
INPUTS_DIR = WORKSPACE_DIR / "inputs"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
REPORTS_DIR = WORKSPACE_DIR / "reports"

SOURCE_FILES = {
    "model_c_observed_reference_yearly.csv": PROCESSING_MODEL_C_DIR
    / "model_c_observed_reference_yearly.csv",
    "model_c_scenario_calibration_table.csv": PROCESSING_MODEL_C_DIR
    / "model_c_scenario_calibration_table.csv",
    "model_c_scenario_projection_table.csv": PROCESSING_MODEL_C_DIR
    / "model_c_scenario_projection_table.csv",
}

TARGET_SPECS = {
    "lyme_prevalence": {
        "target_column": "lyme_cases_per_100k",
        "target_label": "Lyme prevalence per 100k",
        "lag_1_column": "lyme_cases_per_100k_lag_1y",
        "rolling_3_column": "lyme_cases_per_100k_rolling_3y_mean",
    },
    "kme_prevalence": {
        "target_column": "kme_cases_per_100k",
        "target_label": "KME prevalence per 100k",
        "lag_1_column": "kme_cases_per_100k_lag_1y",
        "rolling_3_column": "kme_cases_per_100k_rolling_3y_mean",
    },
    "combined_prevalence": {
        "target_column": "tick_borne_cases_total_per_100k",
        "target_label": "Combined tick-borne prevalence per 100k",
        "lag_1_column": "tick_borne_cases_total_per_100k_lag_1y",
        "rolling_3_column": "tick_borne_cases_total_per_100k_rolling_3y_mean",
    },
}

CLIMATE_FEATURE_COLUMNS = [
    "air_temperature_c_mean_climate",
    "near_surface_specific_humidity_g_kg_climate",
    "precipitation_sum_mm_proxy_climate",
    "soil_moisture_upper_portion_kg_m2_climate",
]

SCENARIO_FEATURE_COLUMNS = ["scenario_is_high_emissions"]
FINAL_VALIDATION_YEARS = [2024, 2025]
INNER_VALIDATION_YEARS = [2021, 2022, 2023]
ALPHA_GRID = [0.0, 0.1, 1.0, 10.0, 100.0]
GRAPH_END_YEAR = 2035
LONG_HORIZON_END_YEAR = 2100


@dataclass
class RidgeModel:
    feature_columns: list[str]
    alpha: float
    intercept: float
    coefficients: np.ndarray
    feature_means: np.ndarray
    feature_scales: np.ndarray

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        values = frame[self.feature_columns].to_numpy(dtype=float)
        predictions = self.intercept + values @ self.coefficients
        return np.clip(predictions, 0.0, None)


def ensure_dirs() -> None:
    for path in [WORKSPACE_DIR, INPUTS_DIR, OUTPUTS_DIR, REPORTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def sync_inputs() -> dict[str, str]:
    copied: dict[str, str] = {}
    for name, source_path in SOURCE_FILES.items():
        destination = INPUTS_DIR / name
        copy_file(source_path, destination)
        copied[name] = str(destination)
    return copied


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    observed = pd.read_csv(INPUTS_DIR / "model_c_observed_reference_yearly.csv", encoding="utf-8-sig")
    calibration = pd.read_csv(
        INPUTS_DIR / "model_c_scenario_calibration_table.csv",
        encoding="utf-8-sig",
    )
    projection = pd.read_csv(
        INPUTS_DIR / "model_c_scenario_projection_table.csv",
        encoding="utf-8-sig",
    )
    for frame in [observed, calibration, projection]:
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype(int)
    return observed, calibration, projection


def add_modeling_columns(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["scenario_family"] = data["scenario_family"].astype(str)
    data["scenario_is_high_emissions"] = (data["scenario_family"] == "high_emissions").astype(float)
    return data


def weighted_rmse(y_true: np.ndarray, y_pred: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sqrt(np.sum(weights * (y_true - y_pred) ** 2) / np.sum(weights)))


def weighted_mae(y_true: np.ndarray, y_pred: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(weights * np.abs(y_true - y_pred)) / np.sum(weights))


def weighted_bias(y_true: np.ndarray, y_pred: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(weights * (y_pred - y_true)) / np.sum(weights))


def weighted_mape(y_true: np.ndarray, y_pred: np.ndarray, weights: np.ndarray) -> float:
    non_zero = np.abs(y_true) > 1e-9
    if not np.any(non_zero):
        return float("nan")
    local_true = y_true[non_zero]
    local_pred = y_pred[non_zero]
    local_weights = weights[non_zero]
    return float(
        100.0
        * np.sum(local_weights * np.abs((local_true - local_pred) / local_true))
        / np.sum(local_weights)
    )


def fit_ridge_model(
    frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    alpha: float,
    sample_weight: np.ndarray,
) -> RidgeModel:
    features = frame[feature_columns].to_numpy(dtype=float)
    target = frame[target_column].to_numpy(dtype=float)
    weights = np.asarray(sample_weight, dtype=float)

    feature_means = np.average(features, axis=0, weights=weights)
    centered = features - feature_means
    feature_scales = np.sqrt(np.average(centered**2, axis=0, weights=weights))
    feature_scales = np.where(feature_scales > 1e-12, feature_scales, 1.0)
    standardized = centered / feature_scales

    target_mean = np.average(target, weights=weights)
    centered_target = target - target_mean

    sqrt_weights = np.sqrt(weights)[:, None]
    x_weighted = standardized * sqrt_weights
    y_weighted = centered_target * np.sqrt(weights)

    gram = x_weighted.T @ x_weighted
    penalty = alpha * np.eye(gram.shape[0])
    beta_scaled = np.linalg.pinv(gram + penalty) @ (x_weighted.T @ y_weighted)
    coefficients = beta_scaled / feature_scales
    intercept = float(target_mean - feature_means @ coefficients)

    return RidgeModel(
        feature_columns=feature_columns,
        alpha=float(alpha),
        intercept=intercept,
        coefficients=coefficients.astype(float),
        feature_means=feature_means.astype(float),
        feature_scales=feature_scales.astype(float),
    )


def build_model_frame(
    calibration: pd.DataFrame,
    target_spec: dict[str, str],
) -> tuple[pd.DataFrame, list[str]]:
    feature_columns = (
        CLIMATE_FEATURE_COLUMNS
        + SCENARIO_FEATURE_COLUMNS
        + [target_spec["lag_1_column"], target_spec["rolling_3_column"]]
    )
    target_column = target_spec["target_column"]
    keep_columns = ["scenario_family", "year", target_column] + feature_columns
    frame = calibration[keep_columns].copy()
    frame = frame.dropna(subset=feature_columns + [target_column]).reset_index(drop=True)
    year_counts = frame.groupby("year")["scenario_family"].transform("count")
    frame["sample_weight"] = 1.0 / year_counts.astype(float)
    frame["split_role"] = np.where(
        frame["year"].isin(FINAL_VALIDATION_YEARS),
        "final_validation",
        "training_candidate",
    )
    return frame, feature_columns


def select_alpha(
    frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
) -> tuple[float, pd.DataFrame]:
    training_candidates = frame[frame["split_role"] == "training_candidate"].copy()
    scored_rows: list[dict[str, object]] = []

    for alpha in ALPHA_GRID:
        fold_rmses: list[float] = []
        for validation_year in INNER_VALIDATION_YEARS:
            fold_train = training_candidates[training_candidates["year"] < validation_year].copy()
            fold_validate = training_candidates[training_candidates["year"] == validation_year].copy()
            if fold_train.empty or fold_validate.empty:
                continue
            model = fit_ridge_model(
                fold_train,
                feature_columns,
                target_column,
                alpha=alpha,
                sample_weight=fold_train["sample_weight"].to_numpy(dtype=float),
            )
            predictions = model.predict(fold_validate)
            fold_rmse = weighted_rmse(
                fold_validate[target_column].to_numpy(dtype=float),
                predictions,
                fold_validate["sample_weight"].to_numpy(dtype=float),
            )
            fold_rmses.append(fold_rmse)
            scored_rows.append(
                {
                    "alpha": alpha,
                    "validation_year": validation_year,
                    "fold_rmse": fold_rmse,
                }
            )
        if not fold_rmses:
            scored_rows.append(
                {
                    "alpha": alpha,
                    "validation_year": "no_fold",
                    "fold_rmse": math.nan,
                }
            )

    scoring = pd.DataFrame(scored_rows)
    alpha_summary = (
        scoring[pd.to_numeric(scoring["validation_year"], errors="coerce").notna()]
        .groupby("alpha", as_index=False)["fold_rmse"]
        .mean()
        .rename(columns={"fold_rmse": "mean_fold_rmse"})
        .sort_values(["mean_fold_rmse", "alpha"], ascending=[True, True])
        .reset_index(drop=True)
    )
    selected_alpha = float(alpha_summary.iloc[0]["alpha"]) if not alpha_summary.empty else 0.0
    scoring = scoring.merge(alpha_summary, on="alpha", how="left")
    return selected_alpha, scoring


def recursive_predict_years(
    *,
    model: RidgeModel,
    target_spec: dict[str, str],
    base_history: dict[int, float],
    scenario_rows: pd.DataFrame,
    start_year: int,
    end_year: int,
    output_role: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    scenario_name = str(scenario_rows["scenario_family"].iloc[0])
    history = dict(base_history)

    for year in range(start_year, end_year + 1):
        current = scenario_rows[scenario_rows["year"] == year].copy()
        if current.empty:
            continue
        if (year - 1) not in history or (year - 2) not in history or (year - 3) not in history:
            raise ValueError(
                f"Missing recursive target history for year {year} in scenario {scenario_name}."
            )
        current[target_spec["lag_1_column"]] = history[year - 1]
        current[target_spec["rolling_3_column"]] = np.mean(
            [history[year - 1], history[year - 2], history[year - 3]]
        )
        prediction = float(model.predict(current)[0])
        history[year] = prediction
        rows.append(
            {
                "scenario_family": scenario_name,
                "year": year,
                "target_column": target_spec["target_column"],
                "target_label": target_spec["target_label"],
                "predicted_prevalence_per_100k": prediction,
                "lag_1_used": float(current[target_spec["lag_1_column"]].iloc[0]),
                "rolling_3_used": float(current[target_spec["rolling_3_column"]].iloc[0]),
                "table_role": output_role,
            }
        )
    return pd.DataFrame(rows)


def build_validation_predictions(
    *,
    calibration: pd.DataFrame,
    model: RidgeModel,
    target_spec: dict[str, str],
) -> pd.DataFrame:
    validation_rows = calibration[calibration["year"].isin(FINAL_VALIDATION_YEARS)].copy()
    observed_history = (
        calibration[["year", target_spec["target_column"]]]
        .drop_duplicates(subset=["year"])
        .sort_values("year")
    )
    base_history = {
        int(row.year): float(getattr(row, target_spec["target_column"]))
        for row in observed_history.itertuples(index=False)
        if int(row.year) < min(FINAL_VALIDATION_YEARS)
    }

    prediction_rows: list[pd.DataFrame] = []
    for _, scenario_frame in validation_rows.groupby("scenario_family", sort=True):
        recursive = recursive_predict_years(
            model=model,
            target_spec=target_spec,
            base_history=base_history,
            scenario_rows=scenario_frame.sort_values("year").reset_index(drop=True),
            start_year=min(FINAL_VALIDATION_YEARS),
            end_year=max(FINAL_VALIDATION_YEARS),
            output_role="final_validation_recursive",
        )
        truth = scenario_frame[
            ["scenario_family", "year", target_spec["target_column"], "sample_weight"]
        ].copy()
        truth = truth.rename(columns={target_spec["target_column"]: "observed_prevalence_per_100k"})
        merged = recursive.merge(truth, on=["scenario_family", "year"], how="left")
        merged["residual"] = (
            merged["predicted_prevalence_per_100k"] - merged["observed_prevalence_per_100k"]
        )
        prediction_rows.append(merged)

    return pd.concat(prediction_rows, ignore_index=True)


def build_future_projection_predictions(
    *,
    observed_reference: pd.DataFrame,
    projection: pd.DataFrame,
    model: RidgeModel,
    target_spec: dict[str, str],
) -> pd.DataFrame:
    observed_history = (
        observed_reference[["year", target_spec["target_column"]]]
        .drop_duplicates(subset=["year"])
        .sort_values("year")
    )
    base_history = {
        int(row.year): float(getattr(row, target_spec["target_column"]))
        for row in observed_history.itertuples(index=False)
    }

    prediction_rows: list[pd.DataFrame] = []
    for _, scenario_frame in projection.groupby("scenario_family", sort=True):
        recursive = recursive_predict_years(
            model=model,
            target_spec=target_spec,
            base_history=base_history,
            scenario_rows=scenario_frame.sort_values("year").reset_index(drop=True),
            start_year=2026,
            end_year=LONG_HORIZON_END_YEAR,
            output_role="scenario_projection_recursive",
        )
        prediction_rows.append(recursive)
    return pd.concat(prediction_rows, ignore_index=True)


def build_graph_tables(
    *,
    observed_reference: pd.DataFrame,
    future_predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenario_families = sorted(future_predictions["scenario_family"].dropna().unique())
    historical_rows: list[dict[str, object]] = []

    for model_name, target_spec in TARGET_SPECS.items():
        history = observed_reference[["year", target_spec["target_column"]]].copy()
        for scenario_family in scenario_families:
            for row in history.itertuples(index=False):
                historical_rows.append(
                    {
                        "model_name": model_name,
                        "target_column": target_spec["target_column"],
                        "target_label": target_spec["target_label"],
                        "scenario_family": scenario_family,
                        "year": int(row.year),
                        "prevalence_per_100k": float(getattr(row, target_spec["target_column"])),
                        "series_role": "observed_history",
                    }
                )

    historical = pd.DataFrame(historical_rows)
    predicted = future_predictions.rename(
        columns={"predicted_prevalence_per_100k": "prevalence_per_100k"}
    ).copy()
    predicted["model_name"] = predicted["target_column"].map(
        {
            spec["target_column"]: model_name
            for model_name, spec in TARGET_SPECS.items()
        }
    )
    predicted["series_role"] = "predicted_future"
    predicted = predicted[
        [
            "model_name",
            "target_column",
            "target_label",
            "scenario_family",
            "year",
            "prevalence_per_100k",
            "series_role",
        ]
    ]

    graph_long = (
        pd.concat([historical, predicted], ignore_index=True)
        .sort_values(["model_name", "scenario_family", "year", "series_role"])
        .reset_index(drop=True)
    )
    graph_10y = graph_long[graph_long["year"] <= GRAPH_END_YEAR].copy()
    return graph_10y, graph_long


def build_coefficients_table(
    *,
    model_name: str,
    model: RidgeModel,
    target_label: str,
) -> pd.DataFrame:
    rows = []
    for feature_name, coefficient in zip(model.feature_columns, model.coefficients):
        rows.append(
            {
                "model_name": model_name,
                "target_label": target_label,
                "alpha": model.alpha,
                "feature_name": feature_name,
                "coefficient": float(coefficient),
                "coefficient_abs": abs(float(coefficient)),
            }
        )
    return pd.DataFrame(rows).sort_values("coefficient_abs", ascending=False).reset_index(drop=True)


def build_metric_rows(
    *,
    model_name: str,
    target_label: str,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    weights = predictions["sample_weight"].to_numpy(dtype=float)
    observed = predictions["observed_prevalence_per_100k"].to_numpy(dtype=float)
    predicted = predictions["predicted_prevalence_per_100k"].to_numpy(dtype=float)
    rows = [
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "weighted_rmse",
            "metric_value": weighted_rmse(observed, predicted, weights),
        },
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "weighted_mae",
            "metric_value": weighted_mae(observed, predicted, weights),
        },
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "weighted_bias",
            "metric_value": weighted_bias(observed, predicted, weights),
        },
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "weighted_mape_pct",
            "metric_value": weighted_mape(observed, predicted, weights),
        },
    ]
    return pd.DataFrame(rows)


def write_workspace_docs() -> None:
    readme = """# Model C Climate-Effect Modeling

This folder is the dedicated modeling workspace for Model C.

Model C goal:

- fit Slovenia-level yearly prevalence models for Lyme, KME, and combined tick-borne disease
- use Copernicus climate-scenario covariates rather than short-range weather forecasts
- produce graph-ready future prevalence trajectories, especially for the next 10 years

This workspace stays downstream of:

- `../data processing - copernicus_forecast_data/outputs/model_c/`

It does not modify the upstream processing outputs.

## Workflow

1. copy the processed Model C calibration, projection, and observed-reference tables into `inputs/`
2. reserve the last two observed years, 2024 and 2025, as grouped final validation years
3. fit three separate prevalence models:
   - Lyme prevalence per 100k
   - KME prevalence per 100k
   - combined tick-borne prevalence per 100k
4. run recursive future projections by scenario family
5. write graph-ready tables into `outputs/`

## Main Command

```powershell
py -3 scripts/run_model_c_climate_modeling.py
```
"""
    methodology = """# Model C Methodology

## Why Reserve Validation Data

Yes, Model C needs reserved validation data before final fitting.

The yearly observed window is short, only 2016-2025, and the calibration table contains
two scenario-family rows per observed year. Because of that:

- validation must be reserved by calendar year, not by individual row
- otherwise the same observed target year would leak into both train and validation

## Validation Design

- final validation years: 2024 and 2025
- grouped rule: both scenario-family rows for a held-out year stay together in validation
- validation mode: recursive, so 2025 predictions depend on the 2024 prediction rather
  than the observed 2024 target

This is closer to the real future rollout.

## First-Pass Feature Block

The first-pass Model C prevalence models use a compact feature set to avoid overfitting:

- yearly climate temperature mean
- yearly climate near-surface specific humidity
- yearly climate precipitation proxy
- yearly climate upper-soil moisture proxy
- scenario-family indicator
- target lag 1 year
- target rolling mean over the previous 3 years

The longer lag block already exists in the calibration table, but the compact block is
safer for the first fit because the observed window is small.

## Output Style

The model output focus is prevalence per 100k, because the requested downstream product
is a graphable past-to-future disease-prevalence trajectory.
"""
    inputs_readme = """# Inputs

These files are copied from the processed Model C workspace so the modeling step is
reproducible in one place.
"""
    outputs_readme = """# Outputs

This folder stores validation predictions, future projections, coefficients, metrics,
and graph-ready prevalence tables.
"""
    reports_readme = """# Reports

This folder stores human-readable summaries of the validation design, fitted models, and
projection outputs.
"""

    (WORKSPACE_DIR / "README.md").write_text(readme.strip() + "\n", encoding="utf-8")
    (WORKSPACE_DIR / "METHODOLOGY.md").write_text(methodology.strip() + "\n", encoding="utf-8")
    (INPUTS_DIR / "README.md").write_text(inputs_readme.strip() + "\n", encoding="utf-8")
    (OUTPUTS_DIR / "README.md").write_text(outputs_readme.strip() + "\n", encoding="utf-8")
    (REPORTS_DIR / "README.md").write_text(reports_readme.strip() + "\n", encoding="utf-8")


def write_report(
    *,
    split_table: pd.DataFrame,
    alpha_scores: pd.DataFrame,
    metrics: pd.DataFrame,
    future_predictions: pd.DataFrame,
) -> None:
    lines = [
        "# Model C Climate-Effect Modeling Report",
        "",
        f"- generated at: `{timestamp_utc()}`",
        "",
        "## Validation Design",
        "",
        "- final validation years are `2024` and `2025`",
        "- both scenario-family rows for the same calendar year stay in the same split",
        "- validation is recursive across the held-out years",
        "",
        "## Split Summary",
        "",
    ]

    for row in split_table.itertuples(index=False):
        lines.append(
            f"- {row.model_name}: training years `{row.training_years}`; final validation years `{row.final_validation_years}`"
        )

    lines.extend(["", "## Alpha Selection", ""])
    for row in alpha_scores.itertuples(index=False):
        lines.append(
            f"- {row.model_name}: selected alpha `{row.selected_alpha}` from mean inner-fold RMSE `{row.selected_alpha_mean_fold_rmse:.4f}`"
        )

    lines.extend(["", "## Final Validation Metrics", ""])
    for row in metrics.itertuples(index=False):
        metric_value = "nan" if pd.isna(row.metric_value) else f"{row.metric_value:.4f}"
        lines.append(f"- {row.model_name} {row.metric_name}: `{metric_value}`")

    lines.extend(["", "## Future Coverage", ""])
    coverage = (
        future_predictions.groupby(["model_name", "scenario_family"], as_index=False)
        .agg(min_year=("year", "min"), max_year=("year", "max"), row_count=("year", "count"))
        .sort_values(["model_name", "scenario_family"])
    )
    for row in coverage.itertuples(index=False):
        lines.append(
            f"- {row.model_name} / {row.scenario_family}: `{row.min_year}` to `{row.max_year}` with `{row.row_count}` projected yearly points"
        )

    (REPORTS_DIR / "model_c_climate_modeling_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ensure_dirs()
    write_workspace_docs()
    copied_inputs = sync_inputs()

    observed_reference, calibration_raw, projection_raw = load_inputs()
    calibration = add_modeling_columns(calibration_raw)
    projection = add_modeling_columns(projection_raw)

    split_rows: list[dict[str, object]] = []
    alpha_rows: list[dict[str, object]] = []
    coefficients_frames: list[pd.DataFrame] = []
    metrics_frames: list[pd.DataFrame] = []
    validation_frames: list[pd.DataFrame] = []
    future_frames: list[pd.DataFrame] = []

    for model_name, target_spec in TARGET_SPECS.items():
        model_frame, feature_columns = build_model_frame(calibration, target_spec)
        selected_alpha, alpha_scoring = select_alpha(
            model_frame,
            feature_columns,
            target_spec["target_column"],
        )

        training_frame = model_frame[model_frame["split_role"] == "training_candidate"].copy()
        final_model = fit_ridge_model(
            training_frame,
            feature_columns,
            target_spec["target_column"],
            alpha=selected_alpha,
            sample_weight=training_frame["sample_weight"].to_numpy(dtype=float),
        )

        validation_predictions = build_validation_predictions(
            calibration=model_frame,
            model=final_model,
            target_spec=target_spec,
        )
        validation_predictions["model_name"] = model_name
        validation_frames.append(validation_predictions)

        future_predictions = build_future_projection_predictions(
            observed_reference=observed_reference,
            projection=projection,
            model=final_model,
            target_spec=target_spec,
        )
        future_predictions["model_name"] = model_name
        future_frames.append(future_predictions)

        split_rows.append(
            {
                "model_name": model_name,
                "training_years": ", ".join(
                    str(year)
                    for year in sorted(training_frame["year"].dropna().astype(int).unique())
                ),
                "final_validation_years": ", ".join(str(year) for year in FINAL_VALIDATION_YEARS),
                "effective_training_row_count": int(len(training_frame)),
                "effective_validation_row_count": int(len(validation_predictions)),
            }
        )

        mean_alpha_scores = (
            alpha_scoring[pd.to_numeric(alpha_scoring["validation_year"], errors="coerce").notna()]
            .groupby("alpha", as_index=False)["fold_rmse"]
            .mean()
            .sort_values(["fold_rmse", "alpha"], ascending=[True, True])
            .reset_index(drop=True)
        )
        selected_mean_rmse = (
            float(mean_alpha_scores.loc[mean_alpha_scores["alpha"] == selected_alpha, "fold_rmse"].iloc[0])
            if not mean_alpha_scores.empty
            else math.nan
        )
        alpha_rows.append(
            {
                "model_name": model_name,
                "selected_alpha": selected_alpha,
                "selected_alpha_mean_fold_rmse": selected_mean_rmse,
            }
        )

        alpha_scoring.insert(0, "model_name", model_name)
        alpha_scoring.to_csv(
            OUTPUTS_DIR / f"{model_name}_alpha_scoring.csv",
            index=False,
            encoding="utf-8-sig",
        )

        coefficients_frames.append(
            build_coefficients_table(
                model_name=model_name,
                model=final_model,
                target_label=target_spec["target_label"],
            )
        )
        metrics_frames.append(
            build_metric_rows(
                model_name=model_name,
                target_label=target_spec["target_label"],
                predictions=validation_predictions,
            )
        )

    split_table = pd.DataFrame(split_rows)
    alpha_summary = pd.DataFrame(alpha_rows)
    coefficients = pd.concat(coefficients_frames, ignore_index=True)
    metrics = pd.concat(metrics_frames, ignore_index=True)
    validation_predictions = pd.concat(validation_frames, ignore_index=True)
    future_predictions = pd.concat(future_frames, ignore_index=True)

    graph_10y, graph_long = build_graph_tables(
        observed_reference=observed_reference,
        future_predictions=future_predictions,
    )
    future_predictions_10y = future_predictions[future_predictions["year"] <= GRAPH_END_YEAR].copy()

    split_table.to_csv(OUTPUTS_DIR / "model_c_validation_split_summary.csv", index=False, encoding="utf-8-sig")
    alpha_summary.to_csv(OUTPUTS_DIR / "model_c_alpha_selection_summary.csv", index=False, encoding="utf-8-sig")
    coefficients.to_csv(OUTPUTS_DIR / "model_c_model_coefficients.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(OUTPUTS_DIR / "model_c_final_validation_metrics.csv", index=False, encoding="utf-8-sig")
    validation_predictions.to_csv(
        OUTPUTS_DIR / "model_c_final_validation_predictions.csv",
        index=False,
        encoding="utf-8-sig",
    )
    future_predictions_10y.to_csv(
        OUTPUTS_DIR / "model_c_future_projection_10y.csv",
        index=False,
        encoding="utf-8-sig",
    )
    future_predictions.to_csv(
        OUTPUTS_DIR / "model_c_future_projection_long.csv",
        index=False,
        encoding="utf-8-sig",
    )
    graph_10y.to_csv(OUTPUTS_DIR / "model_c_graph_prevalence_10y.csv", index=False, encoding="utf-8-sig")
    graph_long.to_csv(OUTPUTS_DIR / "model_c_graph_prevalence_long.csv", index=False, encoding="utf-8-sig")

    write_json(
        OUTPUTS_DIR / "model_c_climate_modeling_manifest.json",
        {
            "generated_at": timestamp_utc(),
            "workspace_dir": str(WORKSPACE_DIR),
            "copied_inputs": copied_inputs,
            "final_validation_years": FINAL_VALIDATION_YEARS,
            "inner_validation_years": INNER_VALIDATION_YEARS,
            "graph_end_year": GRAPH_END_YEAR,
            "long_horizon_end_year": LONG_HORIZON_END_YEAR,
            "models": {
                row["model_name"]: {
                    "selected_alpha": float(
                        alpha_summary.loc[
                            alpha_summary["model_name"] == row["model_name"],
                            "selected_alpha",
                        ].iloc[0]
                    ),
                    "training_years": row["training_years"],
                    "final_validation_years": row["final_validation_years"],
                }
                for row in split_rows
            },
        },
    )

    write_report(
        split_table=split_table,
        alpha_scores=alpha_summary,
        metrics=metrics,
        future_predictions=future_predictions,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
