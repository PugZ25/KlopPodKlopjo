from __future__ import annotations

import calendar
import importlib.util
import math
import re
import shutil
import zipfile
from pathlib import Path

import pandas as pd
import xarray as xr

from build_predictive_panels import CASE_COLUMNS
from pipeline_utils import (
    CLIMATE_ATLAS_RAW_DIR,
    FORECAST_RAW_DIR,
    PROJECT_ROOT,
    SLOVENIA_MONTHLY_PANEL_OUTPUT,
    SLOVENIA_YEARLY_PANEL_OUTPUT,
    timestamp_utc,
    write_json,
)
from run_model_a_slovenia_partitioned_download import VARIABLE_FAMILY_MAP
from run_model_c_climate_chunked_download import CHUNK_PLAN, target_path_for_chunk


PROCESSING_ROOT = PROJECT_ROOT / "data processing - copernicus_forecast_data"
SHARED_DIR = PROCESSING_ROOT / "shared"
REPORTS_DIR = PROCESSING_ROOT / "reports"
OUTPUTS_DIR = PROCESSING_ROOT / "outputs"
MODEL_A_OUTPUT_DIR = OUTPUTS_DIR / "model_a"
MODEL_C_OUTPUT_DIR = OUTPUTS_DIR / "model_c"
SHARED_METADATA_DIR = OUTPUTS_DIR / "shared_metadata"
TMP_DIR = REPORTS_DIR / "_tmp_extract"

MODEL_A_FILE_PATTERN = re.compile(
    r"seasonal-monthly-single-levels_ecmwf_system_(?P<system>\d+)_"
    r"(?P<family>copernicus_[a-z_]+)_init_(?P<year>\d{4})_(?P<month>\d{2})_"
    r"lead_(?P<lead_min>\d+)-(?P<lead_max>\d+)(?:_rawvar_(?P<raw_variable>[a-z0-9_]+))?\.grib$"
)

MODEL_A_RAW_VARIABLE_TO_HISTORICAL_FEATURES = {
    "2m_temperature": ["air_temperature_c_mean"],
    "2m_dewpoint_temperature": ["relative_humidity_pct_mean"],
    "total_precipitation": ["precipitation_sum_mm"],
    "soil_temperature_level_1": ["soil_temperature_level_1_c_mean"],
    "soil_temperature_level_2": ["soil_temperature_level_2_c_mean"],
    "volumetric_soil_water_layer_1": ["soil_water_layer_1_m3_m3_mean"],
    "volumetric_soil_water_layer_2": ["soil_water_layer_2_m3_m3_mean"],
}

MODEL_A_FAMILY_DETAILS = {
    "copernicus_temperature": {
        "historical_reference_features": ["air_temperature_c_mean"],
        "match_status": "direct_match",
        "transformation": "Use monthly mean 2m temperature directly after GRIB parsing.",
        "notes": "The monthly seasonal product supports the mean temperature backbone only, not min/max/std.",
    },
    "copernicus_humidity": {
        "historical_reference_features": ["relative_humidity_pct_mean"],
        "match_status": "derived_match",
        "transformation": (
            "Derive monthly mean relative humidity from monthly mean 2m temperature and "
            "monthly mean 2m dewpoint temperature after GRIB parsing."
        ),
        "notes": "Humidity min/max and humidity-hour counts are not available from the monthly mean product.",
    },
    "copernicus_precipitation": {
        "historical_reference_features": ["precipitation_sum_mm"],
        "match_status": "direct_match_pending_unit_validation",
        "transformation": (
            "Validate seasonal total_precipitation units, then convert to a monthly precipitation sum analogue."
        ),
        "notes": "Extreme precipitation and wet-hour features are not available from the monthly mean product.",
    },
    "copernicus_soil": {
        "historical_reference_features": ["soil_temperature_level_1_c_mean"],
        "match_status": "direct_match",
        "transformation": (
            "Use monthly mean soil temperature level 1 directly after GRIB parsing. "
            "The current monthly seasonal CDS product does not expose the deeper soil temperature "
            "or volumetric soil-water layers under this acquisition strategy."
        ),
        "notes": (
            "The current monthly seasonal CDS soil request supports soil temperature level 1 only "
            "for the reproducible Slovenia monthly-stats pipeline."
        ),
    },
}

