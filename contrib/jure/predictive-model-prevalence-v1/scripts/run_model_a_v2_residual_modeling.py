from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pipeline_utils import PROJECT_ROOT, copy_file, timestamp_utc, write_json


WORKSPACE_DIR = PROJECT_ROOT / "modeling - model_a_v2_residual_forecast"
INPUTS_DIR = WORKSPACE_DIR / "inputs"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
REPORTS_DIR = WORKSPACE_DIR / "reports"

MONTHLY_PANEL_SOURCE = PROJECT_ROOT / "processed" / "slovenia" / "slovenia_monthly_predictive_panel.csv"
FUTURE_SOURCE = (
    PROJECT_ROOT
    / "data processing - copernicus_forecast_data"
    / "outputs"
    / "model_a"
    / "model_a_future_operational_numeric.csv"
)

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

TARGET_SPECS = {
    "lyme_prevalence": {
        "target_column": "lyme_cases_per_100k",
        "target_label": "Lyme prevalence per 100k",
        "baseline_column": "lyme_cases_per_100k_same_month_last_year",
    },
    "kme_prevalence": {
        "target_column": "kme_cases_per_100k",
        "target_label": "KME prevalence per 100k",
        "baseline_column": "kme_cases_per_100k_same_month_last_year",
    },
    "combined_prevalence": {
        "target_column": "tick_borne_cases_total_per_100k",
        "target_label": "Combined tick-borne prevalence per 100k",
        "baseline_column": "tick_borne_cases_total_per_100k_same_month_last_year",
    },
}

FINAL_VALIDATION_YEAR = 2025
INNER_VALIDATION_YEARS = [2023, 2024]
ALPHA_GRID = [0.1, 1.0, 10.0, 100.0, 1000.0]


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
        standardized = (values - self.feature_means) / self.feature_scales
        predictions = self.intercept + standardized @ self.coefficients
        return np.asarray(predictions, dtype=float)


