from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from pipeline_utils import PROJECT_ROOT, timestamp_utc, write_json


PROCESSING_ROOT = PROJECT_ROOT / "data processing - copernicus_forecast_data"
OUTPUTS_ROOT = PROCESSING_ROOT / "outputs"
REPORTS_ROOT = PROCESSING_ROOT / "reports"
MODEL_A_OUTPUT_DIR = OUTPUTS_ROOT / "model_a"
MODEL_C_OUTPUT_DIR = OUTPUTS_ROOT / "model_c"
SHARED_METADATA_DIR = OUTPUTS_ROOT / "shared_metadata"

SLOVENIA_MONTHLY_PANEL = PROJECT_ROOT / "processed" / "slovenia" / "slovenia_monthly_predictive_panel.csv"
SLOVENIA_YEARLY_PANEL = PROJECT_ROOT / "processed" / "slovenia" / "slovenia_yearly_predictive_panel.csv"
MODEL_A_FILE_INDEX = MODEL_A_OUTPUT_DIR / "model_a_forecast_file_index.csv"
MODEL_A_COVERAGE = MODEL_A_OUTPUT_DIR / "model_a_forecast_coverage_summary.csv"
MODEL_C_YEARLY_WIDE = MODEL_C_OUTPUT_DIR / "model_c_slovenia_yearly_wide.csv"
MODEL_C_YEARLY_ANOMALIES = MODEL_C_OUTPUT_DIR / "model_c_slovenia_yearly_anomalies_vs_2016_2025.csv"

MONTHLY_TARGET_COLUMNS = [
    "lyme_cases",
    "kme_cases",
    "tick_borne_cases_total",
    "lyme_cases_per_100k",
    "kme_cases_per_100k",
    "tick_borne_cases_total_per_100k",
]

YEARLY_TARGET_COLUMNS = list(MONTHLY_TARGET_COLUMNS)

MODEL_A_FUTURE_COMPATIBLE_WEATHER = [
    "air_temperature_c_mean",
    "relative_humidity_pct_mean",
    "precipitation_sum_mm",
    "soil_temperature_level_1_c_mean",
]

MODEL_A_METADATA_COLUMNS = [
    "month_start",
    "year",
    "month",
    "month_end",
    "month_of_year_sin",
    "month_of_year_cos",
    "population_total",
    "population_density_per_km2",
]

MODEL_C_CLIMATE_COLUMNS = [
    "air_temperature_c_mean_climate",
    "near_surface_specific_humidity_g_kg_climate",
    "precipitation_sum_mm_proxy_climate",
    "soil_moisture_upper_portion_kg_m2_climate",
]

MODEL_C_ANOMALY_COLUMNS = [
    "air_temperature_c_mean_climate_anomaly_vs_2016_2025",
    "near_surface_specific_humidity_g_kg_climate_anomaly_vs_2016_2025",
    "precipitation_sum_mm_proxy_climate_anomaly_vs_2016_2025",
    "soil_moisture_upper_portion_kg_m2_climate_anomaly_vs_2016_2025",
]


def ensure_dirs() -> None:
    for path in [MODEL_A_OUTPUT_DIR, MODEL_C_OUTPUT_DIR, SHARED_METADATA_DIR, REPORTS_ROOT]:
        path.mkdir(parents=True, exist_ok=True)


def add_monthly_target_lags(df: pd.DataFrame) -> pd.DataFrame:
    data = df.sort_values("month_start").reset_index(drop=True).copy()
    for column in MONTHLY_TARGET_COLUMNS:
        for lag in [1, 2, 3, 6, 12]:
            data[f"{column}_lag_{lag}m"] = data[column].shift(lag)
        for window in [3, 6, 12]:
            data[f"{column}_rolling_{window}m_mean"] = (
                data[column].shift(1).rolling(window=window, min_periods=window).mean()
            )
    return data


def add_yearly_target_lags(df: pd.DataFrame) -> pd.DataFrame:
    data = df.sort_values("year").reset_index(drop=True).copy()
    for column in YEARLY_TARGET_COLUMNS:
        for lag in [1, 2, 3]:
            data[f"{column}_lag_{lag}y"] = data[column].shift(lag)
        data[f"{column}_rolling_3y_mean"] = (
            data[column].shift(1).rolling(window=3, min_periods=3).mean()
        )
    return data