MODEL_C_VARIABLE_CONFIG = {
    "monthly_temperature": {
        "var_code": "t",
        "historical_reference_feature": "air_temperature_c_mean",
        "output_feature": "air_temperature_c_mean_climate",
        "match_status": "direct_match",
        "aggregation": "mean",
        "transform": "identity",
        "output_units": "degC",
        "notes": "Direct climate analogue for historical monthly mean temperature.",
    },
    "monthly_precipitation": {
        "var_code": "r",
        "historical_reference_feature": "precipitation_sum_mm",
        "output_feature": "precipitation_sum_mm_proxy_climate",
        "match_status": "proxy_match",
        "aggregation": "sum",
        "transform": "multiply_by_days_in_month",
        "output_units": "mm/month proxy",
        "notes": (
            "Atlas precipitation is stored as monthly mean of daily accumulated precipitation. "
            "Multiply by days in month to approximate a monthly total comparable to the historical panel."
        ),
    },
    "monthly_near_surface_specific_humidity": {
        "var_code": "huss",
        "historical_reference_feature": "relative_humidity_pct_mean",
        "output_feature": "near_surface_specific_humidity_g_kg_climate",
        "match_status": "proxy_match",
        "aggregation": "mean",
        "transform": "identity",
        "output_units": "g kg-1",
        "notes": "Specific humidity is the closest long-range humidity analogue, but it is not the same measure as relative humidity.",
    },
    "monthly_soil_moisture_in_upper_soil_portion": {
        "var_code": "mrsos",
        "historical_reference_feature": "soil_water_layer_1_m3_m3_mean",
        "output_feature": "soil_moisture_upper_portion_kg_m2_climate",
        "match_status": "proxy_match",
        "aggregation": "mean",
        "transform": "identity",
        "output_units": "kg m-2",
        "notes": "Upper-soil moisture is the closest climate analogue for the historical soil-water backbone.",
    },
}

MODEL_C_SCENARIO_FAMILY = {
    "historical": "historical",
    "rcp_4_5": "medium_emissions",
    "ssp2_4_5": "medium_emissions",
    "rcp_8_5": "high_emissions",
    "ssp5_8_5": "high_emissions",
}

STATIC_OR_METADATA_COLUMNS = {
    "municipality_area_m2",
    "grid_cell_count",
    "overlay_method",
    "elevation_m_mean",
    "elevation_m_std",
    "elevation_m_range",
    "population_total",
    "population_density_per_km2",
    "population_source_year",
    "dominant_clc_code",
    "dominant_clc_label",
    "dominant_clc_cover_pct",
    "urban_cover_pct",
    "agricultural_cover_pct",
    "grassland_pasture_cover_pct",
    "forest_cover_pct",
    "broad_leaved_forest_cover_pct",
    "coniferous_forest_cover_pct",
    "mixed_forest_cover_pct",
    "shrub_transitional_cover_pct",
    "open_bare_cover_pct",
    "wetland_cover_pct",
    "water_cover_pct",
    "municipality_count",
}

TIME_OR_TARGET_COLUMNS = {
    "month_start",
    "year",
    "month",
    "month_end",
    "month_of_year_sin",
    "month_of_year_cos",
    "lyme_cases",
    "kme_cases",
    "tick_borne_cases_total",
    "lyme_cases_per_100k",
    "kme_cases_per_100k",
    "tick_borne_cases_total_per_100k",
}


