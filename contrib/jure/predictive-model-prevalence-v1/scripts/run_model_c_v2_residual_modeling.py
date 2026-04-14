from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pipeline_utils import PROJECT_ROOT, copy_file, timestamp_utc, write_json


WORKSPACE_DIR = PROJECT_ROOT / "modeling - model_c_v2_residual_climate"
INPUTS_DIR = WORKSPACE_DIR / "inputs"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
REPORTS_DIR = WORKSPACE_DIR / "reports"

OBSERVED_SOURCE = (
    PROJECT_ROOT
    / "data processing - copernicus_forecast_data"
    / "outputs"
    / "model_c"
    / "model_c_observed_reference_yearly.csv"
)
CALIBRATION_SOURCE = (
    PROJECT_ROOT
    / "data processing - copernicus_forecast_data"
    / "outputs"
    / "model_c"
    / "model_c_scenario_calibration_table.csv"
)
PROJECTION_SOURCE = (
    PROJECT_ROOT
    / "data processing - copernicus_forecast_data"
    / "outputs"
    / "model_c"
    / "model_c_scenario_projection_table.csv"
)

ANOMALY_COLUMNS = [
    "air_temperature_c_mean_climate_anomaly_vs_2016_2025",
    "near_surface_specific_humidity_g_kg_climate_anomaly_vs_2016_2025",
    "precipitation_sum_mm_proxy_climate_anomaly_vs_2016_2025",
    "soil_moisture_upper_portion_kg_m2_climate_anomaly_vs_2016_2025",
]

TARGET_SPECS = {
    "lyme_prevalence": {
        "target_column": "lyme_cases_per_100k",
        "target_label": "Lyme prevalence per 100k",
        "baseline_strategy": "lag1",
    },
    "kme_prevalence": {
        "target_column": "kme_cases_per_100k",
        "target_label": "KME prevalence per 100k",
        "baseline_strategy": "rolling3",
    },
    "combined_prevalence": {
        "target_column": "tick_borne_cases_total_per_100k",
        "target_label": "Combined tick-borne prevalence per 100k",
        "baseline_strategy": "lag1",
    },
}

FINAL_VALIDATION_YEARS = [2024, 2025]
INNER_VALIDATION_YEARS = [2022, 2023]
ALPHA_GRID = [0.1, 1.0, 10.0, 100.0, 1000.0]
GRAPH_END_YEAR = 2035
LONG_END_YEAR = 2100


@dataclass
class RidgeModel:
    feature_columns: list[str]
    alpha: float
    intercept: float
    coefficients: np.ndarray
    feature_means: np.ndarray
    feature_scales: np.ndarray

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        x = frame[self.feature_columns].to_numpy(dtype=float)
        standardized = (x - self.feature_means) / self.feature_scales
        return self.intercept + standardized @ self.coefficients