def build_model_a_historical_backbone(monthly_df: pd.DataFrame) -> pd.DataFrame:
    data = monthly_df.copy()
    data["month_start"] = pd.to_datetime(data["month_start"])
    data["month_end"] = pd.to_datetime(data["month_end"])
    data = add_monthly_target_lags(data)
    keep_columns = (
        MODEL_A_METADATA_COLUMNS
        + MODEL_A_FUTURE_COMPATIBLE_WEATHER
        + [column for column in data.columns if "_lag_" in column or "_rolling_" in column]
        + MONTHLY_TARGET_COLUMNS
    )
    backbone = data[keep_columns].copy()
    backbone["table_role"] = "historical_training_backbone"
    return backbone.sort_values("month_start").reset_index(drop=True)


def build_model_a_operational_template(index_df: pd.DataFrame, coverage_df: pd.DataFrame) -> pd.DataFrame:
    data = index_df.copy()
    data["init_month_start"] = pd.to_datetime(data["init_month_start"])
    data["target_month_start"] = pd.to_datetime(data["target_month_start"])

    availability = (
        data.assign(file_available=True)
        .pivot_table(
            index=["init_month_start", "lead_month", "target_month_start", "target_year", "target_month"],
            columns="variable_family",
            values="file_available",
            aggfunc="max",
            fill_value=False,
        )
        .reset_index()
    )
    availability.columns.name = None

    file_paths = (
        data.pivot_table(
            index=["init_month_start", "lead_month", "target_month_start", "target_year", "target_month"],
            columns="variable_family",
            values="file_path",
            aggfunc="first",
        )
        .reset_index()
    )
    file_paths.columns.name = None
    file_paths = file_paths.rename(
        columns={
            "copernicus_temperature": "temperature_file_path",
            "copernicus_humidity": "humidity_file_path",
            "copernicus_precipitation": "precipitation_file_path",
            "copernicus_soil": "soil_file_path",
        }
    )

    template = availability.merge(
        file_paths,
        on=["init_month_start", "lead_month", "target_month_start", "target_year", "target_month"],
        how="left",
    )
    template = template.rename(
        columns={
            "copernicus_temperature": "has_temperature",
            "copernicus_humidity": "has_humidity",
            "copernicus_precipitation": "has_precipitation",
            "copernicus_soil": "has_soil",
        }
    )
    for column in ["has_temperature", "has_humidity", "has_precipitation", "has_soil"]:
        if column not in template.columns:
            template[column] = False
    template["all_required_families_available"] = (
        template["has_temperature"]
        & template["has_humidity"]
        & template["has_precipitation"]
        & template["has_soil"]
    )
    template["issue_year"] = template["init_month_start"].dt.year
    template["issue_month"] = template["init_month_start"].dt.month
    template["target_month_of_year_sin"] = template["target_month"].map(
        lambda value: math.sin((2.0 * math.pi * value) / 12.0)
    )
    template["target_month_of_year_cos"] = template["target_month"].map(
        lambda value: math.cos((2.0 * math.pi * value) / 12.0)
    )
    template["table_role"] = "future_operational_template"
    template["latest_observed_month_available"] = pd.Timestamp("2025-12-01")
    template["grib_value_extraction_ready"] = False
    template["notes"] = (
        "Forecast file paths and family coverage are ready. Numeric weather values still await GRIB extraction."
    )

    coverage_map = coverage_df.set_index("variable_family")["historical_window_target_rows"].to_dict()
    template["historical_backtest_support_temperature"] = int(
        coverage_map.get("copernicus_temperature", 0)
    )
    template["historical_backtest_support_humidity"] = int(
        coverage_map.get("copernicus_humidity", 0)
    )
    template["historical_backtest_support_precipitation"] = int(
        coverage_map.get("copernicus_precipitation", 0)
    )
    template["historical_backtest_support_soil"] = int(
        coverage_map.get("copernicus_soil", 0)
    )
    return template.sort_values(["init_month_start", "lead_month"]).reset_index(drop=True)