def ensure_dirs() -> None:
    for path in [
        PROCESSING_ROOT,
        SHARED_DIR,
        REPORTS_DIR,
        OUTPUTS_DIR,
        MODEL_A_OUTPUT_DIR,
        MODEL_C_OUTPUT_DIR,
        SHARED_METADATA_DIR,
        TMP_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


MODEL_A_DIRECT_FEATURES = {
    "air_temperature_c_mean": ("copernicus_temperature", "direct_match"),
    "relative_humidity_pct_mean": ("copernicus_humidity", "derived_match"),
    "precipitation_sum_mm": ("copernicus_precipitation", "direct_match_pending_unit_validation"),
    "soil_temperature_level_1_c_mean": ("copernicus_soil", "direct_match"),
}

MODEL_A_REDUCED_OR_UNAVAILABLE = {
    "air_temperature_c_min": "unavailable_without_daily_or_subdaily_forecast_data",
    "air_temperature_c_max": "unavailable_without_daily_or_subdaily_forecast_data",
    "air_temperature_c_std": "unavailable_without_daily_or_subdaily_forecast_data",
    "relative_humidity_pct_min": "unavailable_without_daily_or_subdaily_forecast_data",
    "relative_humidity_pct_max": "unavailable_without_daily_or_subdaily_forecast_data",
    "air_temperature_c_range": "unavailable_without_daily_or_subdaily_forecast_data",
    "covered_area_pct": "not_a_future_predictor",
    "observation_days_count": "not_a_future_predictor",
    "humidity_hours_ge_80_sum": "unavailable_without_hourly_forecast_data",
    "humidity_hours_ge_90_sum": "unavailable_without_hourly_forecast_data",
    "wet_hours_ge_0_1mm_sum": "unavailable_without_hourly_forecast_data",
    "tick_activity_window_hours_sum": "unavailable_without_hourly_forecast_data",
    "growing_degree_hours_base_5_c_sum": "unavailable_without_hourly_forecast_data",
    "rainy_days_ge_1mm_count": "unavailable_without_daily_forecast_data",
    "humid_days_ge_16h_count": "unavailable_without_daily_or_hourly_forecast_data",
    "tick_favorable_days_ge_6h_count": "unavailable_without_daily_or_hourly_forecast_data",
    "precipitation_daily_max_mm": "unavailable_without_daily_forecast_data",
    "soil_temperature_level_2_c_mean": "unavailable_in_current_monthly_stats_dataset",
    "soil_water_layer_1_m3_m3_mean": "unavailable_in_current_monthly_stats_dataset",
    "soil_water_layer_2_m3_m3_mean": "unavailable_in_current_monthly_stats_dataset",
}

MODEL_C_DIRECT_OR_PROXY = {
    "air_temperature_c_mean": ("monthly_temperature", "direct_match"),
    "precipitation_sum_mm": ("monthly_precipitation", "proxy_match"),
    "relative_humidity_pct_mean": ("monthly_near_surface_specific_humidity", "proxy_match"),
    "soil_water_layer_1_m3_m3_mean": ("monthly_soil_moisture_in_upper_soil_portion", "proxy_match"),
}

MODEL_C_UNAVAILABLE = {
    "air_temperature_c_min": "requires an additional Atlas minimum-temperature variable such as tn",
    "air_temperature_c_max": "requires an additional Atlas maximum-temperature variable such as tx",
    "air_temperature_c_std": "not available in the current first-pass Atlas package",
    "relative_humidity_pct_min": "not available from the current first-pass Atlas package",
    "relative_humidity_pct_max": "not available from the current first-pass Atlas package",
    "soil_temperature_level_1_c_mean": "no direct Atlas soil-temperature variable in the current package",
    "soil_temperature_level_2_c_mean": "no direct Atlas soil-temperature variable in the current package",
    "soil_water_layer_2_m3_m3_mean": "no direct second-layer analogue in the current package",
    "air_temperature_c_range": "requires separate minimum and maximum temperature products",
    "covered_area_pct": "not a future climate predictor",
    "observation_days_count": "not a future climate predictor",
    "humidity_hours_ge_80_sum": "not available from monthly climate means",
    "humidity_hours_ge_90_sum": "not available from monthly climate means",
    "wet_hours_ge_0_1mm_sum": "not available from monthly climate means",
    "tick_activity_window_hours_sum": "not available from monthly climate means",
    "growing_degree_hours_base_5_c_sum": "not available in the current first-pass package",
    "rainy_days_ge_1mm_count": "requires an additional wet-days Atlas variable such as r01",
    "humid_days_ge_16h_count": "not available from monthly climate means",
    "tick_favorable_days_ge_6h_count": "not available from monthly climate means",
    "precipitation_daily_max_mm": "requires an additional Atlas extremes variable such as rx1day",
}


def build_dependency_rows(slovenia_monthly_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for column in slovenia_monthly_columns:
        row = {
            "historical_panel_column": column,
            "column_group": "other",
            "model_a_status": "",
            "model_a_source": "",
            "model_a_transformation": "",
            "model_c_status": "",
            "model_c_source": "",
            "model_c_transformation": "",
            "notes": "",
        }

        if column in TIME_OR_TARGET_COLUMNS:
            row["column_group"] = "time_or_target"
            row["model_a_status"] = "reused_from_historical_panel_or_recomputed"
            row["model_c_status"] = "reused_from_historical_panel_or_recomputed"
            if column in CASE_COLUMNS or column.endswith("_per_100k"):
                row["notes"] = "Target or disease-history field, not a future weather download."
            else:
                row["notes"] = "Calendar field recomputed from the target month or year."
        elif column in STATIC_OR_METADATA_COLUMNS:
            row["column_group"] = "static_or_metadata"
            row["model_a_status"] = "fixed_metadata"
            row["model_c_status"] = "fixed_metadata"
            row["notes"] = "Keep as fixed Slovenia-level metadata or drop later if it is constant."
        elif column in MODEL_A_DIRECT_FEATURES:
            family, status = MODEL_A_DIRECT_FEATURES[column]
            row["column_group"] = "environmental_dynamic"
            row["model_a_status"] = status
            row["model_a_source"] = family
            row["model_a_transformation"] = MODEL_A_FAMILY_DETAILS[family]["transformation"]
            if column in MODEL_C_DIRECT_OR_PROXY:
                model_c_variable, model_c_status = MODEL_C_DIRECT_OR_PROXY[column]
                row["model_c_status"] = model_c_status
                row["model_c_source"] = model_c_variable
                row["model_c_transformation"] = MODEL_C_VARIABLE_CONFIG[model_c_variable]["notes"]
            else:
                row["model_c_status"] = MODEL_C_UNAVAILABLE.get(column, "not_in_first_pass_package")
        elif column in MODEL_A_REDUCED_OR_UNAVAILABLE:
            row["column_group"] = "environmental_dynamic"
            row["model_a_status"] = MODEL_A_REDUCED_OR_UNAVAILABLE[column]
            row["model_c_status"] = MODEL_C_UNAVAILABLE.get(column, "not_in_first_pass_package")
        elif column in MODEL_C_DIRECT_OR_PROXY:
            model_c_variable, model_c_status = MODEL_C_DIRECT_OR_PROXY[column]
            row["column_group"] = "environmental_dynamic"
            row["model_a_status"] = MODEL_A_REDUCED_OR_UNAVAILABLE.get(column, "not_in_first_pass_package")
            row["model_c_status"] = model_c_status
            row["model_c_source"] = model_c_variable
            row["model_c_transformation"] = MODEL_C_VARIABLE_CONFIG[model_c_variable]["notes"]
        else:
            row["notes"] = "Column not classified by the first-pass dependency map."

        rows.append(row)
    return pd.DataFrame(rows)


def build_model_a_file_index(
    slovenia_monthly_df: pd.DataFrame,
    *,
    grib_parser_ready: bool,
) -> pd.DataFrame:
    monthly_min = pd.to_datetime(slovenia_monthly_df["month_start"]).min()
    monthly_max = pd.to_datetime(slovenia_monthly_df["month_start"]).max()
    rows: list[dict[str, object]] = []

    for family_dir in sorted(FORECAST_RAW_DIR.iterdir()):
        if not family_dir.is_dir():
            continue
        family = family_dir.name
        dataset_dir = family_dir / "seasonal-monthly-single-levels"
        if not dataset_dir.exists():
            continue
        config = MODEL_A_FAMILY_DETAILS.get(family)
        if config is None:
            continue
        parsed_files: list[dict[str, object]] = []
        for path in sorted(dataset_dir.glob("*.grib")):
            match = MODEL_A_FILE_PATTERN.match(path.name)
            if not match:
                continue
            parsed_files.append(
                {
                    "path": path,
                    "match": match,
                    "raw_variable": match.group("raw_variable"),
                }
            )

        split_file_keys = {
            (
                item["match"].group("system"),
                item["match"].group("year"),
                item["match"].group("month"),
                item["match"].group("lead_min"),
                item["match"].group("lead_max"),
            )
            for item in parsed_files
            if item["raw_variable"]
        }

        for item in parsed_files:
            path = item["path"]
            match = item["match"]
            raw_variable_name = item["raw_variable"]
            file_key = (
                match.group("system"),
                match.group("year"),
                match.group("month"),
                match.group("lead_min"),
                match.group("lead_max"),
            )
            if raw_variable_name is None and file_key in split_file_keys:
                continue

            init_year = int(match.group("year"))
            init_month = int(match.group("month"))
            lead_min = int(match.group("lead_min"))
            lead_max = int(match.group("lead_max"))
            init_month_start = pd.Timestamp(year=init_year, month=init_month, day=1)
            requested_raw_variables = (
                [raw_variable_name]
                if raw_variable_name is not None
                else list(VARIABLE_FAMILY_MAP[family])
            )
            historical_reference_features = (
                MODEL_A_RAW_VARIABLE_TO_HISTORICAL_FEATURES.get(
                    raw_variable_name,
                    config["historical_reference_features"],
                )
                if raw_variable_name is not None
                else config["historical_reference_features"]
            )
            for lead_month in range(lead_min, lead_max + 1):
                target_month_start = init_month_start + pd.DateOffset(months=lead_month)
                rows.append(
                    {
                        "variable_family": family,
                        "request_mode": "split_file" if raw_variable_name is not None else "combined_file",
                        "raw_variable_name": raw_variable_name or "",
                        "requested_raw_variables": "; ".join(requested_raw_variables),
                        "historical_reference_features": "; ".join(historical_reference_features),
                        "match_status": config["match_status"],
                        "init_year": init_year,
                        "init_month": init_month,
                        "init_month_start": init_month_start.date().isoformat(),
                        "lead_month": lead_month,
                        "target_year": int(target_month_start.year),
                        "target_month": int(target_month_start.month),
                        "target_month_start": target_month_start.date().isoformat(),
                        "target_in_historical_panel_window": bool(
                            monthly_min <= target_month_start <= monthly_max
                        ),
                        "value_extraction_status": (
                            "ready_to_parse" if grib_parser_ready else "pending_grib_parser_dependency"
                        ),
                        "transformation_rule": config["transformation"],
                        "notes": config["notes"],
                        "file_path": str(path),
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["variable_family", "init_year", "init_month", "lead_month"]
    ).reset_index(drop=True)


def extract_netcdf_path(zip_path: Path, extract_root: Path) -> Path:
    extract_dir = extract_root / zip_path.stem
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        nc_names = [name for name in archive.namelist() if name.endswith(".nc")]
        if len(nc_names) != 1:
            raise ValueError(f"Expected exactly one .nc inside {zip_path}, found {nc_names}")
        nc_name = nc_names[0]
        archive.extract(nc_name, extract_dir)
    return extract_dir / nc_name


def scenario_family(experiment: str) -> str:
    return MODEL_C_SCENARIO_FAMILY.get(experiment, experiment)


def apply_transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "identity":
        return series.astype(float)
    if transform == "multiply_by_days_in_month":
        factors = series.index.to_series().map(lambda dt: calendar.monthrange(dt.year, dt.month)[1])
        return series.astype(float) * factors.to_numpy()
    raise ValueError(f"Unsupported transform: {transform}")


def build_model_c_monthly_long() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for chunk in CHUNK_PLAN:
        zip_path = target_path_for_chunk(chunk)
        if not zip_path.exists():
            continue

        variable_name = chunk["variable"]
        config = MODEL_C_VARIABLE_CONFIG[variable_name]
        nc_path = extract_netcdf_path(zip_path, TMP_DIR)
        ds = xr.open_dataset(nc_path)
        try:
            field = ds[config["var_code"]]
            spatial_dims = [dim for dim in ("lat", "lon") if dim in field.dims]
            member_dim = "member" if "member" in field.dims else None
            spatial_cell_count = 1
            for dim in spatial_dims:
                spatial_cell_count *= int(field.sizes[dim])
            if spatial_dims:
                field = field.mean(dim=spatial_dims, skipna=True)

            if member_dim is None:
                field = field.expand_dims(member=["member_1"])
                member_dim = "member"

            mean_series = field.mean(dim=member_dim).to_series()
            median_series = field.median(dim=member_dim).to_series()
            p10_series = field.quantile(0.10, dim=member_dim).to_series()
            p90_series = field.quantile(0.90, dim=member_dim).to_series()

            mean_series = apply_transform(mean_series, config["transform"])
            median_series = apply_transform(median_series, config["transform"])
            p10_series = apply_transform(p10_series, config["transform"])
            p90_series = apply_transform(p90_series, config["transform"])

            monthly = pd.DataFrame(
                {
                    "month_start": pd.to_datetime(mean_series.index),
                    "value_mean": mean_series.to_numpy(),
                    "value_median": median_series.to_numpy(),
                    "value_p10": p10_series.to_numpy(),
                    "value_p90": p90_series.to_numpy(),
                }
            )
            monthly["year"] = monthly["month_start"].dt.year
            monthly["month"] = monthly["month_start"].dt.month
            monthly["month_of_year_sin"] = monthly["month"].map(
                lambda value: math.sin((2.0 * math.pi * value) / 12.0)
            )
            monthly["month_of_year_cos"] = monthly["month"].map(
                lambda value: math.cos((2.0 * math.pi * value) / 12.0)
            )
            monthly["origin"] = chunk["origin"]
            monthly["domain"] = chunk["domain"]
            monthly["experiment"] = chunk["experiment"]
            monthly["scenario_family"] = scenario_family(chunk["experiment"])
            monthly["period"] = chunk["period"]
            monthly["variable_name"] = variable_name
            monthly["variable_code"] = config["var_code"]
            monthly["historical_reference_feature"] = config["historical_reference_feature"]
            monthly["output_feature"] = config["output_feature"]
            monthly["match_status"] = config["match_status"]
            monthly["output_units"] = config["output_units"]
            monthly["aggregation_rule"] = config["aggregation"]
            monthly["member_count"] = int(ds.sizes.get("member", 1))
            monthly["spatial_cell_count"] = spatial_cell_count
            monthly["source_zip_path"] = str(zip_path)
            monthly["notes"] = config["notes"]
            rows.append(monthly)
        finally:
            ds.close()
            shutil.rmtree(nc_path.parent, ignore_errors=True)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).sort_values(
        ["scenario_family", "origin", "variable_name", "month_start"]
    ).reset_index(drop=True)


def build_model_c_yearly_long(monthly_long: pd.DataFrame) -> pd.DataFrame:
    if monthly_long.empty:
        return pd.DataFrame()

    yearly_frames: list[pd.DataFrame] = []
    group_cols = [
        "origin",
        "domain",
        "experiment",
        "scenario_family",
        "period",
        "variable_name",
        "variable_code",
        "historical_reference_feature",
        "output_feature",
        "match_status",
        "output_units",
        "aggregation_rule",
        "member_count",
        "spatial_cell_count",
        "source_zip_path",
        "notes",
        "year",
    ]

    for _, frame in monthly_long.groupby(
        [
            "origin",
            "domain",
            "experiment",
            "scenario_family",
            "period",
            "variable_name",
            "year",
        ],
        sort=True,
    ):
        meta = frame.iloc[0].to_dict()
        if meta["aggregation_rule"] == "sum":
            agg = frame[["value_mean", "value_median", "value_p10", "value_p90"]].sum()
        else:
            agg = frame[["value_mean", "value_median", "value_p10", "value_p90"]].mean()

        yearly_frames.append(
            pd.DataFrame(
                [
                    {
                        **{col: meta[col] for col in group_cols},
                        "year_start": f"{int(meta['year'])}-01-01",
                        "year_end": f"{int(meta['year'])}-12-31",
                        "value_mean": float(agg["value_mean"]),
                        "value_median": float(agg["value_median"]),
                        "value_p10": float(agg["value_p10"]),
                        "value_p90": float(agg["value_p90"]),
                    }
                ]
            )
        )

    return pd.concat(yearly_frames, ignore_index=True).sort_values(
        ["scenario_family", "origin", "variable_name", "year"]
    ).reset_index(drop=True)


def build_model_c_wide(table: pd.DataFrame, *, time_key: str) -> pd.DataFrame:
    if table.empty:
        return pd.DataFrame()
    wide = (
        table.pivot_table(
            index=["scenario_family", time_key],
            columns="output_feature",
            values="value_mean",
            aggfunc="first",
        )
        .reset_index()
        .sort_values(["scenario_family", time_key])
        .reset_index(drop=True)
    )
    if time_key == "month_start":
        wide["month_start"] = pd.to_datetime(wide["month_start"])
        wide["year"] = wide["month_start"].dt.year
        wide["month"] = wide["month_start"].dt.month
        wide["month_of_year_sin"] = wide["month"].map(
            lambda value: math.sin((2.0 * math.pi * value) / 12.0)
        )
        wide["month_of_year_cos"] = wide["month"].map(
            lambda value: math.cos((2.0 * math.pi * value) / 12.0)
        )
    return wide


def build_model_c_yearly_anomalies(yearly_wide: pd.DataFrame) -> pd.DataFrame:
    if yearly_wide.empty:
        return pd.DataFrame()
    feature_columns = [
        column
        for column in yearly_wide.columns
        if column.endswith("_climate") or column.endswith("_proxy_climate")
    ]
    if not feature_columns:
        return pd.DataFrame()

    anomaly_rows: list[pd.DataFrame] = []
    scenario_rows = yearly_wide[yearly_wide["scenario_family"].isin(["medium_emissions", "high_emissions"])].copy()
    for scenario, frame in scenario_rows.groupby("scenario_family", sort=True):
        baseline = frame[(frame["year"] >= 2016) & (frame["year"] <= 2025)]
        if baseline.empty:
            continue
        baseline_means = baseline[feature_columns].mean()
        adjusted = frame.copy()
        for column in feature_columns:
            adjusted[f"{column}_anomaly_vs_2016_2025"] = adjusted[column] - baseline_means[column]
        anomaly_rows.append(adjusted)

    if not anomaly_rows:
        return pd.DataFrame()
    return pd.concat(anomaly_rows, ignore_index=True).sort_values(
        ["scenario_family", "year"]
    ).reset_index(drop=True)


def write_readiness_report(
    *,
    slovenia_monthly_df: pd.DataFrame,
    slovenia_yearly_df: pd.DataFrame,
    dependency_df: pd.DataFrame,
    model_a_index_df: pd.DataFrame,
    model_c_monthly_df: pd.DataFrame,
    parser_status: dict[str, bool],
) -> None:
    monthly_min = pd.to_datetime(slovenia_monthly_df["month_start"]).min().date().isoformat()
    monthly_max = pd.to_datetime(slovenia_monthly_df["month_start"]).max().date().isoformat()
    yearly_min = int(slovenia_yearly_df["year"].min())
    yearly_max = int(slovenia_yearly_df["year"].max())

    model_a_pending = int(
        (model_a_index_df["value_extraction_status"] == "pending_grib_parser_dependency").sum()
    )
    model_c_features = sorted(model_c_monthly_df["output_feature"].dropna().unique().tolist())

    lines = [
        "# Copernicus Forecast Processing Readiness",
        "",
        f"- generated at: `{timestamp_utc()}`",
        "",
        "## Model Goals",
        "",
        "- Model A: Slovenia monthly operational forecasting up to six months ahead using seasonal forecast weather aligned to the historical predictive monthly panel.",
        "- Model C: Slovenia long-range climate-effect forecasting using climate scenarios, processed primarily as yearly climate trajectories rather than exact weather prediction.",
        "",
        "## Historical Dependency Backbone",
        "",
        f"- Slovenia monthly panel window: `{monthly_min}` to `{monthly_max}`",
        f"- Slovenia yearly panel window: `{yearly_min}` to `{yearly_max}`",
        f"- Monthly panel columns: `{len(slovenia_monthly_df.columns)}`",
        f"- Yearly panel columns: `{len(slovenia_yearly_df.columns)}`",
        "",
        "## Parser Readiness",
        "",
        f"- xarray available: `{parser_status['xarray']}`",
        f"- cfgrib available: `{parser_status['cfgrib']}`",
        f"- pygrib available: `{parser_status['pygrib']}`",
        f"- eccodes available: `{parser_status['eccodes']}`",
        "",
        "## Model A Processing Status",
        "",
        f"- indexed forecast rows: `{len(model_a_index_df)}`",
        f"- GRIB value extraction rows still pending parser dependency: `{model_a_pending}`",
        "- Model A should be post-processed as an issue-month x lead-month x target-month table, then joined to disease-history lags from the historical Slovenia monthly panel.",
        "- Model A should use a reduced weather feature subset because the seasonal monthly forecast product does not contain the daily or hourly detail needed to rebuild all historical weather features.",
        "",
        "## Model C Processing Status",
        "",
        f"- processed monthly climate rows: `{len(model_c_monthly_df)}`",
        f"- processed climate features: `{', '.join(model_c_features)}`",
        "- Model C can already be processed from the downloaded Atlas ZIP packages because they contain NetCDF files readable with xarray.",
        "- Model C should be used with raw scenario values plus anomaly tables against a recent 2016-2025 baseline, because several future variables are proxy matches rather than one-to-one copies of the historical panel.",
        "",
        "## Dependency Rule",
        "",
        "- The historical predictive panels stay the canonical schema for targets, disease-history lags, and static metadata.",
        "- Model A future weather features should be aligned to target months.",
        "- Model C future climate features should be aligned to scenario months or years and treated as direct or proxy climate analogues.",
        "",
        "## Direct vs Proxy Summary",
        "",
        f"- dependency rows recorded: `{len(dependency_df)}`",
        f"- Model A direct or derived matches: `{int(dependency_df['model_a_status'].isin(['direct_match', 'derived_match', 'direct_match_pending_unit_validation']).sum())}`",
        f"- Model C direct or proxy matches: `{int(dependency_df['model_c_status'].isin(['direct_match', 'proxy_match']).sum())}`",
        "",
    ]
    (REPORTS_DIR / "processing_readiness_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ensure_dirs()

    slovenia_monthly_df = pd.read_csv(SLOVENIA_MONTHLY_PANEL_OUTPUT, encoding="utf-8-sig")
    slovenia_yearly_df = pd.read_csv(SLOVENIA_YEARLY_PANEL_OUTPUT, encoding="utf-8-sig")

    parser_status = {
        "xarray": module_available("xarray"),
        "cfgrib": module_available("cfgrib"),
        "pygrib": module_available("pygrib"),
        "eccodes": module_available("eccodes"),
    }

    dependency_df = build_dependency_rows(list(slovenia_monthly_df.columns))
    model_a_index_df = build_model_a_file_index(
        slovenia_monthly_df,
        grib_parser_ready=bool(
            parser_status["cfgrib"] or parser_status["pygrib"] or parser_status["eccodes"]
        ),
    )
    model_a_coverage_summary = (
        model_a_index_df.assign(
            issue_target_key=lambda df: (
                df["init_month_start"].astype(str)
                + "|"
                + df["lead_month"].astype(str)
                + "|"
                + df["target_month_start"].astype(str)
            ),
            historical_issue_target_key=lambda df: df["issue_target_key"].where(
                df["target_in_historical_panel_window"]
            ),
        )
        .groupby("variable_family", as_index=False)
        .agg(
            file_row_count=("variable_family", "size"),
            row_count=("issue_target_key", "nunique"),
            min_init_month_start=("init_month_start", "min"),
            max_init_month_start=("init_month_start", "max"),
            historical_window_target_rows=("historical_issue_target_key", "nunique"),
        )
        .sort_values("variable_family")
        .reset_index(drop=True)
    )
    model_c_monthly_df = build_model_c_monthly_long()
    model_c_yearly_df = build_model_c_yearly_long(model_c_monthly_df)
    model_c_monthly_wide = build_model_c_wide(model_c_monthly_df, time_key="month_start")
    model_c_yearly_wide = build_model_c_wide(model_c_yearly_df, time_key="year")
    model_c_yearly_anomalies = build_model_c_yearly_anomalies(model_c_yearly_wide)

    dependency_df.to_csv(
        SHARED_DIR / "historical_future_dependency_map.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_a_index_df.to_csv(
        MODEL_A_OUTPUT_DIR / "model_a_forecast_file_index.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_a_coverage_summary.to_csv(
        MODEL_A_OUTPUT_DIR / "model_a_forecast_coverage_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_c_monthly_df.to_csv(
        MODEL_C_OUTPUT_DIR / "model_c_slovenia_monthly_long.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_c_yearly_df.to_csv(
        MODEL_C_OUTPUT_DIR / "model_c_slovenia_yearly_long.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_c_monthly_wide.to_csv(
        MODEL_C_OUTPUT_DIR / "model_c_slovenia_monthly_wide.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_c_yearly_wide.to_csv(
        MODEL_C_OUTPUT_DIR / "model_c_slovenia_yearly_wide.csv",
        index=False,
        encoding="utf-8-sig",
    )
    model_c_yearly_anomalies.to_csv(
        MODEL_C_OUTPUT_DIR / "model_c_slovenia_yearly_anomalies_vs_2016_2025.csv",
        index=False,
        encoding="utf-8-sig",
    )

    dependency_payload = {
        "generated_at_utc": timestamp_utc(),
        "historical_monthly_panel": str(SLOVENIA_MONTHLY_PANEL_OUTPUT),
        "historical_yearly_panel": str(SLOVENIA_YEARLY_PANEL_OUTPUT),
        "parser_status": parser_status,
        "dependency_rows": dependency_df.to_dict(orient="records"),
    }
    write_json(SHARED_DIR / "historical_future_dependency_map.json", dependency_payload)

    manifest = {
        "generated_at_utc": timestamp_utc(),
        "inputs": {
            "slovenia_monthly_panel": str(SLOVENIA_MONTHLY_PANEL_OUTPUT),
            "slovenia_yearly_panel": str(SLOVENIA_YEARLY_PANEL_OUTPUT),
            "forecast_raw_root": str(FORECAST_RAW_DIR),
            "climate_atlas_raw_root": str(CLIMATE_ATLAS_RAW_DIR),
        },
        "parser_status": parser_status,
        "outputs": {
            "dependency_map_csv": str(SHARED_DIR / "historical_future_dependency_map.csv"),
            "dependency_map_json": str(SHARED_DIR / "historical_future_dependency_map.json"),
            "model_a_index_csv": str(MODEL_A_OUTPUT_DIR / "model_a_forecast_file_index.csv"),
            "model_a_coverage_summary_csv": str(
                MODEL_A_OUTPUT_DIR / "model_a_forecast_coverage_summary.csv"
            ),
            "model_c_monthly_long_csv": str(MODEL_C_OUTPUT_DIR / "model_c_slovenia_monthly_long.csv"),
            "model_c_yearly_long_csv": str(MODEL_C_OUTPUT_DIR / "model_c_slovenia_yearly_long.csv"),
            "model_c_monthly_wide_csv": str(MODEL_C_OUTPUT_DIR / "model_c_slovenia_monthly_wide.csv"),
            "model_c_yearly_wide_csv": str(MODEL_C_OUTPUT_DIR / "model_c_slovenia_yearly_wide.csv"),
            "model_c_yearly_anomalies_csv": str(
                MODEL_C_OUTPUT_DIR / "model_c_slovenia_yearly_anomalies_vs_2016_2025.csv"
            ),
            "readiness_report_md": str(REPORTS_DIR / "processing_readiness_report.md"),
        },
        "counts": {
            "dependency_rows": int(len(dependency_df)),
            "model_a_index_rows": int(len(model_a_index_df)),
            "model_a_coverage_rows": int(len(model_a_coverage_summary)),
            "model_c_monthly_rows": int(len(model_c_monthly_df)),
            "model_c_yearly_rows": int(len(model_c_yearly_df)),
            "model_c_monthly_wide_rows": int(len(model_c_monthly_wide)),
            "model_c_yearly_wide_rows": int(len(model_c_yearly_wide)),
            "model_c_yearly_anomaly_rows": int(len(model_c_yearly_anomalies)),
        },
    }
    write_json(SHARED_METADATA_DIR / "copernicus_forecast_processing_manifest.json", manifest)

    write_readiness_report(
        slovenia_monthly_df=slovenia_monthly_df,
        slovenia_yearly_df=slovenia_yearly_df,
        dependency_df=dependency_df,
        model_a_index_df=model_a_index_df,
        model_c_monthly_df=model_c_monthly_df,
        parser_status=parser_status,
    )

    print("Copernicus forecast processing assets built successfully.")
    print(f"- dependency rows: {len(dependency_df)}")
    print(f"- model A forecast index rows: {len(model_a_index_df)}")
    print(f"- model C monthly rows: {len(model_c_monthly_df)}")
    print(f"- model C yearly rows: {len(model_c_yearly_df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
