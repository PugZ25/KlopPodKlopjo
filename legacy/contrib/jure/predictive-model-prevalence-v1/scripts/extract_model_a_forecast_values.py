from __future__ import annotations

import calendar
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline_utils import PROJECT_ROOT, timestamp_utc, write_json


PROCESSING_ROOT = PROJECT_ROOT / "data processing - copernicus_forecast_data"
OUTPUT_DIR = PROCESSING_ROOT / "outputs" / "model_a"
REPORTS_DIR = PROCESSING_ROOT / "reports"
SHARED_METADATA_DIR = PROCESSING_ROOT / "outputs" / "shared_metadata"

MODEL_A_FILE_INDEX = OUTPUT_DIR / "model_a_forecast_file_index.csv"
MODEL_A_FUTURE_TEMPLATE = OUTPUT_DIR / "model_a_future_operational_template.csv"
MODEL_A_BACKTEST_TEMPLATE = OUTPUT_DIR / "model_a_backtest_support_template.csv"

FAMILY_EXPECTED_SHORT_NAMES = {
    "copernicus_temperature": {"t2m"},
    "copernicus_humidity": {"t2m", "d2m"},
    "copernicus_precipitation": {"tprate"},
    "copernicus_soil": {"stl1", "stl2", "swvl1", "swvl2"},
}
RAW_VARIABLE_TO_SHORT_NAME = {
    "2m_temperature": "t2m",
    "2m_dewpoint_temperature": "d2m",
    "total_precipitation": "tprate",
    "soil_temperature_level_1": "stl1",
    "soil_temperature_level_2": "stl2",
    "volumetric_soil_water_layer_1": "swvl1",
    "volumetric_soil_water_layer_2": "swvl2",
}

CORE_FORECAST_FEATURES = [
    "air_temperature_c_mean_forecast",
    "relative_humidity_pct_mean_forecast",
    "precipitation_sum_mm_forecast",
    "soil_temperature_level_1_c_mean_forecast",
]

EXTENDED_REQUESTED_FORECAST_FEATURES = [
    "air_temperature_c_mean_forecast",
    "relative_humidity_pct_mean_forecast",
    "precipitation_sum_mm_forecast",
    "soil_temperature_level_1_c_mean_forecast",
    "soil_temperature_level_2_c_mean_forecast",
    "soil_water_layer_1_m3_m3_mean_forecast",
    "soil_water_layer_2_m3_m3_mean_forecast",
]

FORECAST_FEATURE_UNITS = {
    "air_temperature_c_mean_forecast": "degC",
    "relative_humidity_pct_mean_forecast": "pct",
    "precipitation_sum_mm_forecast": "mm/month",
    "soil_temperature_level_1_c_mean_forecast": "degC",
    "soil_temperature_level_2_c_mean_forecast": "degC",
    "soil_water_layer_1_m3_m3_mean_forecast": "m3/m3",
    "soil_water_layer_2_m3_m3_mean_forecast": "m3/m3",
}


