from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pipeline_utils import PROJECT_ROOT, copy_file, timestamp_utc, write_json


WORKSPACE_DIR = PROJECT_ROOT / "modeling - model_a_operational_forecast"
INPUTS_DIR = WORKSPACE_DIR / "inputs"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
REPORTS_DIR = WORKSPACE_DIR / "reports"

MONTHLY_PANEL_SOURCE = PROJECT_ROOT / "processed" / "slovenia" / "slovenia_monthly_predictive_panel.csv"
MODEL_A_FUTURE_SOURCE = (
    PROJECT_ROOT
    / "data processing - copernicus_forecast_data"
    / "outputs"
    / "model_a"
    / "model_a_future_operational_numeric.csv"
)

TARGET_SPECS = {
    "lyme_prevalence": {
        "target_column": "lyme_cases_per_100k",
        "target_label": "Lyme prevalence per 100k",
    },
    "kme_prevalence": {
        "target_column": "kme_cases_per_100k",
        "target_label": "KME prevalence per 100k",
    },
    "combined_prevalence": {
        "target_column": "tick_borne_cases_total_per_100k",
        "target_label": "Combined tick-borne prevalence per 100k",
    },
}

WEATHER_FEATURES = [
    "air_temperature_c_mean",
    "relative_humidity_pct_mean",
    "precipitation_sum_mm",
    "soil_temperature_level_1_c_mean",
]

FUTURE_WEATHER_RENAME = {
    "air_temperature_c_mean_forecast": "air_temperature_c_mean",
    "relative_humidity_pct_mean_forecast": "relative_humidity_pct_mean",
    "precipitation_sum_mm_forecast": "precipitation_sum_mm",
    "soil_temperature_level_1_c_mean_forecast": "soil_temperature_level_1_c_mean",
}

FINAL_VALIDATION_YEAR = 2025
INNER_VALIDATION_YEARS = [2023, 2024]
ALPHA_GRID = [0.0, 0.1, 1.0, 10.0, 100.0]


@dataclass
class RidgeModel:
    feature_columns: list[str]
    alpha: float
    intercept: float
    coefficients: np.ndarray

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        values = frame[self.feature_columns].to_numpy(dtype=float)
        predictions = self.intercept + values @ self.coefficients
        return np.clip(predictions, 0.0, None)