def split_model_a_operational_tables(template: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = template.copy()
    data["target_month_start"] = pd.to_datetime(data["target_month_start"])
    future = data[data["target_month_start"] >= pd.Timestamp("2026-01-01")].copy()
    future["table_scope"] = "future_operational"
    backtest = data[data["target_month_start"] < pd.Timestamp("2026-01-01")].copy()
    backtest["table_scope"] = "historical_backtest_support"
    return (
        future.sort_values(["init_month_start", "lead_month"]).reset_index(drop=True),
        backtest.sort_values(["init_month_start", "lead_month"]).reset_index(drop=True),
    )


def build_model_c_observed_reference(yearly_df: pd.DataFrame) -> pd.DataFrame:
    data = yearly_df.copy()
    data = add_yearly_target_lags(data)
    keep_columns = [
        "year",
        "year_start",
        "year_end",
        "population_total",
        "population_density_per_km2",
        "air_temperature_c_mean",
        "relative_humidity_pct_mean",
        "precipitation_sum_mm",
        "soil_water_layer_1_m3_m3_mean",
    ] + [column for column in data.columns if "_lag_" in column or "_rolling_" in column] + YEARLY_TARGET_COLUMNS
    reference = data[keep_columns].copy()
    reference["table_role"] = "observed_yearly_reference"
    return reference.sort_values("year").reset_index(drop=True)


def build_model_c_scenario_tables(
    observed_reference: pd.DataFrame,
    yearly_wide: pd.DataFrame,
    yearly_anomalies: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    climate = yearly_wide.copy()
    anomalies = yearly_anomalies.copy()

    for frame in [climate, anomalies]:
        if "scenario_family" in frame.columns:
            frame["scenario_family"] = frame["scenario_family"].astype(str)
        if "year" in frame.columns:
            frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype(int)

    joined = climate.merge(
        anomalies[["scenario_family", "year", *MODEL_C_ANOMALY_COLUMNS]],
        on=["scenario_family", "year"],
        how="left",
    )

    observed_targets = observed_reference[["year", *YEARLY_TARGET_COLUMNS] + [column for column in observed_reference.columns if "_lag_" in column or "_rolling_" in column]]

    calibration = joined[(joined["scenario_family"].isin(["medium_emissions", "high_emissions"])) & (joined["year"].between(2016, 2025))].copy()
    calibration = calibration.merge(observed_targets, on="year", how="left")
    calibration["table_role"] = "scenario_calibration"
    calibration["target_available"] = calibration["kme_cases"].notna()

    projection = joined[(joined["scenario_family"].isin(["medium_emissions", "high_emissions"])) & (joined["year"] >= 2026)].copy()
    for column in YEARLY_TARGET_COLUMNS + [column for column in observed_targets.columns if column not in {"year", *YEARLY_TARGET_COLUMNS}]:
        if column != "year":
            projection[column] = pd.NA
    projection["table_role"] = "scenario_projection"
    projection["target_available"] = False
    projection["projection_horizon_years_from_2025"] = projection["year"] - 2025

    calibration = calibration.sort_values(["scenario_family", "year"]).reset_index(drop=True)
    projection = projection.sort_values(["scenario_family", "year"]).reset_index(drop=True)
    return calibration, projection


def write_report(
    *,
    model_a_backbone: pd.DataFrame,
    model_a_future_template: pd.DataFrame,
    model_a_backtest_template: pd.DataFrame,
    model_c_reference: pd.DataFrame,
    model_c_calibration: pd.DataFrame,
    model_c_projection: pd.DataFrame,
) -> None:
    lines = [
        "# Predictive Model Table Assembly",
        "",
        f"- generated at: `{timestamp_utc()}`",
        "",
        "## Model A",
        "",
        f"- historical backbone rows: `{len(model_a_backbone)}`",
        f"- future operational template rows: `{len(model_a_future_template)}`",
        f"- historical backtest-support template rows: `{len(model_a_backtest_template)}`",
        f"- future rows with all required forecast families available: `{int(model_a_future_template['all_required_families_available'].sum())}`",
        "- Model A is not fitted yet.",
        "- The historical backbone is ready for feature design and target definition.",
        "- The operational template is ready for forecast-file joins, but numeric future weather extraction is still pending GRIB runtime support.",
        "",
        "## Model C",
        "",
        f"- observed yearly reference rows: `{len(model_c_reference)}`",
        f"- scenario calibration rows: `{len(model_c_calibration)}`",
        f"- scenario projection rows: `{len(model_c_projection)}`",
        "- Model C is not fitted yet.",
        "- The calibration table already pairs scenario-consistent climate features with observed yearly disease targets for 2016-2025.",
        "- The projection table continues the same feature schema into future years.",
        "",
    ]
    (REPORTS_ROOT / "predictive_model_table_assembly_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ensure_dirs()

    slovenia_monthly = pd.read_csv(SLOVENIA_MONTHLY_PANEL, encoding="utf-8-sig")
    slovenia_yearly = pd.read_csv(SLOVENIA_YEARLY_PANEL, encoding="utf-8-sig")
    model_a_index = pd.read_csv(MODEL_A_FILE_INDEX, encoding="utf-8-sig")
    model_a_coverage = pd.read_csv(MODEL_A_COVERAGE, encoding="utf-8-sig")
    model_c_yearly_wide = pd.read_csv(MODEL_C_YEARLY_WIDE, encoding="utf-8-sig")
    model_c_yearly_anomalies = pd.read_csv(MODEL_C_YEARLY_ANOMALIES, encoding="utf-8-sig")

    model_a_backbone = build_model_a_historical_backbone(slovenia_monthly)
    model_a_template_all = build_model_a_operational_template(model_a_index, model_a_coverage)
    model_a_future_template, model_a_backtest_template = split_model_a_operational_tables(
        model_a_template_all
    )
    model_c_reference = build_model_c_observed_reference(slovenia_yearly)
    model_c_calibration, model_c_projection = build_model_c_scenario_tables(
        model_c_reference,
        model_c_yearly_wide,
        model_c_yearly_anomalies,
    )

    model_a_backbone.to_csv(
        MODEL_A_OUTPUT_DIR / "model_a_historical_training_backbone.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_a_future_template.to_csv(
        MODEL_A_OUTPUT_DIR / "model_a_future_operational_template.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_a_backtest_template.to_csv(
        MODEL_A_OUTPUT_DIR / "model_a_backtest_support_template.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_c_reference.to_csv(
        MODEL_C_OUTPUT_DIR / "model_c_observed_reference_yearly.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_c_calibration.to_csv(
        MODEL_C_OUTPUT_DIR / "model_c_scenario_calibration_table.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_c_projection.to_csv(
        MODEL_C_OUTPUT_DIR / "model_c_scenario_projection_table.csv",
        index=False,
        encoding="utf-8-sig",
    )

    manifest = {
        "generated_at_utc": timestamp_utc(),
        "inputs": {
            "slovenia_monthly_panel": str(SLOVENIA_MONTHLY_PANEL),
            "slovenia_yearly_panel": str(SLOVENIA_YEARLY_PANEL),
            "model_a_file_index": str(MODEL_A_FILE_INDEX),
            "model_a_coverage": str(MODEL_A_COVERAGE),
            "model_c_yearly_wide": str(MODEL_C_YEARLY_WIDE),
            "model_c_yearly_anomalies": str(MODEL_C_YEARLY_ANOMALIES),
        },
        "outputs": {
            "model_a_historical_training_backbone": str(
                MODEL_A_OUTPUT_DIR / "model_a_historical_training_backbone.csv"
            ),
            "model_a_future_operational_template": str(
                MODEL_A_OUTPUT_DIR / "model_a_future_operational_template.csv"
            ),
            "model_a_backtest_support_template": str(
                MODEL_A_OUTPUT_DIR / "model_a_backtest_support_template.csv"
            ),
            "model_c_observed_reference_yearly": str(
                MODEL_C_OUTPUT_DIR / "model_c_observed_reference_yearly.csv"
            ),
            "model_c_scenario_calibration_table": str(
                MODEL_C_OUTPUT_DIR / "model_c_scenario_calibration_table.csv"
            ),
            "model_c_scenario_projection_table": str(
                MODEL_C_OUTPUT_DIR / "model_c_scenario_projection_table.csv"
            ),
            "assembly_report_md": str(REPORTS_ROOT / "predictive_model_table_assembly_report.md"),
        },
        "counts": {
            "model_a_historical_training_backbone_rows": int(len(model_a_backbone)),
            "model_a_future_operational_template_rows": int(len(model_a_future_template)),
            "model_a_backtest_support_template_rows": int(len(model_a_backtest_template)),
            "model_c_observed_reference_yearly_rows": int(len(model_c_reference)),
            "model_c_scenario_calibration_rows": int(len(model_c_calibration)),
            "model_c_scenario_projection_rows": int(len(model_c_projection)),
        },
    }
    write_json(
        SHARED_METADATA_DIR / "predictive_model_table_manifest.json",
        manifest,
    )
    write_report(
        model_a_backbone=model_a_backbone,
        model_a_future_template=model_a_future_template,
        model_a_backtest_template=model_a_backtest_template,
        model_c_reference=model_c_reference,
        model_c_calibration=model_c_calibration,
        model_c_projection=model_c_projection,
    )

    print("Predictive model tables built successfully.")
    print(f"- Model A historical backbone rows: {len(model_a_backbone)}")
    print(f"- Model A future template rows: {len(model_a_future_template)}")
    print(f"- Model A backtest-support template rows: {len(model_a_backtest_template)}")
    print(f"- Model C calibration rows: {len(model_c_calibration)}")
    print(f"- Model C projection rows: {len(model_c_projection)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