def ensure_dirs() -> None:
    for path in [WORKSPACE_DIR, INPUTS_DIR, OUTPUTS_DIR, REPORTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def write_workspace_docs() -> None:
    readme = """# Model C V2 Residual Climate Modeling

This workspace contains the Version 2 yearly climate-effect branch.

Key changes from V1:

- training uses one collapsed historical climate row per calendar year
- the model predicts climate adjustment around a prevalence baseline
- future scenario paths are driven by climate anomaly indices rather than raw duplicated scenario calibration rows

## Main Commands

```powershell
py -3 scripts/run_model_c_v2_residual_modeling.py
py -3 scripts/generate_model_c_v2_presentation_graphs.py
```
"""
    methodology = """# Model C V2 Methodology

## Core Idea

Model C V1 was too close to a direct regression on duplicated scenario-family rows.
Model C V2 changes that:

1. collapse historical scenario rows to one climate-analogue row per year
2. define a baseline prevalence trajectory
3. predict only the climate-driven adjustment around that baseline

## Baseline Strategy

- Lyme: lag-1 yearly prevalence
- Combined: lag-1 yearly prevalence
- KME: rolling 3-year prevalence mean

## Climate Feature Compression

The model uses two compact indices:

- thermal_humidity_index
- wetness_index

These are built from standardized climate anomaly columns using the historical
collapsed years only.
"""
    (WORKSPACE_DIR / "README.md").write_text(readme, encoding="utf-8")
    (WORKSPACE_DIR / "METHODOLOGY.md").write_text(methodology, encoding="utf-8")
    (INPUTS_DIR / "README.md").write_text("# Inputs\n\nCopied Model C source tables for V2.\n", encoding="utf-8")
    (OUTPUTS_DIR / "README.md").write_text("# Outputs\n\nValidation, projections, graph tables, and metadata.\n", encoding="utf-8")
    (REPORTS_DIR / "README.md").write_text("# Reports\n\nHuman-readable summaries for Model C V2.\n", encoding="utf-8")


def sync_inputs() -> dict[str, str]:
    copied = {}
    for source in [OBSERVED_SOURCE, CALIBRATION_SOURCE, PROJECTION_SOURCE]:
        destination = INPUTS_DIR / source.name
        copy_file(source, destination)
        copied[source.name] = str(destination)
    return copied


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    observed = pd.read_csv(INPUTS_DIR / OBSERVED_SOURCE.name, encoding="utf-8-sig")
    calibration = pd.read_csv(INPUTS_DIR / CALIBRATION_SOURCE.name, encoding="utf-8-sig")
    projection = pd.read_csv(INPUTS_DIR / PROJECTION_SOURCE.name, encoding="utf-8-sig")
    for frame in [observed, calibration, projection]:
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype(int)
    return observed, calibration, projection


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def bias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(y_pred - y_true))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    non_zero = np.abs(y_true) > 1e-9
    if not np.any(non_zero):
        return float("nan")
    return float(100.0 * np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])))


def fit_ridge(
    frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    alpha: float,
) -> RidgeModel:
    x = frame[feature_columns].to_numpy(dtype=float)
    y = frame[target_column].to_numpy(dtype=float)
    feature_means = x.mean(axis=0)
    centered = x - feature_means
    feature_scales = centered.std(axis=0)
    feature_scales = np.where(feature_scales > 1e-12, feature_scales, 1.0)
    standardized = centered / feature_scales
    y_mean = float(y.mean())
    y_centered = y - y_mean
    gram = standardized.T @ standardized
    beta = np.linalg.pinv(gram + alpha * np.eye(gram.shape[0])) @ (standardized.T @ y_centered)
    return RidgeModel(
        feature_columns=feature_columns,
        alpha=float(alpha),
        intercept=y_mean,
        coefficients=np.asarray(beta, dtype=float),
        feature_means=np.asarray(feature_means, dtype=float),
        feature_scales=np.asarray(feature_scales, dtype=float),
    )


def collapse_historical_calibration(calibration: pd.DataFrame, observed: pd.DataFrame) -> pd.DataFrame:
    climate = (
        calibration.groupby("year", as_index=False)[ANOMALY_COLUMNS]
        .mean()
        .sort_values("year")
        .reset_index(drop=True)
    )
    target_columns = [
        "lyme_cases_per_100k",
        "kme_cases_per_100k",
        "tick_borne_cases_total_per_100k",
    ]
    observed_targets = observed[["year", *target_columns]].copy()
    collapsed = climate.merge(observed_targets, on="year", how="left")
    return collapsed