def ensure_dirs() -> None:
    for path in [WORKSPACE_DIR, INPUTS_DIR, OUTPUTS_DIR, REPORTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def write_workspace_docs() -> None:
    readme = """# Model A Operational Forecast Modeling

This folder is the dedicated modeling workspace for Model A.

Model A goal:

- fit Slovenia-level monthly prevalence models for Lyme, KME, and combined tick-borne disease
- use the current Copernicus seasonal forecast weather block
- produce a graph-ready operational outlook for the available future target months

This workspace is downstream of the processed forecast tables and does not modify them.
"""
    methodology = """# Model A Methodology

## Important Constraint

Model A does not yet have a full historical hindcast weather block for humidity,
precipitation, and soil under the same reproducible acquisition path as the future files.

Because of that, the first-pass Model A validation uses:

- observed historical monthly weather as a proxy for what forecast weather would have been
- a fixed latest-observed disease anchor across the January-to-April operational issue window

That matches the current future forecast table, where `latest_observed_month_available`
is fixed at `2025-12-01`.

## Operational Window

The first-pass operational line uses the latest available issue for each target month from:

- January 2026 issue
- February 2026 issue
- March 2026 issue
- April 2026 issue

This yields one canonical forecast point per target month for:

- February 2026 through October 2026

## Validation Design

- final holdout year: 2025
- validation months: February through October 2025, using the same latest-issue structure
- inner alpha selection years: 2023 and 2024

## First-Pass Feature Block

- target-month weather block: temperature, humidity, precipitation, soil temperature level 1
- target-month seasonal encoding
- issue month and lead month
- December prevalence anchor from the previous year
- previous-year Q4 prevalence mean
- same-month previous-year prevalence

This is a practical first-pass operational design, not yet the final forecast-validation design.
"""
    inputs_readme = "# Inputs\n\nCopied source tables for the isolated Model A modeling step.\n"
    outputs_readme = "# Outputs\n\nValidation, projections, graph tables, and model metadata.\n"
    reports_readme = "# Reports\n\nHuman-readable notes for Model A fitting and operational outlook generation.\n"

    (WORKSPACE_DIR / "README.md").write_text(readme, encoding="utf-8")
    (WORKSPACE_DIR / "METHODOLOGY.md").write_text(methodology, encoding="utf-8")
    (INPUTS_DIR / "README.md").write_text(inputs_readme, encoding="utf-8")
    (OUTPUTS_DIR / "README.md").write_text(outputs_readme, encoding="utf-8")
    (REPORTS_DIR / "README.md").write_text(reports_readme, encoding="utf-8")


def sync_inputs() -> dict[str, str]:
    copied = {}
    for source in [MONTHLY_PANEL_SOURCE, MODEL_A_FUTURE_SOURCE]:
        destination = INPUTS_DIR / source.name
        copy_file(source, destination)
        copied[source.name] = str(destination)
    return copied


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly = pd.read_csv(INPUTS_DIR / MONTHLY_PANEL_SOURCE.name, encoding="utf-8-sig")
    future = pd.read_csv(INPUTS_DIR / MODEL_A_FUTURE_SOURCE.name, encoding="utf-8-sig")
    monthly["month_start"] = pd.to_datetime(monthly["month_start"])
    future["target_month_start"] = pd.to_datetime(future["target_month_start"])
    future["init_month_start"] = pd.to_datetime(future["init_month_start"])
    monthly["year"] = pd.to_numeric(monthly["year"], errors="coerce").astype(int)
    monthly["month"] = pd.to_numeric(monthly["month"], errors="coerce").astype(int)
    future["target_year"] = pd.to_numeric(future["target_year"], errors="coerce").astype(int)
    future["target_month"] = pd.to_numeric(future["target_month"], errors="coerce").astype(int)
    future["issue_year"] = pd.to_numeric(future["issue_year"], errors="coerce").astype(int)
    future["issue_month"] = pd.to_numeric(future["issue_month"], errors="coerce").astype(int)
    future["lead_month"] = pd.to_numeric(future["lead_month"], errors="coerce").astype(int)
    return monthly, future


def weighted_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def weighted_mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def weighted_bias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(y_pred - y_true))


def weighted_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    non_zero = np.abs(y_true) > 1e-9
    if not np.any(non_zero):
        return float("nan")
    return float(100.0 * np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])))


def fit_ridge_model(
    frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    alpha: float,
) -> RidgeModel:
    x = frame[feature_columns].to_numpy(dtype=float)
    y = frame[target_column].to_numpy(dtype=float)
    x_mean = x.mean(axis=0)
    x_centered = x - x_mean
    x_scale = x_centered.std(axis=0)
    x_scale = np.where(x_scale > 1e-12, x_scale, 1.0)
    x_std = x_centered / x_scale
    y_mean = float(y.mean())
    y_centered = y - y_mean

    gram = x_std.T @ x_std
    beta_std = np.linalg.pinv(gram + alpha * np.eye(gram.shape[0])) @ (x_std.T @ y_centered)
    coefficients = beta_std / x_scale
    intercept = float(y_mean - x_mean @ coefficients)
    return RidgeModel(feature_columns=feature_columns, alpha=float(alpha), intercept=intercept, coefficients=coefficients)