def ensure_dirs() -> None:
    for path in [WORKSPACE_DIR, INPUTS_DIR, OUTPUTS_DIR, REPORTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def write_workspace_docs() -> None:
    readme = """# Model A V2 Residual Forecasting

This workspace contains the Version 2 monthly operational forecasting branch.

Key change from V1:

- the model no longer predicts prevalence directly
- it starts from a seasonal baseline, mainly same-month-last-year prevalence
- it then predicts the residual adjustment around that baseline using forecast weather anomalies

Outputs include holdout validation tables, future latest-issue forecasts, and
presentation-ready charts.

## Main Commands

```powershell
py -3 scripts/run_model_a_v2_residual_modeling.py
py -3 scripts/generate_model_a_v2_presentation_graphs.py
```
"""
    methodology = """# Model A V2 Methodology

## Core Idea

Model A V1 was learning too much of the seasonal shape directly.
Model A V2 forces a baseline-plus-adjustment structure:

1. baseline = same-month-last-year prevalence
2. residual target = observed prevalence - baseline
3. residual model uses:
   - target-month weather anomalies versus historical month climatology
   - issue month
   - lead month
   - month-of-year encoding
   - baseline context versus previous December and previous Q4

## Validation

- training years: 2017-2024
- final validation year: 2025
- inner alpha selection years: 2023 and 2024

## Important Caveat

Historical validation still relies on observed monthly weather as a proxy for what
historical forecast weather would have been. The future operational run does use the
real Copernicus forecast weather block.
"""
    (WORKSPACE_DIR / "README.md").write_text(readme, encoding="utf-8")
    (WORKSPACE_DIR / "METHODOLOGY.md").write_text(methodology, encoding="utf-8")
    (INPUTS_DIR / "README.md").write_text("# Inputs\n\nCopied source tables for Model A V2.\n", encoding="utf-8")
    (OUTPUTS_DIR / "README.md").write_text("# Outputs\n\nValidation, forecasts, coefficients, graph tables, and metadata.\n", encoding="utf-8")
    (REPORTS_DIR / "README.md").write_text("# Reports\n\nHuman-readable summaries for Model A V2.\n", encoding="utf-8")


def sync_inputs() -> dict[str, str]:
    copied = {}
    for source in [MONTHLY_PANEL_SOURCE, FUTURE_SOURCE]:
        destination = INPUTS_DIR / source.name
        copy_file(source, destination)
        copied[source.name] = str(destination)
    return copied


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly = pd.read_csv(INPUTS_DIR / MONTHLY_PANEL_SOURCE.name, encoding="utf-8-sig")
    future = pd.read_csv(INPUTS_DIR / FUTURE_SOURCE.name, encoding="utf-8-sig")

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


def build_monthly_climatology(monthly: pd.DataFrame) -> pd.DataFrame:
    climatology = monthly.groupby("month", as_index=False)[WEATHER_FEATURES].mean()
    climatology = climatology.rename(
        columns={feature: f"{feature}_climatology" for feature in WEATHER_FEATURES}
    )
    return climatology


def build_historical_operational_panel(monthly: pd.DataFrame, climatology: pd.DataFrame) -> pd.DataFrame:
    index = monthly.set_index("month_start").sort_index()
    rows: list[dict[str, object]] = []

    for target in monthly.itertuples(index=False):
        target_month_start = pd.Timestamp(target.month_start)
        target_year = int(target.year)
        target_month = int(target.month)

        if target_month < 2 or target_month > 10:
            continue
        if target_year < 2017:
            continue

        issue_month = min(target_month - 1, 4)
        lead_month = target_month - issue_month
        issue_month_start = pd.Timestamp(year=target_year, month=issue_month, day=1)
        same_month_last_year = pd.Timestamp(year=target_year - 1, month=target_month, day=1)
        prev_dec = pd.Timestamp(year=target_year - 1, month=12, day=1)
        q4_months = [
            pd.Timestamp(year=target_year - 1, month=10, day=1),
            pd.Timestamp(year=target_year - 1, month=11, day=1),
            pd.Timestamp(year=target_year - 1, month=12, day=1),
        ]

        if same_month_last_year not in index.index or prev_dec not in index.index:
            continue
        if any(month_start not in index.index for month_start in q4_months):
            continue

        target_row = index.loc[target_month_start]
        same_month_row = index.loc[same_month_last_year]
        prev_dec_row = index.loc[prev_dec]
        q4_frame = index.loc[q4_months]
        climatology_row = climatology[climatology["month"] == target_month].iloc[0]

        row: dict[str, object] = {
            "target_month_start": target_month_start,
            "target_year": target_year,
            "target_month": target_month,
            "issue_month_start": issue_month_start,
            "issue_month": issue_month,
            "lead_month": lead_month,
            "target_month_of_year_sin": float(target_row["month_of_year_sin"]),
            "target_month_of_year_cos": float(target_row["month_of_year_cos"]),
        }

        for feature in WEATHER_FEATURES:
            value = float(target_row[feature])
            clim = float(climatology_row[f"{feature}_climatology"])
            row[feature] = value
            row[f"{feature}_anomaly"] = value - clim

        for _, spec in TARGET_SPECS.items():
            column = spec["target_column"]
            baseline = float(same_month_row[column])
            prev_dec_value = float(prev_dec_row[column])
            q4_mean = float(q4_frame[column].mean())
            observed = float(target_row[column])
            row[f"{column}_baseline_same_month_last_year"] = baseline
            row[f"{column}_prev_dec_anchor"] = prev_dec_value
            row[f"{column}_prev_q4_mean"] = q4_mean
            row[f"{column}_baseline_gap_prev_dec"] = baseline - prev_dec_value
            row[f"{column}_baseline_gap_q4_mean"] = baseline - q4_mean
            row[column] = observed
            row[f"{column}_residual_target"] = observed - baseline

        rows.append(row)

    return pd.DataFrame(rows).sort_values("target_month_start").reset_index(drop=True)


def build_future_operational_panels(
    monthly: pd.DataFrame,
    future: pd.DataFrame,
    climatology: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    usable = future[future["usable_core_weather_block_ready"].fillna(False)].copy()
    usable = usable.rename(columns=FUTURE_WEATHER_RENAME)
    usable = usable.sort_values(["target_month_start", "init_month_start"]).reset_index(drop=True)

    monthly_index = monthly.set_index("month_start").sort_index()
    prev_dec = pd.Timestamp("2025-12-01")
    q4_months = [pd.Timestamp("2025-10-01"), pd.Timestamp("2025-11-01"), pd.Timestamp("2025-12-01")]
    prev_dec_row = monthly_index.loc[prev_dec]
    q4_frame = monthly_index.loc[q4_months]

    usable = usable.merge(climatology, left_on="target_month", right_on="month", how="left").drop(columns=["month"])

    for feature in WEATHER_FEATURES:
        usable[f"{feature}_anomaly"] = usable[feature] - usable[f"{feature}_climatology"]

    same_month_maps: dict[str, pd.DataFrame] = {}
    for _, spec in TARGET_SPECS.items():
        column = spec["target_column"]
        same_month_maps[column] = (
            monthly[monthly["year"] == 2025][["month", column]]
            .rename(columns={column: f"{column}_baseline_same_month_last_year"})
            .copy()
        )

    for column, mapping in same_month_maps.items():
        usable = usable.merge(mapping, left_on="target_month", right_on="month", how="left").drop(columns=["month"])
        usable[f"{column}_prev_dec_anchor"] = float(prev_dec_row[column])
        usable[f"{column}_prev_q4_mean"] = float(q4_frame[column].mean())
        usable[f"{column}_baseline_gap_prev_dec"] = (
            usable[f"{column}_baseline_same_month_last_year"] - usable[f"{column}_prev_dec_anchor"]
        )
        usable[f"{column}_baseline_gap_q4_mean"] = (
            usable[f"{column}_baseline_same_month_last_year"] - usable[f"{column}_prev_q4_mean"]
        )

    usable["forecast_selection_rule"] = "all_issue_target_rows"
    latest = (
        usable.sort_values(["target_month_start", "init_month_start"])
        .groupby("target_month_start", as_index=False)
        .tail(1)
        .sort_values("target_month_start")
        .reset_index(drop=True)
    )
    latest["forecast_selection_rule"] = "latest_available_issue_per_target_month"
    return usable, latest


def feature_columns_for_target(target_column: str) -> list[str]:
    return [
        "target_month_of_year_sin",
        "target_month_of_year_cos",
        "issue_month",
        "lead_month",
        *[f"{feature}_anomaly" for feature in WEATHER_FEATURES],
        f"{target_column}_baseline_same_month_last_year",
        f"{target_column}_baseline_gap_prev_dec",
        f"{target_column}_baseline_gap_q4_mean",
    ]


def select_alpha(
    frame: pd.DataFrame,
    feature_columns: list[str],
    residual_target_column: str,
    baseline_column: str,
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
            model = fit_ridge(fold_train, feature_columns, residual_target_column, alpha=alpha)
            residual_pred = model.predict(fold_validate)
            prediction = fold_validate[baseline_column].to_numpy(dtype=float) + residual_pred
            prediction = np.clip(prediction, 0.0, None)
            score = rmse(fold_validate[baseline_column.replace("_baseline_same_month_last_year", "")].to_numpy(dtype=float), prediction)
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


def build_metric_rows(
    model_name: str,
    target_label: str,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    observed = predictions["observed_prevalence_per_100k"].to_numpy(dtype=float)
    predicted = predictions["predicted_prevalence_per_100k"].to_numpy(dtype=float)
    baseline = predictions["baseline_prevalence_per_100k"].to_numpy(dtype=float)
    rows = [
        {"model_name": model_name, "target_label": target_label, "metric_name": "rmse", "metric_value": rmse(observed, predicted)},
        {"model_name": model_name, "target_label": target_label, "metric_name": "mae", "metric_value": mae(observed, predicted)},
        {"model_name": model_name, "target_label": target_label, "metric_name": "bias", "metric_value": bias(observed, predicted)},
        {"model_name": model_name, "target_label": target_label, "metric_name": "mape_pct", "metric_value": mape(observed, predicted)},
        {"model_name": model_name, "target_label": target_label, "metric_name": "baseline_rmse", "metric_value": rmse(observed, baseline)},
        {"model_name": model_name, "target_label": target_label, "metric_name": "baseline_mae", "metric_value": mae(observed, baseline)},
        {"model_name": model_name, "target_label": target_label, "metric_name": "baseline_mape_pct", "metric_value": mape(observed, baseline)},
    ]
    return pd.DataFrame(rows)


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


def build_graph_table(monthly: pd.DataFrame, future_latest: pd.DataFrame) -> pd.DataFrame:
    history = monthly[
        (monthly["month_start"] >= pd.Timestamp("2017-01-01"))
        & (monthly["month_start"] <= pd.Timestamp("2025-12-01"))
    ].copy()
    rows: list[dict[str, object]] = []

    for model_name, spec in TARGET_SPECS.items():
        target_column = spec["target_column"]
        for row in history.itertuples(index=False):
            rows.append(
                {
                    "model_name": model_name,
                    "target_column": target_column,
                    "target_label": spec["target_label"],
                    "date": pd.Timestamp(row.month_start),
                    "prevalence_per_100k": float(getattr(row, target_column)),
                    "series_role": "observed_history",
                }
            )

        local_future = future_latest[future_latest["model_name"] == model_name]
        for row in local_future.itertuples(index=False):
            rows.append(
                {
                    "model_name": model_name,
                    "target_column": target_column,
                    "target_label": spec["target_label"],
                    "date": pd.Timestamp(row.target_month_start),
                    "prevalence_per_100k": float(row.predicted_prevalence_per_100k),
                    "series_role": "predicted_future",
                }
            )
    return pd.DataFrame(rows).sort_values(["model_name", "date", "series_role"]).reset_index(drop=True)


def write_report(
    *,
    split_summary: pd.DataFrame,
    alpha_summary: pd.DataFrame,
    metric_summary: pd.DataFrame,
    future_latest: pd.DataFrame,
) -> None:
    lines = [
        "# Model A V2 Residual Forecast Report",
        "",
        f"- generated at: `{timestamp_utc()}`",
        "",
        "## Design",
        "",
        "- baseline = same-month-last-year prevalence",
        "- model predicts residual adjustment around that baseline",
        "- weather inputs enter as month-climatology anomalies rather than only raw values",
        "",
        "## Validation Split",
        "",
    ]
    for row in split_summary.itertuples(index=False):
        lines.append(
            f"- {row.model_name}: train years `{row.training_years}`; final validation year `{row.final_validation_year}`"
        )

    lines.extend(["", "## Alpha Selection", ""])
    for row in alpha_summary.itertuples(index=False):
        lines.append(
            f"- {row.model_name}: selected alpha `{row.selected_alpha}` from mean inner-fold RMSE `{row.selected_alpha_mean_fold_rmse:.4f}`"
        )

    lines.extend(["", "## Validation Metrics", ""])
    for model_name, frame in metric_summary.groupby("model_name", sort=False):
        lines.append(f"- {model_name}:")
        for metric in frame.itertuples(index=False):
            lines.append(f"  {metric.metric_name} = `{metric.metric_value:.4f}`")

    lines.extend(["", "## Operational Coverage", ""])
    for row in future_latest.itertuples(index=False):
        lines.append(
            f"- {row.model_name}: target `{pd.Timestamp(row.target_month_start).date()}` from issue `{pd.Timestamp(row.init_month_start).date()}`"
        )

    (REPORTS_DIR / "model_a_v2_residual_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ensure_dirs()
    write_workspace_docs()
    copied_inputs = sync_inputs()

    monthly, future = load_inputs()
    climatology = build_monthly_climatology(monthly)
    historical = build_historical_operational_panel(monthly, climatology)
    future_all, future_latest = build_future_operational_panels(monthly, future, climatology)

    historical.to_csv(OUTPUTS_DIR / "model_a_v2_historical_panel.csv", index=False, encoding="utf-8-sig")
    future_all.to_csv(OUTPUTS_DIR / "model_a_v2_future_issue_target_panel.csv", index=False, encoding="utf-8-sig")
    future_latest.to_csv(OUTPUTS_DIR / "model_a_v2_future_latest_issue_panel.csv", index=False, encoding="utf-8-sig")

    split_rows: list[dict[str, object]] = []
    alpha_rows: list[dict[str, object]] = []
    coefficient_frames: list[pd.DataFrame] = []
    metric_frames: list[pd.DataFrame] = []
    validation_frames: list[pd.DataFrame] = []
    future_issue_frames: list[pd.DataFrame] = []
    future_latest_frames: list[pd.DataFrame] = []

    for model_name, spec in TARGET_SPECS.items():
        target_column = spec["target_column"]
        residual_target_column = f"{target_column}_residual_target"
        baseline_column = f"{target_column}_baseline_same_month_last_year"
        feature_columns = feature_columns_for_target(target_column)

        model_frame = historical[
            [
                "target_month_start",
                "target_year",
                "target_month",
                "issue_month_start",
                *feature_columns,
                residual_target_column,
                target_column,
            ]
        ].copy()
        model_frame = model_frame.dropna().reset_index(drop=True)

        selected_alpha, alpha_scoring = select_alpha(
            model_frame,
            feature_columns,
            residual_target_column,
            baseline_column,
        )

        training = model_frame[model_frame["target_year"] < FINAL_VALIDATION_YEAR].copy()
        validation = model_frame[model_frame["target_year"] == FINAL_VALIDATION_YEAR].copy()
        model = fit_ridge(training, feature_columns, residual_target_column, alpha=selected_alpha)

        residual_pred = model.predict(validation)
        predicted = np.clip(validation[baseline_column].to_numpy(dtype=float) + residual_pred, 0.0, None)
        validation_pred = validation[["target_month_start", "issue_month_start", "issue_month", "lead_month"]].copy()
        validation_pred["model_name"] = model_name
        validation_pred["target_label"] = spec["target_label"]
        validation_pred["observed_prevalence_per_100k"] = validation[target_column].to_numpy(dtype=float)
        validation_pred["baseline_prevalence_per_100k"] = validation[baseline_column].to_numpy(dtype=float)
        validation_pred["predicted_residual"] = residual_pred
        validation_pred["predicted_prevalence_per_100k"] = predicted
        validation_pred["residual"] = predicted - validation_pred["observed_prevalence_per_100k"]
        validation_frames.append(validation_pred)

        future_issue = future_all[
            ["init_month_start", "target_month_start", *feature_columns, "forecast_selection_rule"]
        ].copy()
        future_issue["model_name"] = model_name
        future_issue["target_label"] = spec["target_label"]
        future_issue["predicted_residual"] = model.predict(future_issue)
        future_issue["baseline_prevalence_per_100k"] = future_issue[baseline_column].to_numpy(dtype=float)
        future_issue["predicted_prevalence_per_100k"] = np.clip(
            future_issue["baseline_prevalence_per_100k"].to_numpy(dtype=float)
            + future_issue["predicted_residual"].to_numpy(dtype=float),
            0.0,
            None,
        )
        future_issue_frames.append(future_issue)

        future_latest_local = future_latest[
            ["init_month_start", "target_month_start", *feature_columns, "forecast_selection_rule"]
        ].copy()
        future_latest_local["model_name"] = model_name
        future_latest_local["target_label"] = spec["target_label"]
        future_latest_local["predicted_residual"] = model.predict(future_latest_local)
        future_latest_local["baseline_prevalence_per_100k"] = future_latest_local[baseline_column].to_numpy(dtype=float)
        future_latest_local["predicted_prevalence_per_100k"] = np.clip(
            future_latest_local["baseline_prevalence_per_100k"].to_numpy(dtype=float)
            + future_latest_local["predicted_residual"].to_numpy(dtype=float),
            0.0,
            None,
        )
        future_latest_frames.append(future_latest_local)

        split_rows.append(
            {
                "model_name": model_name,
                "training_years": ", ".join(str(value) for value in sorted(training["target_year"].unique())),
                "final_validation_year": FINAL_VALIDATION_YEAR,
                "training_row_count": int(len(training)),
                "final_validation_row_count": int(len(validation)),
            }
        )

        mean_alpha = (
            alpha_scoring[pd.to_numeric(alpha_scoring["validation_year"], errors="coerce").notna()]
            .groupby("alpha", as_index=False)["fold_rmse"]
            .mean()
            .sort_values(["fold_rmse", "alpha"], ascending=[True, True])
            .reset_index(drop=True)
        )
        selected_mean_rmse = float(
            mean_alpha.loc[mean_alpha["alpha"] == selected_alpha, "fold_rmse"].iloc[0]
        ) if not mean_alpha.empty else math.nan
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
    future_issue_predictions = pd.concat(future_issue_frames, ignore_index=True)
    future_latest_predictions = pd.concat(future_latest_frames, ignore_index=True)
    graph_table = build_graph_table(monthly, future_latest_predictions)

    split_summary.to_csv(OUTPUTS_DIR / "model_a_v2_validation_split_summary.csv", index=False, encoding="utf-8-sig")
    alpha_summary.to_csv(OUTPUTS_DIR / "model_a_v2_alpha_selection_summary.csv", index=False, encoding="utf-8-sig")
    metric_summary.to_csv(OUTPUTS_DIR / "model_a_v2_validation_metrics.csv", index=False, encoding="utf-8-sig")
    coefficients.to_csv(OUTPUTS_DIR / "model_a_v2_model_coefficients.csv", index=False, encoding="utf-8-sig")
    validation_predictions.to_csv(OUTPUTS_DIR / "model_a_v2_validation_predictions.csv", index=False, encoding="utf-8-sig")
    future_issue_predictions.to_csv(OUTPUTS_DIR / "model_a_v2_future_issue_target_predictions.csv", index=False, encoding="utf-8-sig")
    future_latest_predictions.to_csv(OUTPUTS_DIR / "model_a_v2_future_latest_issue_predictions.csv", index=False, encoding="utf-8-sig")
    graph_table.to_csv(OUTPUTS_DIR / "model_a_v2_graph_prevalence.csv", index=False, encoding="utf-8-sig")

    write_json(
        OUTPUTS_DIR / "model_a_v2_manifest.json",
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
        future_latest=future_latest_predictions,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