def add_compact_indices(
    historical: pd.DataFrame,
    projection: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, float]]]:
    stats: dict[str, dict[str, float]] = {}
    historical = historical.copy()
    projection = projection.copy()

    for column in ANOMALY_COLUMNS:
        mean_value = float(historical[column].mean())
        std_value = float(historical[column].std())
        if abs(std_value) < 1e-12:
            std_value = 1.0
        stats[column] = {"mean": mean_value, "std": std_value}
        historical[f"{column}_z"] = (historical[column] - mean_value) / std_value
        projection[f"{column}_z"] = (projection[column] - mean_value) / std_value

    historical["thermal_humidity_index"] = (
        historical["air_temperature_c_mean_climate_anomaly_vs_2016_2025_z"]
        + historical["near_surface_specific_humidity_g_kg_climate_anomaly_vs_2016_2025_z"]
    )
    historical["wetness_index"] = (
        historical["precipitation_sum_mm_proxy_climate_anomaly_vs_2016_2025_z"]
        + historical["soil_moisture_upper_portion_kg_m2_climate_anomaly_vs_2016_2025_z"]
    )

    projection["thermal_humidity_index"] = (
        projection["air_temperature_c_mean_climate_anomaly_vs_2016_2025_z"]
        + projection["near_surface_specific_humidity_g_kg_climate_anomaly_vs_2016_2025_z"]
    )
    projection["wetness_index"] = (
        projection["precipitation_sum_mm_proxy_climate_anomaly_vs_2016_2025_z"]
        + projection["soil_moisture_upper_portion_kg_m2_climate_anomaly_vs_2016_2025_z"]
    )
    return historical, projection, stats


def baseline_and_momentum(
    history: dict[int, float],
    year: int,
    strategy: str,
) -> tuple[float, float]:
    if strategy == "lag1":
        baseline = history[year - 1]
        rolling3 = np.mean([history[year - 1], history[year - 2], history[year - 3]])
        momentum = history[year - 1] - rolling3
        return float(baseline), float(momentum)
    if strategy == "rolling3":
        baseline = np.mean([history[year - 1], history[year - 2], history[year - 3]])
        momentum = history[year - 1] - baseline
        return float(baseline), float(momentum)
    raise ValueError(f"Unsupported strategy: {strategy}")


def build_training_frame(
    historical: pd.DataFrame,
    target_spec: dict[str, str],
) -> tuple[pd.DataFrame, list[str]]:
    data = historical.copy().sort_values("year").reset_index(drop=True)
    target_column = target_spec["target_column"]
    strategy = target_spec["baseline_strategy"]
    rows: list[dict[str, object]] = []

    history: dict[int, float] = {
        int(row.year): float(getattr(row, target_column))
        for row in data.itertuples(index=False)
    }

    for row in data.itertuples(index=False):
        year = int(row.year)
        if (year - 1) not in history or (year - 2) not in history or (year - 3) not in history:
            continue
        baseline, momentum = baseline_and_momentum(history, year, strategy)
        observed = float(getattr(row, target_column))
        rows.append(
            {
                "year": year,
                "target_column": target_column,
                "baseline_prevalence_per_100k": baseline,
                "recent_momentum": momentum,
                "thermal_humidity_index": float(row.thermal_humidity_index),
                "wetness_index": float(row.wetness_index),
                target_column: observed,
                "residual_target": observed - baseline,
            }
        )

    frame = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    feature_columns = [
        "baseline_prevalence_per_100k",
        "recent_momentum",
        "thermal_humidity_index",
        "wetness_index",
    ]
    return frame, feature_columns


def make_recursive_features(
    *,
    year: int,
    climate_row: pd.Series,
    history: dict[int, float],
    strategy: str,
) -> dict[str, float]:
    baseline, momentum = baseline_and_momentum(history, year, strategy)
    return {
        "year": year,
        "baseline_prevalence_per_100k": baseline,
        "recent_momentum": momentum,
        "thermal_humidity_index": float(climate_row["thermal_humidity_index"]),
        "wetness_index": float(climate_row["wetness_index"]),
    }