def build_historical_latest_issue_rows(monthly: pd.DataFrame) -> pd.DataFrame:
    index = monthly.set_index("month_start").sort_index()
    rows: list[dict[str, object]] = []

    for target in monthly.itertuples(index=False):
        target_month = pd.Timestamp(target.month_start)
        target_year = int(target.year)
        target_month_num = int(target.month)

        if target_month_num < 2 or target_month_num > 10:
            continue

        issue_month_num = min(target_month_num - 1, 4)
        lead_month = target_month_num - issue_month_num
        issue_month_start = pd.Timestamp(year=target_year, month=issue_month_num, day=1)
        anchor_month_start = pd.Timestamp(year=target_year - 1, month=12, day=1)
        q4_months = [
            pd.Timestamp(year=target_year - 1, month=10, day=1),
            pd.Timestamp(year=target_year - 1, month=11, day=1),
            pd.Timestamp(year=target_year - 1, month=12, day=1),
        ]
        same_month_last_year = pd.Timestamp(year=target_year - 1, month=target_month_num, day=1)

        if anchor_month_start not in index.index or same_month_last_year not in index.index:
            continue
        if any(month not in index.index for month in q4_months):
            continue

        anchor_row = index.loc[anchor_month_start]
        q4_frame = index.loc[q4_months]
        same_month_row = index.loc[same_month_last_year]
        target_row = index.loc[target_month]

        row: dict[str, object] = {
            "target_month_start": target_month,
            "target_year": target_year,
            "target_month": target_month_num,
            "issue_month_start": issue_month_start,
            "issue_year": target_year,
            "issue_month": issue_month_num,
            "lead_month": lead_month,
            "target_month_of_year_sin": float(target_row["month_of_year_sin"]),
            "target_month_of_year_cos": float(target_row["month_of_year_cos"]),
            "anchor_month_start": anchor_month_start,
        }

        for weather_col in WEATHER_FEATURES:
            row[weather_col] = float(target_row[weather_col])

        for _, spec in TARGET_SPECS.items():
            col = spec["target_column"]
            row[f"{col}_anchor_prev"] = float(anchor_row[col])
            row[f"{col}_anchor_q4_mean"] = float(q4_frame[col].mean())
            row[f"{col}_same_month_last_year"] = float(same_month_row[col])
            row[col] = float(target_row[col])

        rows.append(row)

    return pd.DataFrame(rows).sort_values("target_month_start").reset_index(drop=True)