def ensure_dirs() -> None:
    for path in [OUTPUT_DIR, REPORTS_DIR, SHARED_METADATA_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def import_grib_stack():
    try:
        import cfgrib  # type: ignore
        import eccodes  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive runtime guidance
        raise RuntimeError(
            "Model A GRIB extraction requires a Python runtime with working "
            "cfgrib/ecCodes support. Run this script with `py -3.13`."
        ) from exc
    return cfgrib, eccodes


def normalize_month_start(values: object) -> pd.DatetimeIndex:
    timestamps = pd.to_datetime(values)
    return timestamps.to_period("M").to_timestamp()


def first_non_null(series: pd.Series):
    non_null = series.dropna()
    if non_null.empty:
        return np.nan
    return non_null.iloc[0]


def unique_join(series: pd.Series) -> str:
    values = sorted({str(value) for value in series.dropna() if str(value).strip()})
    return "; ".join(values)


def expected_short_names_from_requested_variables(requested_raw_variables: str, family: str) -> set[str]:
    raw_variables = [
        value.strip()
        for value in str(requested_raw_variables).split(";")
        if value.strip()
    ]
    expected = {
        RAW_VARIABLE_TO_SHORT_NAME[value]
        for value in raw_variables
        if value in RAW_VARIABLE_TO_SHORT_NAME
    }
    return expected or set(FAMILY_EXPECTED_SHORT_NAMES[family])


def collapse_member_step(da) -> dict[str, object]:
    dims = list(da.dims)
    spatial_dims = [dim for dim in dims if dim.lower() in {"latitude", "longitude", "lat", "lon"}]
    grid_cell_count = 1
    for dim in spatial_dims:
        grid_cell_count *= int(da.sizes[dim])

    field = da
    if spatial_dims:
        field = field.mean(dim=spatial_dims, skipna=True)

    member_dim = next((dim for dim in field.dims if dim.lower() in {"number", "member", "realization"}), None)
    if member_dim is None:
        field = field.expand_dims(member=[0])
        member_dim = "member"

    step_dim = next((dim for dim in field.dims if dim.lower() in {"step", "leadtime", "forecastmonth"}), None)
    if step_dim is None:
        raise ValueError(f"Could not identify step-like dimension for {da.name}.")

    field = field.transpose(step_dim, member_dim)
    if "valid_time" in field.coords:
        target_month_start = normalize_month_start(field.coords["valid_time"].values)
    else:
        time_coord = pd.to_datetime(field.coords["time"].values)
        step_coord = pd.to_timedelta(field.coords[step_dim].values)
        target_month_start = normalize_month_start(time_coord + step_coord)

    values = np.asarray(field.to_numpy(), dtype=float)
    return {
        "target_month_start": target_month_start,
        "values": values,
        "member_count": int(field.sizes[member_dim]),
        "grid_cell_count": int(grid_cell_count),
        "source_units": da.attrs.get("units", ""),
    }


def summarize_member_values(
    feature_name: str,
    target_month_start: pd.DatetimeIndex,
    values: np.ndarray,
) -> pd.DataFrame:
    data = np.asarray(values, dtype=float)
    with np.errstate(invalid="ignore"):
        summary = pd.DataFrame(
            {
                "target_month_start": target_month_start,
                feature_name: np.nanmean(data, axis=1),
                f"{feature_name}_p10": np.nanquantile(data, 0.10, axis=1),
                f"{feature_name}_p50": np.nanquantile(data, 0.50, axis=1),
                f"{feature_name}_p90": np.nanquantile(data, 0.90, axis=1),
                f"{feature_name}_std": np.nanstd(data, axis=1),
            }
        )
    return summary


def kelvin_to_celsius(values: np.ndarray) -> np.ndarray:
    return np.asarray(values, dtype=float) - 273.15


def derive_relative_humidity_pct(temperature_k: np.ndarray, dewpoint_k: np.ndarray) -> np.ndarray:
    temperature_c = kelvin_to_celsius(temperature_k)
    dewpoint_c = kelvin_to_celsius(dewpoint_k)
    with np.errstate(over="ignore", invalid="ignore"):
        numerator = np.exp((17.625 * dewpoint_c) / (243.04 + dewpoint_c))
        denominator = np.exp((17.625 * temperature_c) / (243.04 + temperature_c))
        rh = 100.0 * (numerator / denominator)
    return np.clip(rh, 0.0, 100.0)


def precipitation_rate_to_monthly_mm(
    precipitation_rate_m_per_s: np.ndarray,
    target_month_start: pd.DatetimeIndex,
) -> np.ndarray:
    seconds_per_month = np.array(
        [
            calendar.monthrange(timestamp.year, timestamp.month)[1] * 24 * 60 * 60
            for timestamp in target_month_start
        ],
        dtype=float,
    )[:, None]
    return np.asarray(precipitation_rate_m_per_s, dtype=float) * seconds_per_month * 1000.0


def shared_target_months(matrices: list[dict[str, object]]) -> pd.DatetimeIndex:
    if not matrices:
        raise ValueError("At least one matrix is required.")
    baseline = matrices[0]["target_month_start"]
    for matrix in matrices[1:]:
        if not pd.Index(baseline).equals(pd.Index(matrix["target_month_start"])):
            raise ValueError("Forecast variables inside one file do not share the same target months.")
    return pd.DatetimeIndex(baseline)


def load_family_matrices(
    file_path: Path,
    family: str,
    cfgrib,
    expected_short_names: set[str] | None = None,
) -> tuple[dict[str, dict[str, object]], list[str]]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        datasets = cfgrib.open_datasets(str(file_path), backend_kwargs={"indexpath": ""})

    matrices: dict[str, dict[str, object]] = {}
    for dataset in datasets:
        for variable_name in dataset.data_vars:
            matrices[variable_name] = collapse_member_step(dataset[variable_name])
    available_short_names = sorted(matrices)
    expected = expected_short_names or set(FAMILY_EXPECTED_SHORT_NAMES[family])
    missing_short_names = sorted(expected - set(available_short_names))
    return matrices, missing_short_names


def extract_family_table(
    file_path: Path,
    family: str,
    cfgrib,
    expected_short_names: set[str] | None = None,
) -> pd.DataFrame:
    matrices, missing_short_names = load_family_matrices(
        file_path,
        family,
        cfgrib,
        expected_short_names=expected_short_names,
    )
    available_short_names = sorted(matrices)

    if not matrices:
        return pd.DataFrame(
            {
                "target_month_start": pd.Series(dtype="datetime64[ns]"),
                "variable_family": pd.Series(dtype="string"),
                "source_file_path": pd.Series(dtype="string"),
            }
        )

    frames: list[pd.DataFrame] = []
    notes: list[str] = []
    member_count = max(int(matrix["member_count"]) for matrix in matrices.values())
    grid_cell_count = max(int(matrix["grid_cell_count"]) for matrix in matrices.values())

    if family == "copernicus_temperature" and "t2m" in matrices:
        matrix = matrices["t2m"]
        target_month_start = pd.DatetimeIndex(matrix["target_month_start"])
        transformed = kelvin_to_celsius(np.asarray(matrix["values"], dtype=float))
        frames.append(
            summarize_member_values(
                "air_temperature_c_mean_forecast",
                target_month_start,
                transformed,
            )
        )

    if family == "copernicus_humidity":
        if {"t2m", "d2m"} <= set(matrices):
            target_month_start = shared_target_months([matrices["t2m"], matrices["d2m"]])
            transformed = derive_relative_humidity_pct(
                np.asarray(matrices["t2m"]["values"], dtype=float),
                np.asarray(matrices["d2m"]["values"], dtype=float),
            )
            frames.append(
                summarize_member_values(
                    "relative_humidity_pct_mean_forecast",
                    target_month_start,
                    transformed,
                )
            )
        else:
            notes.append("Could not derive relative humidity because t2m and d2m were not both available.")

    if family == "copernicus_precipitation" and "tprate" in matrices:
        matrix = matrices["tprate"]
        target_month_start = pd.DatetimeIndex(matrix["target_month_start"])
        transformed = precipitation_rate_to_monthly_mm(
            np.asarray(matrix["values"], dtype=float),
            target_month_start,
        )
        frames.append(
            summarize_member_values(
                "precipitation_sum_mm_forecast",
                target_month_start,
                transformed,
            )
        )

    if family == "copernicus_soil":
        soil_feature_map = {
            "stl1": "soil_temperature_level_1_c_mean_forecast",
            "stl2": "soil_temperature_level_2_c_mean_forecast",
            "swvl1": "soil_water_layer_1_m3_m3_mean_forecast",
            "swvl2": "soil_water_layer_2_m3_m3_mean_forecast",
        }
        for short_name, feature_name in soil_feature_map.items():
            if short_name not in matrices:
                continue
            matrix = matrices[short_name]
            target_month_start = pd.DatetimeIndex(matrix["target_month_start"])
            values = np.asarray(matrix["values"], dtype=float)
            if short_name.startswith("stl"):
                values = kelvin_to_celsius(values)
            frames.append(summarize_member_values(feature_name, target_month_start, values))

    if not frames:
        target_month_start = pd.DatetimeIndex(next(iter(matrices.values()))["target_month_start"])
        table = pd.DataFrame({"target_month_start": target_month_start})
    else:
        table = frames[0]
        for frame in frames[1:]:
            table = table.merge(frame, on="target_month_start", how="outer")

    family_status = "ok_complete"
    if missing_short_names:
        family_status = "ok_partial_missing_variables"
        notes.append(f"Missing GRIB short names: {', '.join(missing_short_names)}.")

    if (
        family == "copernicus_soil"
        and expected_short_names == FAMILY_EXPECTED_SHORT_NAMES["copernicus_soil"]
        and {"stl2", "swvl1", "swvl2"} & set(missing_short_names)
    ):
        notes.append(
            "Current soil forecast files contain only stl1 in this download set. "
            "A corrected soil re-download is needed to restore the full requested soil block."
        )

    table["variable_family"] = family
    table["source_file_path"] = str(file_path)
    table["available_short_names"] = "; ".join(available_short_names)
    table["missing_short_names"] = "; ".join(missing_short_names)
    table["family_extraction_status"] = family_status
    table["ensemble_member_count"] = member_count
    table["grid_cell_count"] = grid_cell_count
    table["family_notes"] = " ".join(notes).strip()
    return table.sort_values("target_month_start").reset_index(drop=True)


def build_extracted_family_rows(model_a_index: pd.DataFrame, cfgrib) -> pd.DataFrame:
    cache: dict[tuple[str, str], pd.DataFrame] = {}
    records: list[dict[str, object]] = []

    for row in model_a_index.itertuples(index=False):
        file_path = Path(row.file_path)
        expected_short_names = expected_short_names_from_requested_variables(
            row.requested_raw_variables,
            row.variable_family,
        )
        cache_key = (
            row.variable_family,
            str(file_path),
            ";".join(sorted(expected_short_names)),
        )
        if cache_key not in cache:
            cache[cache_key] = extract_family_table(
                file_path,
                row.variable_family,
                cfgrib,
                expected_short_names=expected_short_names,
            )

        family_table = cache[cache_key]
        target_month_start = pd.Timestamp(row.target_month_start)
        match = family_table[family_table["target_month_start"] == target_month_start]

        extracted_payload: dict[str, object] = {
            "family_row_extraction_status": "target_month_not_found_in_file",
        }
        if not match.empty:
            extracted_payload = match.iloc[0].to_dict()
            extracted_payload["family_row_extraction_status"] = extracted_payload.get(
                "family_extraction_status",
                "ok_complete",
            )

        record = {
            "variable_family": row.variable_family,
            "requested_raw_variables": row.requested_raw_variables,
            "historical_reference_features": row.historical_reference_features,
            "match_status": row.match_status,
            "init_year": int(row.init_year),
            "init_month": int(row.init_month),
            "init_month_start": pd.Timestamp(row.init_month_start),
            "lead_month": int(row.lead_month),
            "target_year": int(row.target_year),
            "target_month": int(row.target_month),
            "target_month_start": target_month_start,
            "target_in_historical_panel_window": bool(row.target_in_historical_panel_window),
            "value_extraction_status": row.value_extraction_status,
            "transformation_rule": row.transformation_rule,
            "notes": row.notes,
            "file_path": row.file_path,
        }
        record.update(extracted_payload)
        records.append(record)

    return pd.DataFrame(records).sort_values(
        ["variable_family", "init_month_start", "lead_month"]
    ).reset_index(drop=True)


def build_wide_table(extracted_family_rows: pd.DataFrame) -> pd.DataFrame:
    group_keys = [
        "init_month_start",
        "lead_month",
        "target_month_start",
        "target_year",
        "target_month",
    ]
    aggregate_columns = [
        "requested_raw_variables",
        "historical_reference_features",
        "available_short_names",
        "missing_short_names",
        "family_notes",
        "family_row_extraction_status",
        "ensemble_member_count",
        "grid_cell_count",
    ]
    aggregate_columns.extend(EXTENDED_REQUESTED_FORECAST_FEATURES)
    for feature in EXTENDED_REQUESTED_FORECAST_FEATURES:
        aggregate_columns.extend(
            [
                f"{feature}_p10",
                f"{feature}_p50",
                f"{feature}_p90",
                f"{feature}_std",
            ]
        )

    prepared = extracted_family_rows.copy()
    for column in aggregate_columns:
        if column not in prepared.columns:
            prepared[column] = np.nan

    string_join_columns = {
        "requested_raw_variables",
        "historical_reference_features",
        "available_short_names",
        "missing_short_names",
        "family_notes",
        "family_row_extraction_status",
    }
    max_columns = {
        "ensemble_member_count",
        "grid_cell_count",
    }
    aggregation = {}
    for column in aggregate_columns:
        if column in string_join_columns:
            aggregation[column] = unique_join
        elif column in max_columns:
            aggregation[column] = "max"
        else:
            aggregation[column] = first_non_null
    wide = (
        prepared[group_keys + ["variable_family"] + aggregate_columns]
        .groupby(group_keys, as_index=False, dropna=False)
        .agg(aggregation)
    )

    family_lists = (
        prepared.groupby(group_keys, dropna=False)["variable_family"]
        .agg(unique_join)
        .reset_index(name="available_variable_families")
    )
    status_lists = (
        prepared.assign(
            status_label=lambda df: df["variable_family"] + ":" + df["family_row_extraction_status"]
        )
        .groupby(group_keys, dropna=False)["status_label"]
        .agg(unique_join)
        .reset_index(name="family_extraction_statuses")
    )

    wide = wide.merge(family_lists, on=group_keys, how="left")
    wide = wide.merge(status_lists, on=group_keys, how="left")
    for feature in EXTENDED_REQUESTED_FORECAST_FEATURES:
        wide[f"has_{feature}"] = wide[feature].notna()

    wide["has_core_operational_block"] = wide[CORE_FORECAST_FEATURES].notna().all(axis=1)
    wide["has_full_requested_feature_block"] = wide[EXTENDED_REQUESTED_FORECAST_FEATURES].notna().all(axis=1)
    wide["has_any_soil_forecast_feature"] = wide[
        [
            "soil_temperature_level_1_c_mean_forecast",
            "soil_temperature_level_2_c_mean_forecast",
            "soil_water_layer_1_m3_m3_mean_forecast",
            "soil_water_layer_2_m3_m3_mean_forecast",
        ]
    ].notna().any(axis=1)
    return wide.sort_values(["init_month_start", "lead_month"]).reset_index(drop=True)


def merge_numeric_templates(wide_table: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    future_template = pd.read_csv(MODEL_A_FUTURE_TEMPLATE, encoding="utf-8-sig")
    backtest_template = pd.read_csv(MODEL_A_BACKTEST_TEMPLATE, encoding="utf-8-sig")

    for frame in [future_template, backtest_template]:
        frame["init_month_start"] = pd.to_datetime(frame["init_month_start"])
        frame["target_month_start"] = pd.to_datetime(frame["target_month_start"])

    merge_keys = ["init_month_start", "lead_month", "target_month_start", "target_year", "target_month"]
    future_numeric = future_template.merge(wide_table, on=merge_keys, how="left")
    backtest_numeric = backtest_template.merge(wide_table, on=merge_keys, how="left")

    future_numeric["grib_value_extraction_ready"] = future_numeric["has_core_operational_block"].fillna(False)
    future_numeric["usable_core_weather_block_ready"] = future_numeric["has_core_operational_block"].fillna(False)
    backtest_numeric["grib_value_extraction_ready"] = backtest_numeric["has_core_operational_block"].fillna(False)
    backtest_numeric["usable_core_weather_block_ready"] = backtest_numeric["has_core_operational_block"].fillna(False)

    core_ready_note = (
        "Numeric forecast extraction succeeded for the operational monthly-stats weather block: "
        "temperature, derived humidity, precipitation, and soil temperature level 1."
    )
    full_ready_note = (
        "Numeric forecast extraction succeeded for the operational monthly-stats weather block. "
        "The deeper soil temperature and soil-water layers are not provided by this CDS monthly dataset."
    )
    temperature_only_note = (
        "Numeric extraction is available for temperature-only backtest support rows. "
        "The other forecast families are not present for these historical rows in the current archive."
    )
    not_ready_note = "No numeric forecast extraction was available for this row."

    future_numeric["notes"] = np.where(
        future_numeric["grib_value_extraction_ready"].fillna(False),
        full_ready_note,
        np.where(
            future_numeric["usable_core_weather_block_ready"].fillna(False),
            core_ready_note,
            not_ready_note,
        ),
    )
    backtest_numeric["notes"] = np.where(
        backtest_numeric["grib_value_extraction_ready"].fillna(False),
        full_ready_note,
        np.where(
            backtest_numeric["usable_core_weather_block_ready"].fillna(False),
            core_ready_note,
            np.where(
                backtest_numeric["has_air_temperature_c_mean_forecast"].fillna(False),
                temperature_only_note,
                not_ready_note,
            ),
        ),
    )
    return future_numeric, backtest_numeric


def build_feature_availability_summary(wide_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for feature in EXTENDED_REQUESTED_FORECAST_FEATURES:
        available = wide_table[wide_table[feature].notna()].copy()
        rows.append(
            {
                "feature_name": feature,
                "feature_units": FORECAST_FEATURE_UNITS[feature],
                "available_row_count": int(len(available)),
                "min_target_month_start": (
                    available["target_month_start"].min().date().isoformat() if not available.empty else ""
                ),
                "max_target_month_start": (
                    available["target_month_start"].max().date().isoformat() if not available.empty else ""
                ),
                "available_issue_month_count": (
                    int(available["init_month_start"].nunique()) if not available.empty else 0
                ),
            }
        )
    return pd.DataFrame(rows)


def write_report(
    *,
    python_version: str,
    eccodes_version: str,
    extracted_family_rows: pd.DataFrame,
    wide_table: pd.DataFrame,
    future_numeric: pd.DataFrame,
    backtest_numeric: pd.DataFrame,
    feature_summary: pd.DataFrame,
) -> None:
    report_path = REPORTS_DIR / "model_a_numeric_extraction_report.md"
    lines = [
        "# Model A Numeric Forecast Extraction",
        "",
        f"- generated at: `{timestamp_utc()}`",
        f"- python runtime: `{python_version}`",
        f"- ecCodes version: `{eccodes_version}`",
        "",
        "## Output Counts",
        "",
        f"- extracted family rows: `{len(extracted_family_rows)}`",
        f"- wide forecast rows: `{len(wide_table)}`",
        f"- future operational numeric rows: `{len(future_numeric)}`",
        f"- backtest-support numeric rows: `{len(backtest_numeric)}`",
        "",
        "## Future Readiness",
        "",
        f"- future rows with operational monthly-stats feature block: `{int(future_numeric['grib_value_extraction_ready'].fillna(False).sum())}`",
        f"- future rows with extended locked-era soil block: `{int(future_numeric['has_full_requested_feature_block'].fillna(False).sum())}`",
        "",
        "## Feature Availability",
        "",
    ]
    for row in feature_summary.itertuples(index=False):
        lines.append(
            f"- `{row.feature_name}`: `{row.available_row_count}` rows, "
            f"target window `{row.min_target_month_start}` to `{row.max_target_month_start}`"
        )

    lines.extend(
        [
            "",
            "## Soil Scope",
            "",
            "- Under the current `seasonal-monthly-single-levels` CDS acquisition rules, the reproducible soil monthly block provides `soil_temperature_level_1`.",
            "- `soil_temperature_level_2`, `soil_water_layer_1`, and `soil_water_layer_2` are not exposed by this monthly CDS dataset and therefore remain outside the first-pass operational block.",
            "",
        ]
    )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ensure_dirs()
    cfgrib, eccodes = import_grib_stack()

    model_a_index = pd.read_csv(MODEL_A_FILE_INDEX, encoding="utf-8-sig")
    model_a_index["init_month_start"] = pd.to_datetime(model_a_index["init_month_start"])
    model_a_index["target_month_start"] = pd.to_datetime(model_a_index["target_month_start"])

    extracted_family_rows = build_extracted_family_rows(model_a_index, cfgrib)
    wide_table = build_wide_table(extracted_family_rows)
    future_numeric, backtest_numeric = merge_numeric_templates(wide_table)
    feature_summary = build_feature_availability_summary(wide_table)

    extracted_family_rows.to_csv(
        OUTPUT_DIR / "model_a_extracted_family_rows.csv",
        index=False,
        encoding="utf-8-sig",
    )
    wide_table.to_csv(
        OUTPUT_DIR / "model_a_forecast_values_wide.csv",
        index=False,
        encoding="utf-8-sig",
    )
    future_numeric.to_csv(
        OUTPUT_DIR / "model_a_future_operational_numeric.csv",
        index=False,
        encoding="utf-8-sig",
    )
    backtest_numeric.to_csv(
        OUTPUT_DIR / "model_a_backtest_support_numeric.csv",
        index=False,
        encoding="utf-8-sig",
    )
    feature_summary.to_csv(
        OUTPUT_DIR / "model_a_feature_availability_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    python_version = sys.version.split()[0]
    eccodes_version = str(eccodes.codes_get_api_version())
    manifest = {
        "generated_at_utc": timestamp_utc(),
        "python_version": python_version,
        "eccodes_version": eccodes_version,
        "inputs": {
            "model_a_file_index": str(MODEL_A_FILE_INDEX),
            "model_a_future_template": str(MODEL_A_FUTURE_TEMPLATE),
            "model_a_backtest_template": str(MODEL_A_BACKTEST_TEMPLATE),
        },
        "outputs": {
            "model_a_extracted_family_rows": str(OUTPUT_DIR / "model_a_extracted_family_rows.csv"),
            "model_a_forecast_values_wide": str(OUTPUT_DIR / "model_a_forecast_values_wide.csv"),
            "model_a_future_operational_numeric": str(OUTPUT_DIR / "model_a_future_operational_numeric.csv"),
            "model_a_backtest_support_numeric": str(OUTPUT_DIR / "model_a_backtest_support_numeric.csv"),
            "model_a_feature_availability_summary": str(
                OUTPUT_DIR / "model_a_feature_availability_summary.csv"
            ),
            "model_a_numeric_extraction_report": str(REPORTS_DIR / "model_a_numeric_extraction_report.md"),
        },
        "counts": {
            "extracted_family_rows": int(len(extracted_family_rows)),
            "wide_forecast_rows": int(len(wide_table)),
            "future_operational_numeric_rows": int(len(future_numeric)),
            "backtest_support_numeric_rows": int(len(backtest_numeric)),
        },
    }
    write_json(SHARED_METADATA_DIR / "model_a_numeric_extraction_manifest.json", manifest)

    write_report(
        python_version=python_version,
        eccodes_version=eccodes_version,
        extracted_family_rows=extracted_family_rows,
        wide_table=wide_table,
        future_numeric=future_numeric,
        backtest_numeric=backtest_numeric,
        feature_summary=feature_summary,
    )

    print("Model A forecast values extracted successfully.")
    print(f"- Extracted family rows: {len(extracted_family_rows)}")
    print(f"- Wide forecast rows: {len(wide_table)}")
    print(
        f"- Future rows with operational monthly-stats feature block: "
        f"{int(future_numeric['grib_value_extraction_ready'].fillna(False).sum())}"
    )
    print(
        f"- Future rows with extended locked-era soil block: "
        f"{int(future_numeric['has_full_requested_feature_block'].fillna(False).sum())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