def select_alpha(
    training_frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
) -> tuple[float, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    trainable = training_frame[training_frame["year"] < min(FINAL_VALIDATION_YEARS)].copy()

    for alpha in ALPHA_GRID:
        fold_scores = []
        for validation_year in INNER_VALIDATION_YEARS:
            fold_train = trainable[trainable["year"] < validation_year].copy()
            fold_validate = trainable[trainable["year"] == validation_year].copy()
            if fold_train.empty or fold_validate.empty:
                continue
            model = fit_ridge(fold_train, feature_columns, "residual_target", alpha=alpha)
            predicted = np.clip(
                fold_validate["baseline_prevalence_per_100k"].to_numpy(dtype=float)
                + model.predict(fold_validate),
                0.0,
                None,
            )
            score = rmse(fold_validate[target_column].to_numpy(dtype=float), predicted)
            fold_scores.append(score)
            rows.append({"alpha": alpha, "validation_year": validation_year, "fold_rmse": score})
        if not fold_scores:
            rows.append({"alpha": alpha, "validation_year": "no_fold", "fold_rmse": math.nan})

    scoring = pd.DataFrame(rows)
    alpha_summary = (
        scoring[pd.to_numeric(scoring["validation_year"], errors="coerce").notna()]
        .groupby("alpha", as_index=False)["fold_rmse"]
        .mean()
        .rename(columns={"fold_rmse": "mean_fold_rmse"})
        .sort_values(["mean_fold_rmse", "alpha"], ascending=[True, True])
        .reset_index(drop=True)
    )
    selected_alpha = float(alpha_summary.iloc[0]["alpha"]) if not alpha_summary.empty else ALPHA_GRID[-1]
    return selected_alpha, scoring.merge(alpha_summary, on="alpha", how="left")


def recursive_predict_years(
    *,
    model: RidgeModel,
    climate_rows: pd.DataFrame,
    target_spec: dict[str, str],
    observed_history: dict[int, float],
    start_year: int,
    end_year: int,
    scenario_family: str,
    table_role: str,
) -> pd.DataFrame:
    history = dict(observed_history)
    rows: list[dict[str, object]] = []
    strategy = target_spec["baseline_strategy"]

    for year in range(start_year, end_year + 1):
        climate_row = climate_rows[climate_rows["year"] == year]
        if climate_row.empty:
            continue
        feature_row = make_recursive_features(
            year=year,
            climate_row=climate_row.iloc[0],
            history=history,
            strategy=strategy,
        )
        feature_df = pd.DataFrame([feature_row])
        predicted_residual = float(model.predict(feature_df)[0])
        prediction = max(0.0, feature_row["baseline_prevalence_per_100k"] + predicted_residual)
        history[year] = prediction
        rows.append(
            {
                "scenario_family": scenario_family,
                "year": year,
                "target_column": target_spec["target_column"],
                "target_label": target_spec["target_label"],
                "baseline_prevalence_per_100k": feature_row["baseline_prevalence_per_100k"],
                "recent_momentum": feature_row["recent_momentum"],
                "predicted_residual": predicted_residual,
                "predicted_prevalence_per_100k": prediction,
                "table_role": table_role,
            }
        )
    return pd.DataFrame(rows)


def build_validation_predictions(
    *,
    historical: pd.DataFrame,
    model: RidgeModel,
    target_spec: dict[str, str],
) -> pd.DataFrame:
    observed_history = {
        int(row.year): float(getattr(row, target_spec["target_column"]))
        for row in historical.itertuples(index=False)
        if int(row.year) < min(FINAL_VALIDATION_YEARS)
    }
    validation_rows = recursive_predict_years(
        model=model,
        climate_rows=historical,
        target_spec=target_spec,
        observed_history=observed_history,
        start_year=min(FINAL_VALIDATION_YEARS),
        end_year=max(FINAL_VALIDATION_YEARS),
        scenario_family="collapsed_historical",
        table_role="final_validation_recursive",
    )
    truth = historical[historical["year"].isin(FINAL_VALIDATION_YEARS)][["year", target_spec["target_column"]]].copy()
    truth = truth.rename(columns={target_spec["target_column"]: "observed_prevalence_per_100k"})
    merged = validation_rows.merge(truth, on="year", how="left")
    merged["residual"] = merged["predicted_prevalence_per_100k"] - merged["observed_prevalence_per_100k"]
    merged["baseline_residual"] = merged["baseline_prevalence_per_100k"] - merged["observed_prevalence_per_100k"]
    return merged


def build_future_projections(
    *,
    projection: pd.DataFrame,
    observed: pd.DataFrame,
    model: RidgeModel,
    target_spec: dict[str, str],
) -> pd.DataFrame:
    observed_history = {
        int(row.year): float(getattr(row, target_spec["target_column"]))
        for row in observed.itertuples(index=False)
    }
    frames: list[pd.DataFrame] = []
    for scenario_family, frame in projection.groupby("scenario_family", sort=True):
        local = frame.sort_values("year").reset_index(drop=True)
        predicted = recursive_predict_years(
            model=model,
            climate_rows=local,
            target_spec=target_spec,
            observed_history=observed_history,
            start_year=2026,
            end_year=LONG_END_YEAR,
            scenario_family=str(scenario_family),
            table_role="scenario_projection_recursive",
        )
        frames.append(predicted)
    return pd.concat(frames, ignore_index=True)


def build_metric_rows(
    *,
    model_name: str,
    target_label: str,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    observed = predictions["observed_prevalence_per_100k"].to_numpy(dtype=float)
    predicted = predictions["predicted_prevalence_per_100k"].to_numpy(dtype=float)
    baseline = predictions["baseline_prevalence_per_100k"].to_numpy(dtype=float)
    rows = [
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "rmse",
            "metric_value": rmse(observed, predicted),
        },
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "mae",
            "metric_value": mae(observed, predicted),
        },
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "bias",
            "metric_value": bias(observed, predicted),
        },
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "mape_pct",
            "metric_value": mape(observed, predicted),
        },
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "baseline_rmse",
            "metric_value": rmse(observed, baseline),
        },
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "baseline_mae",
            "metric_value": mae(observed, baseline),
        },
        {
            "model_name": model_name,
            "target_label": target_label,
            "metric_name": "baseline_mape_pct",
            "metric_value": mape(observed, baseline),
        },
    ]
    return pd.DataFrame(rows)


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