def build_future_latest_issue_rows(monthly: pd.DataFrame, future: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    future_ready = future[future["usable_core_weather_block_ready"].fillna(False)].copy()
    future_ready = future_ready.rename(columns=FUTURE_WEATHER_RENAME)
    future_ready = future_ready.sort_values(["target_month_start", "init_month_start"]).reset_index(drop=True)

    anchor_month_start = pd.Timestamp("2025-12-01")
    q4_months = [pd.Timestamp("2025-10-01"), pd.Timestamp("2025-11-01"), pd.Timestamp("2025-12-01")]
    monthly_index = monthly.set_index("month_start").sort_index()
    anchor_row = monthly_index.loc[anchor_month_start]
    q4_frame = monthly_index.loc[q4_months]

    for _, spec in TARGET_SPECS.items():
        col = spec["target_column"]
        future_ready[f"{col}_anchor_prev"] = float(anchor_row[col])
        future_ready[f"{col}_anchor_q4_mean"] = float(q4_frame[col].mean())
        same_month_map = (
            monthly[monthly["year"] == 2025][["month", col]]
            .rename(columns={col: f"{col}_same_month_last_year"})
            .copy()
        )
        future_ready = future_ready.merge(
            same_month_map,
            left_on="target_month",
            right_on="month",
            how="left",
        ).drop(columns=["month"])

    latest_issue = (
        future_ready.sort_values(["target_month_start", "init_month_start"])
        .groupby("target_month_start", as_index=False)
        .tail(1)
        .sort_values("target_month_start")
        .reset_index(drop=True)
    )
    latest_issue["forecast_selection_rule"] = "latest_available_issue_per_target_month"
    future_ready["forecast_selection_rule"] = "all_issue_target_rows"
    return future_ready, latest_issue


def feature_columns_for_target(target_column: str) -> list[str]:
    return [
        *WEATHER_FEATURES,
        "target_month_of_year_sin",
        "target_month_of_year_cos",
        "lead_month",
        "issue_month",
        f"{target_column}_anchor_prev",
        f"{target_column}_anchor_q4_mean",
        f"{target_column}_same_month_last_year",
    ]


def select_alpha(
    frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
) -> tuple[float, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    training_candidates = frame[frame["target_year"] < FINAL_VALIDATION_YEAR].copy()

    for alpha in ALPHA_GRID:
        fold_scores = []
        for validation_year in INNER_VALIDATION_YEARS:
            fold_train = training_candidates[training_candidates["target_year"] < validation_year].copy()
            fold_validate = training_candidates[training_candidates["target_year"] == validation_year].copy()
            if fold_train.empty or fold_validate.empty:
                continue
            model = fit_ridge_model(fold_train, feature_columns, target_column, alpha=alpha)
            pred = model.predict(fold_validate)
            rmse = weighted_rmse(fold_validate[target_column].to_numpy(dtype=float), pred)
            fold_scores.append(rmse)
            rows.append({"alpha": alpha, "validation_year": validation_year, "fold_rmse": rmse})
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
    selected_alpha = float(alpha_summary.iloc[0]["alpha"]) if not alpha_summary.empty else 0.0
    return selected_alpha, scoring.merge(alpha_summary, on="alpha", how="left")


def build_graph_table(
    monthly: pd.DataFrame,
    operational_predictions: pd.DataFrame,
) -> pd.DataFrame:
    history = monthly[
        (monthly["month_start"] >= pd.Timestamp("2024-01-01"))
        & (monthly["month_start"] <= pd.Timestamp("2025-12-01"))
    ].copy()

    rows: list[dict[str, object]] = []
    for model_name, spec in TARGET_SPECS.items():
        col = spec["target_column"]
        for row in history.itertuples(index=False):
            rows.append(
                {
                    "model_name": model_name,
                    "target_column": col,
                    "target_label": spec["target_label"],
                    "date": pd.Timestamp(row.month_start),
                    "prevalence_per_100k": float(getattr(row, col)),
                    "series_role": "observed_history",
                }
            )
        model_future = operational_predictions[operational_predictions["model_name"] == model_name]
        for row in model_future.itertuples(index=False):
            rows.append(
                {
                    "model_name": model_name,
                    "target_column": col,
                    "target_label": spec["target_label"],
                    "date": pd.Timestamp(row.target_month_start),
                    "prevalence_per_100k": float(row.predicted_prevalence_per_100k),
                    "series_role": "predicted_future",
                }
            )

    return pd.DataFrame(rows).sort_values(["model_name", "date", "series_role"]).reset_index(drop=True)


def build_coefficients_table(model_name: str, target_label: str, model: RidgeModel) -> pd.DataFrame:
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


def build_metric_rows(model_name: str, target_label: str, frame: pd.DataFrame) -> pd.DataFrame:
    observed = frame["observed_prevalence_per_100k"].to_numpy(dtype=float)
    predicted = frame["predicted_prevalence_per_100k"].to_numpy(dtype=float)
    rows = [
        {"model_name": model_name, "target_label": target_label, "metric_name": "rmse", "metric_value": weighted_rmse(observed, predicted)},
        {"model_name": model_name, "target_label": target_label, "metric_name": "mae", "metric_value": weighted_mae(observed, predicted)},
        {"model_name": model_name, "target_label": target_label, "metric_name": "bias", "metric_value": weighted_bias(observed, predicted)},
        {"model_name": model_name, "target_label": target_label, "metric_name": "mape_pct", "metric_value": weighted_mape(observed, predicted)},
    ]
    return pd.DataFrame(rows)


def write_report(
    *,
    split_summary: pd.DataFrame,
    alpha_summary: pd.DataFrame,
    metric_summary: pd.DataFrame,
    operational_predictions: pd.DataFrame,
) -> None:
    lines = [
        "# Model A Operational Forecast Modeling Report",
        "",
        f"- generated at: `{timestamp_utc()}`",
        "",
        "## Important Caveat",
        "",
        "- historical validation still uses observed monthly weather as a proxy for historical forecast weather",
        "- the future operational outlook does use the real Copernicus forecast weather block",
        "",
        "## Validation Structure",
        "",
    ]
    for row in split_summary.itertuples(index=False):
        lines.append(
            f"- {row.model_name}: train target years `{row.training_years}`; final validation year `{row.final_validation_year}`"
        )

    lines.extend(["", "## Alpha Selection", ""])
    for row in alpha_summary.itertuples(index=False):
        lines.append(
            f"- {row.model_name}: selected alpha `{row.selected_alpha}` from mean inner-fold RMSE `{row.selected_alpha_mean_fold_rmse:.4f}`"
        )

    lines.extend(["", "## Final Validation Metrics", ""])
    for row in metric_summary.itertuples(index=False):
        lines.append(f"- {row.model_name} {row.metric_name}: `{row.metric_value:.4f}`")

    lines.extend(["", "## Operational Coverage", ""])
    for row in operational_predictions.itertuples(index=False):
        lines.append(
            f"- {row.model_name}: target `{pd.Timestamp(row.target_month_start).date()}` from issue `{pd.Timestamp(row.init_month_start).date()}`"
        )

    (REPORTS_DIR / "model_a_operational_modeling_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ensure_dirs()
    write_workspace_docs()
    copied_inputs = sync_inputs()

    monthly, future = load_inputs()
    historical_panel = build_historical_latest_issue_rows(monthly)
    future_all, future_latest = build_future_latest_issue_rows(monthly, future)

    split_rows: list[dict[str, object]] = []
    alpha_rows: list[dict[str, object]] = []
    coefficient_frames: list[pd.DataFrame] = []
    metric_frames: list[pd.DataFrame] = []
    validation_frames: list[pd.DataFrame] = []
    future_all_frames: list[pd.DataFrame] = []
    future_latest_frames: list[pd.DataFrame] = []

    historical_panel.to_csv(OUTPUTS_DIR / "model_a_historical_latest_issue_panel.csv", index=False, encoding="utf-8-sig")
    future_all.to_csv(OUTPUTS_DIR / "model_a_future_issue_target_feature_panel.csv", index=False, encoding="utf-8-sig")
    future_latest.to_csv(OUTPUTS_DIR / "model_a_future_latest_issue_feature_panel.csv", index=False, encoding="utf-8-sig")

    for model_name, spec in TARGET_SPECS.items():
        target_column = spec["target_column"]
        feature_columns = feature_columns_for_target(target_column)
        frame = historical_panel[
            ["target_month_start", "target_year", "target_month", "issue_month_start", *feature_columns, target_column]
        ].copy()
        frame = frame.dropna().reset_index(drop=True)

        selected_alpha, alpha_scoring = select_alpha(frame, feature_columns, target_column)
        training = frame[frame["target_year"] < FINAL_VALIDATION_YEAR].copy()
        validation = frame[frame["target_year"] == FINAL_VALIDATION_YEAR].copy()
        model = fit_ridge_model(training, feature_columns, target_column, alpha=selected_alpha)

        validation_pred = validation[["target_month_start", "issue_month_start", "issue_month", "lead_month"]].copy()
        validation_pred["model_name"] = model_name
        validation_pred["target_label"] = spec["target_label"]
        validation_pred["observed_prevalence_per_100k"] = validation[target_column].to_numpy(dtype=float)
        validation_pred["predicted_prevalence_per_100k"] = model.predict(validation)
        validation_pred["residual"] = validation_pred["predicted_prevalence_per_100k"] - validation_pred["observed_prevalence_per_100k"]
        validation_frames.append(validation_pred)

        future_pred_all = future_all[["init_month_start", "target_month_start", *feature_columns]].copy()
        future_pred_all["model_name"] = model_name
        future_pred_all["target_label"] = spec["target_label"]
        future_pred_all["predicted_prevalence_per_100k"] = model.predict(future_pred_all)
        future_all_frames.append(future_pred_all)

        future_pred_latest = future_latest[
            ["init_month_start", "target_month_start", *feature_columns, "forecast_selection_rule"]
        ].copy()
        future_pred_latest["model_name"] = model_name
        future_pred_latest["target_label"] = spec["target_label"]
        future_pred_latest["predicted_prevalence_per_100k"] = model.predict(future_pred_latest)
        future_latest_frames.append(future_pred_latest)

        split_rows.append(
            {
                "model_name": model_name,
                "training_years": ", ".join(str(y) for y in sorted(training["target_year"].unique())),
                "final_validation_year": FINAL_VALIDATION_YEAR,
                "training_row_count": int(len(training)),
                "final_validation_row_count": int(len(validation)),
            }
        )

        mean_alpha_scores = (
            alpha_scoring[pd.to_numeric(alpha_scoring["validation_year"], errors="coerce").notna()]
            .groupby("alpha", as_index=False)["fold_rmse"]
            .mean()
            .sort_values(["fold_rmse", "alpha"], ascending=[True, True])
            .reset_index(drop=True)
        )
        selected_mean_rmse = float(
            mean_alpha_scores.loc[mean_alpha_scores["alpha"] == selected_alpha, "fold_rmse"].iloc[0]
        ) if not mean_alpha_scores.empty else math.nan
        alpha_rows.append(
            {
                "model_name": model_name,
                "selected_alpha": selected_alpha,
                "selected_alpha_mean_fold_rmse": selected_mean_rmse,
            }
        )
        alpha_scoring.insert(0, "model_name", model_name)
        alpha_scoring.to_csv(OUTPUTS_DIR / f"{model_name}_alpha_scoring.csv", index=False, encoding="utf-8-sig")

        coefficient_frames.append(build_coefficients_table(model_name, spec["target_label"], model))
        metric_frames.append(build_metric_rows(model_name, spec["target_label"], validation_pred))

    split_summary = pd.DataFrame(split_rows)
    alpha_summary = pd.DataFrame(alpha_rows)
    metric_summary = pd.concat(metric_frames, ignore_index=True)
    coefficients = pd.concat(coefficient_frames, ignore_index=True)
    validation_predictions = pd.concat(validation_frames, ignore_index=True)
    future_issue_target_predictions = pd.concat(future_all_frames, ignore_index=True)
    future_latest_predictions = pd.concat(future_latest_frames, ignore_index=True)

    graph_table = build_graph_table(monthly, future_latest_predictions)

    split_summary.to_csv(OUTPUTS_DIR / "model_a_validation_split_summary.csv", index=False, encoding="utf-8-sig")
    alpha_summary.to_csv(OUTPUTS_DIR / "model_a_alpha_selection_summary.csv", index=False, encoding="utf-8-sig")
    metric_summary.to_csv(OUTPUTS_DIR / "model_a_final_validation_metrics.csv", index=False, encoding="utf-8-sig")
    coefficients.to_csv(OUTPUTS_DIR / "model_a_model_coefficients.csv", index=False, encoding="utf-8-sig")
    validation_predictions.to_csv(OUTPUTS_DIR / "model_a_final_validation_predictions.csv", index=False, encoding="utf-8-sig")
    future_issue_target_predictions.to_csv(OUTPUTS_DIR / "model_a_future_issue_target_predictions.csv", index=False, encoding="utf-8-sig")
    future_latest_predictions.to_csv(OUTPUTS_DIR / "model_a_future_latest_issue_predictions.csv", index=False, encoding="utf-8-sig")
    graph_table.to_csv(OUTPUTS_DIR / "model_a_graph_prevalence_operational.csv", index=False, encoding="utf-8-sig")

    write_json(
        OUTPUTS_DIR / "model_a_operational_modeling_manifest.json",
        {
            "generated_at": timestamp_utc(),
            "workspace_dir": str(WORKSPACE_DIR),
            "copied_inputs": copied_inputs,
            "final_validation_year": FINAL_VALIDATION_YEAR,
            "inner_validation_years": INNER_VALIDATION_YEARS,
        },
    )
    write_report(
        split_summary=split_summary,
        alpha_summary=alpha_summary,
        metric_summary=metric_summary,
        operational_predictions=future_latest_predictions,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