def build_graph_tables(
    *,
    observed: pd.DataFrame,
    future_predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenario_families = sorted(future_predictions["scenario_family"].dropna().astype(str).unique())
    history_rows: list[dict[str, object]] = []

    for model_name, target_spec in TARGET_SPECS.items():
        target_column = target_spec["target_column"]
        history = observed[["year", target_column]].copy()
        for scenario_family in scenario_families:
            for row in history.itertuples(index=False):
                history_rows.append(
                    {
                        "model_name": model_name,
                        "target_column": target_column,
                        "target_label": target_spec["target_label"],
                        "scenario_family": scenario_family,
                        "year": int(row.year),
                        "prevalence_per_100k": float(getattr(row, target_column)),
                        "series_role": "observed_history",
                    }
                )

    historical = pd.DataFrame(history_rows)
    predicted = future_predictions.rename(
        columns={"predicted_prevalence_per_100k": "prevalence_per_100k"}
    ).copy()
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


def write_report(
    *,
    split_summary: pd.DataFrame,
    alpha_summary: pd.DataFrame,
    metric_summary: pd.DataFrame,
    future_predictions: pd.DataFrame,
) -> None:
    lines = [
        "# Model C V2 Residual Climate Report",
        "",
        f"- generated at: `{timestamp_utc()}`",
        "",
        "## Design",
        "",
        "- one collapsed historical climate row is used per observed year",
        "- the model predicts climate-driven prevalence adjustment around a baseline trajectory",
        "- future yearly prevalence is generated recursively within each scenario family",
        "",
        "## Validation Split",
        "",
    ]
    for row in split_summary.itertuples(index=False):
        lines.append(
            f"- {row.model_name}: train years `{row.training_years}`; final validation years `{row.final_validation_years}`"
        )

    lines.extend(["", "## Alpha Selection", ""])
    for row in alpha_summary.itertuples(index=False):
        mean_rmse = "nan" if pd.isna(row.selected_alpha_mean_fold_rmse) else f"{row.selected_alpha_mean_fold_rmse:.4f}"
        lines.append(
            f"- {row.model_name}: selected alpha `{row.selected_alpha}` from mean inner-fold RMSE `{mean_rmse}`"
        )

    lines.extend(["", "## Validation Metrics", ""])
    for model_name, frame in metric_summary.groupby("model_name", sort=False):
        lines.append(f"- {model_name}:")
        for metric in frame.itertuples(index=False):
            metric_value = "nan" if pd.isna(metric.metric_value) else f"{metric.metric_value:.4f}"
            lines.append(f"  {metric.metric_name} = `{metric_value}`")

    lines.extend(["", "## Projection Coverage", ""])
    coverage = (
        future_predictions.groupby(["model_name", "scenario_family"], as_index=False)
        .agg(min_year=("year", "min"), max_year=("year", "max"), row_count=("year", "count"))
        .sort_values(["model_name", "scenario_family"])
    )
    for row in coverage.itertuples(index=False):
        lines.append(
            f"- {row.model_name} / {row.scenario_family}: `{row.min_year}` to `{row.max_year}` with `{row.row_count}` projected yearly points"
        )

    (REPORTS_DIR / "model_c_v2_residual_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ensure_dirs()
    write_workspace_docs()
    copied_inputs = sync_inputs()

    observed, calibration, projection = load_inputs()
    historical = collapse_historical_calibration(calibration, observed)
    historical, projection_indexed, feature_stats = add_compact_indices(historical, projection)

    historical.to_csv(
        OUTPUTS_DIR / "model_c_v2_historical_collapsed.csv",
        index=False,
        encoding="utf-8-sig",
    )
    projection_indexed.to_csv(
        OUTPUTS_DIR / "model_c_v2_projection_indexed.csv",
        index=False,
        encoding="utf-8-sig",
    )

    split_rows: list[dict[str, object]] = []
    alpha_rows: list[dict[str, object]] = []
    coefficient_frames: list[pd.DataFrame] = []
    metric_frames: list[pd.DataFrame] = []
    validation_frames: list[pd.DataFrame] = []
    future_frames: list[pd.DataFrame] = []

    feature_columns_reference: list[str] | None = None

    for model_name, target_spec in TARGET_SPECS.items():
        training_frame, feature_columns = build_training_frame(historical, target_spec)
        feature_columns_reference = feature_columns
        training_frame.to_csv(
            OUTPUTS_DIR / f"{model_name}_v2_training_frame.csv",
            index=False,
            encoding="utf-8-sig",
        )

        selected_alpha, alpha_scoring = select_alpha(
            training_frame,
            feature_columns,
            target_spec["target_column"],
        )

        train_rows = training_frame[training_frame["year"] < min(FINAL_VALIDATION_YEARS)].copy()
        final_model = fit_ridge(train_rows, feature_columns, "residual_target", alpha=selected_alpha)

        validation_predictions = build_validation_predictions(
            historical=historical,
            model=final_model,
            target_spec=target_spec,
        )
        validation_predictions["model_name"] = model_name
        validation_frames.append(validation_predictions)

        future_predictions = build_future_projections(
            projection=projection_indexed,
            observed=observed,
            model=final_model,
            target_spec=target_spec,
        )
        future_predictions["model_name"] = model_name
        future_frames.append(future_predictions)

        split_rows.append(
            {
                "model_name": model_name,
                "training_years": ", ".join(str(value) for value in sorted(train_rows["year"].astype(int).unique())),
                "final_validation_years": ", ".join(str(year) for year in FINAL_VALIDATION_YEARS),
                "training_row_count": int(len(train_rows)),
                "final_validation_row_count": int(len(validation_predictions)),
            }
        )

        mean_alpha = (
            alpha_scoring[pd.to_numeric(alpha_scoring["validation_year"], errors="coerce").notna()]
            .groupby("alpha", as_index=False)["fold_rmse"]
            .mean()
            .sort_values(["fold_rmse", "alpha"], ascending=[True, True])
            .reset_index(drop=True)
        )
        selected_mean_rmse = (
            float(mean_alpha.loc[mean_alpha["alpha"] == selected_alpha, "fold_rmse"].iloc[0])
            if not mean_alpha.empty
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

        coefficient_frames.append(
            build_coefficients_table(
                model_name=model_name,
                model=final_model,
                target_label=target_spec["target_label"],
            )
        )
        metric_frames.append(
            build_metric_rows(
                model_name=model_name,
                target_label=target_spec["target_label"],
                predictions=validation_predictions,
            )
        )

    split_summary = pd.DataFrame(split_rows)
    alpha_summary = pd.DataFrame(alpha_rows)
    coefficients = pd.concat(coefficient_frames, ignore_index=True)
    metric_summary = pd.concat(metric_frames, ignore_index=True)
    validation_predictions = pd.concat(validation_frames, ignore_index=True)
    future_predictions = pd.concat(future_frames, ignore_index=True)

    graph_10y, graph_long = build_graph_tables(
        observed=observed,
        future_predictions=future_predictions,
    )
    future_projection_10y = future_predictions[future_predictions["year"] <= GRAPH_END_YEAR].copy()

    split_summary.to_csv(
        OUTPUTS_DIR / "model_c_v2_validation_split_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    alpha_summary.to_csv(
        OUTPUTS_DIR / "model_c_v2_alpha_selection_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    coefficients.to_csv(
        OUTPUTS_DIR / "model_c_v2_model_coefficients.csv",
        index=False,
        encoding="utf-8-sig",
    )
    metric_summary.to_csv(
        OUTPUTS_DIR / "model_c_v2_validation_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )
    validation_predictions.to_csv(
        OUTPUTS_DIR / "model_c_v2_validation_predictions.csv",
        index=False,
        encoding="utf-8-sig",
    )
    future_projection_10y.to_csv(
        OUTPUTS_DIR / "model_c_v2_future_projection_10y.csv",
        index=False,
        encoding="utf-8-sig",
    )
    future_predictions.to_csv(
        OUTPUTS_DIR / "model_c_v2_future_projection_long.csv",
        index=False,
        encoding="utf-8-sig",
    )
    graph_10y.to_csv(
        OUTPUTS_DIR / "model_c_v2_graph_prevalence_10y.csv",
        index=False,
        encoding="utf-8-sig",
    )
    graph_long.to_csv(
        OUTPUTS_DIR / "model_c_v2_graph_prevalence_long.csv",
        index=False,
        encoding="utf-8-sig",
    )

    write_json(
        OUTPUTS_DIR / "model_c_v2_manifest.json",
        {
            "generated_at": timestamp_utc(),
            "workspace_dir": str(WORKSPACE_DIR),
            "copied_inputs": copied_inputs,
            "final_validation_years": FINAL_VALIDATION_YEARS,
            "inner_validation_years": INNER_VALIDATION_YEARS,
            "graph_end_year": GRAPH_END_YEAR,
            "long_end_year": LONG_END_YEAR,
            "feature_columns": feature_columns_reference or [],
            "compact_index_feature_stats": feature_stats,
        },
    )

    write_report(
        split_summary=split_summary,
        alpha_summary=alpha_summary,
        metric_summary=metric_summary,
        future_predictions=future_predictions,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
