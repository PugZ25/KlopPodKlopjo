from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_WEATHER_DEM_INPUT = Path("data/processed/training/obcina_weekly_weather_dem_features.csv")
DEFAULT_CLC_INPUT = Path("data/processed/training/obcina_clc_features.csv")
DEFAULT_LOG_POPULATION_INPUT = Path(
    "data/processed/training/obcina_surs_log_population_yearly_features.csv"
)
DEFAULT_POPULATION_DENSITY_INPUT = Path(
    "data/processed/training/obcina_surs_population_density_yearly_features.csv"
)
DEFAULT_EPIDEMIOLOGY_INPUT = Path("data/processed/training/obcina_weekly_epidemiology.csv")
DEFAULT_OUTPUT = Path("data/processed/training/obcina_weekly_tick_borne_catboost_ready.csv")
DEFAULT_MANIFEST_OUTPUT = Path(
    "data/processed/training/obcina_weekly_tick_borne_catboost_ready_manifest.json"
)

CLC_FEATURE_COLUMNS = [
    "dominant_clc_code",
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
]
EPIDEMIOLOGY_FEATURE_COLUMNS = [
    "lyme_cases_lag_2w",
    "lyme_cases_lag_3w",
    "lyme_cases_prev_4w_sum",
    "kme_cases_lag_2w",
    "kme_cases_prev_8w_sum",
]
TARGET_COLUMNS = [
    "target_lyme_cases",
    "target_kme_cases",
    "target_tick_borne_cases_total",
    "target_lyme_presence",
    "target_kme_presence",
]
RECOMMENDED_FEATURE_COLUMNS = [
    "obcina_sifra",
    "overlay_method",
    "dominant_clc_code",
    "air_temperature_c_mean",
    "air_temperature_c_min",
    "air_temperature_c_max",
    "air_temperature_c_std",
    "relative_humidity_pct_mean",
    "relative_humidity_pct_min",
    "relative_humidity_pct_max",
    "precipitation_sum_mm",
    "precipitation_daily_max_mm",
    "soil_temperature_level_1_c_mean",
    "soil_temperature_level_2_c_mean",
    "soil_water_layer_1_m3_m3_mean",
    "soil_water_layer_2_m3_m3_mean",
    "humidity_hours_ge_80_sum",
    "humidity_hours_ge_90_sum",
    "wet_hours_ge_0_1mm_sum",
    "tick_activity_window_hours_sum",
    "growing_degree_hours_base_5_c_sum",
    "rainy_days_ge_1mm_count",
    "humid_days_ge_16h_count",
    "tick_favorable_days_ge_6h_count",
    "air_temperature_c_range",
    "air_temperature_c_mean_lag_1w",
    "air_temperature_c_mean_lag_2w",
    "air_temperature_c_mean_lag_4w",
    "air_temperature_c_mean_rolling_4w_mean",
    "relative_humidity_pct_mean_lag_1w",
    "relative_humidity_pct_mean_lag_2w",
    "relative_humidity_pct_mean_lag_4w",
    "relative_humidity_pct_mean_rolling_4w_mean",
    "precipitation_sum_mm_lag_1w",
    "precipitation_sum_mm_lag_2w",
    "precipitation_sum_mm_lag_4w",
    "precipitation_sum_mm_rolling_4w_mean",
    "soil_water_layer_1_m3_m3_mean_lag_1w",
    "soil_water_layer_1_m3_m3_mean_lag_2w",
    "soil_water_layer_1_m3_m3_mean_lag_4w",
    "soil_water_layer_1_m3_m3_mean_rolling_4w_mean",
    "tick_activity_window_hours_sum_lag_1w",
    "tick_activity_window_hours_sum_lag_2w",
    "tick_activity_window_hours_sum_lag_4w",
    "tick_activity_window_hours_sum_rolling_4w_mean",
    "year",
    "month",
    "iso_week",
    "week_of_year_sin",
    "week_of_year_cos",
    "elevation_m_mean",
    "elevation_m_std",
    "elevation_m_range",
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
    "log_population_total",
    "population_density_per_km2",
    "lyme_cases_lag_2w",
    "lyme_cases_lag_3w",
    "lyme_cases_prev_4w_sum",
    "kme_cases_lag_2w",
    "kme_cases_prev_8w_sum",
]
RECOMMENDED_CATEGORICAL_COLUMNS = [
    "obcina_sifra",
    "overlay_method",
    "dominant_clc_code",
]


@dataclass(frozen=True)
class TickBorneCatBoostTables:
    combined: Any
    manifest: dict[str, Any]


def _ensure_columns(frame: Any, required_columns: list[str], *, label: str) -> None:
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def _normalize_municipality_code(value: object) -> str:
    text = str(value).strip()
    if not text:
        return text
    return text.lstrip("0") or "0"


def _normalize_identifiers(frame: Any) -> Any:
    normalized = frame.copy()
    if "obcina_sifra" in normalized.columns:
        normalized["obcina_sifra"] = normalized["obcina_sifra"].map(_normalize_municipality_code)
    if "obcina_naziv" in normalized.columns:
        normalized["obcina_naziv"] = normalized["obcina_naziv"].map(lambda value: str(value).strip())
    return normalized


def _load_csv(path: Path, *, label: str) -> Any:
    import pandas as pd

    if not path.exists():
        raise FileNotFoundError(f"{label} CSV not found: {path}")
    return _normalize_identifiers(pd.read_csv(path))


def _merge_static_features(
    base: Any,
    static: Any,
    *,
    label: str,
    feature_columns: list[str],
) -> tuple[Any, dict[str, Any]]:
    _ensure_columns(static, ["obcina_sifra", "obcina_naziv", *feature_columns], label=label)

    static_subset = static[["obcina_sifra", "obcina_naziv", *feature_columns]].copy()
    duplicated = static_subset["obcina_sifra"].duplicated(keep=False)
    if duplicated.any():
        duplicate_codes = sorted(
            static_subset.loc[duplicated, "obcina_sifra"].astype(str).unique().tolist()
        )
        raise ValueError(f"{label} has duplicate municipality codes: {', '.join(duplicate_codes)}")

    merged = base.merge(
        static_subset,
        on="obcina_sifra",
        how="left",
        validate="many_to_one",
        suffixes=("", f"_{label.lower()}"),
    )

    diagnostic = {
        "name_mismatch_count": 0,
        "name_mismatch_codes_sample": [],
    }
    source_name_column = f"obcina_naziv_{label.lower()}"
    if source_name_column in merged.columns:
        mismatch = merged[
            merged[source_name_column].notna()
            & (merged["obcina_naziv"].astype(str) != merged[source_name_column].astype(str))
        ]
        diagnostic["name_mismatch_count"] = int(mismatch["obcina_sifra"].nunique())
        diagnostic["name_mismatch_codes_sample"] = sorted(
            mismatch["obcina_sifra"].astype(str).unique().tolist()
        )[:10]
        merged = merged.drop(columns=[source_name_column])

    missing_mask = merged[feature_columns].isna().any(axis=1)
    if missing_mask.any():
        missing_codes = sorted(merged.loc[missing_mask, "obcina_sifra"].astype(str).unique().tolist())
        raise ValueError(
            f"{label} features are missing for municipality codes: {', '.join(missing_codes)}"
        )

    return merged, diagnostic


def _attach_latest_yearly_feature(
    base: Any,
    annual: Any,
    *,
    label: str,
    value_column: str,
    source_year_column: str,
) -> tuple[Any, dict[str, Any]]:
    import pandas as pd

    _ensure_columns(annual, ["year", "obcina_sifra", "obcina_naziv", value_column], label=label)

    source_rows = annual[["year", "obcina_sifra", "obcina_naziv", value_column]].copy()
    source_rows["year"] = pd.to_numeric(source_rows["year"], errors="raise").astype(int)
    source_rows[value_column] = pd.to_numeric(source_rows[value_column], errors="coerce")
    source_rows = source_rows[source_rows[value_column].notna()].copy()

    duplicated = source_rows.duplicated(subset=["obcina_sifra", "year"], keep=False)
    if duplicated.any():
        duplicate_pairs = (
            source_rows.loc[duplicated, ["obcina_sifra", "year"]]
            .drop_duplicates()
            .sort_values(["obcina_sifra", "year"])
        )
        formatted = [f"{row.obcina_sifra}:{row.year}" for row in duplicate_pairs.itertuples(index=False)]
        raise ValueError(f"{label} has duplicate municipality/year rows: {', '.join(formatted)}")

    lookup_by_code: dict[str, dict[str, list[Any]]] = {}
    for row in source_rows.sort_values(["obcina_sifra", "year"]).itertuples(index=False):
        current = lookup_by_code.setdefault(
            str(row.obcina_sifra),
            {"years": [], "values": [], "names": []},
        )
        current["years"].append(int(row.year))
        current["values"].append(float(row.__getattribute__(value_column)))
        current["names"].append(str(row.obcina_naziv))

    values: list[float | None] = []
    source_years: list[int | None] = []
    mismatch_codes: set[str] = set()
    forward_fill_years: set[int] = set()
    missing_codes: set[str] = set()

    for row in base.itertuples(index=False):
        code = str(row.obcina_sifra)
        year = int(row.year)
        source = lookup_by_code.get(code)
        if source is None:
            values.append(None)
            source_years.append(None)
            missing_codes.add(code)
            continue

        index = bisect_right(source["years"], year) - 1
        if index < 0:
            values.append(None)
            source_years.append(None)
            missing_codes.add(code)
            continue

        matched_year = int(source["years"][index])
        matched_name = source["names"][index]
        if matched_name and str(row.obcina_naziv) and matched_name != str(row.obcina_naziv):
            mismatch_codes.add(code)
        if matched_year < year:
            forward_fill_years.add(year)

        values.append(float(source["values"][index]))
        source_years.append(matched_year)

    merged = base.copy()
    merged[value_column] = values
    merged[source_year_column] = pd.Series(source_years, dtype="Int64")

    if merged[value_column].isna().any():
        missing_codes = sorted(merged.loc[merged[value_column].isna(), "obcina_sifra"].astype(str).unique())
        raise ValueError(
            f"{label} values are missing for municipality codes: {', '.join(missing_codes)}"
        )

    diagnostic = {
        "name_mismatch_count": len(mismatch_codes),
        "name_mismatch_codes_sample": sorted(mismatch_codes)[:10],
        "forward_fill_years": sorted(forward_fill_years),
    }
    return merged, diagnostic


def _build_epidemiology_features(epidemiology: Any) -> tuple[Any, dict[str, Any]]:
    import pandas as pd

    _ensure_columns(
        epidemiology,
        [
            "week_start",
            "week_end",
            "obcina_sifra",
            "obcina_naziv",
            "lyme_cases",
            "kme_cases",
            "tick_borne_cases_total",
        ],
        label="Weekly epidemiology CSV",
    )

    epi = epidemiology.copy()
    epi["week_start"] = pd.to_datetime(epi["week_start"], errors="raise")
    epi["week_end"] = pd.to_datetime(epi["week_end"], errors="raise")
    for column in ("lyme_cases", "kme_cases", "tick_borne_cases_total"):
        epi[column] = pd.to_numeric(epi[column], errors="raise").astype(int)

    epi = epi.sort_values(["obcina_sifra", "week_start"], kind="stable").reset_index(drop=True)

    duplicated = epi.duplicated(subset=["week_start", "obcina_sifra"], keep=False)
    if duplicated.any():
        duplicate_keys = (
            epi.loc[duplicated, ["obcina_sifra", "week_start"]]
            .drop_duplicates()
            .sort_values(["obcina_sifra", "week_start"])
        )
        formatted = [
            f"{row.obcina_sifra}:{row.week_start.date().isoformat()}"
            for row in duplicate_keys.itertuples(index=False)
        ]
        raise ValueError(
            "Weekly epidemiology CSV has duplicate municipality/week rows: " + ", ".join(formatted)
        )

    lyme_grouped = epi.groupby("obcina_sifra", sort=False)["lyme_cases"]
    kme_grouped = epi.groupby("obcina_sifra", sort=False)["kme_cases"]

    epi["lyme_cases_lag_2w"] = lyme_grouped.shift(2)
    epi["lyme_cases_lag_3w"] = lyme_grouped.shift(3)
    epi["lyme_cases_prev_4w_sum"] = lyme_grouped.transform(
        lambda series: series.shift(1).rolling(window=4, min_periods=4).sum()
    )
    epi["kme_cases_lag_2w"] = kme_grouped.shift(2)
    epi["kme_cases_prev_8w_sum"] = kme_grouped.transform(
        lambda series: series.shift(1).rolling(window=8, min_periods=8).sum()
    )

    epi["target_lyme_cases"] = epi["lyme_cases"]
    epi["target_kme_cases"] = epi["kme_cases"]
    epi["target_tick_borne_cases_total"] = epi["tick_borne_cases_total"]
    epi["target_lyme_presence"] = (epi["lyme_cases"] > 0).astype(int)
    epi["target_kme_presence"] = (epi["kme_cases"] > 0).astype(int)

    feature_frame = epi[
        [
            "week_start",
            "week_end",
            "obcina_sifra",
            "obcina_naziv",
            *EPIDEMIOLOGY_FEATURE_COLUMNS,
            *TARGET_COLUMNS,
        ]
    ].copy()

    diagnostics = {
        "epidemiology_week_min": epi["week_start"].min().date().isoformat(),
        "epidemiology_week_max": epi["week_start"].max().date().isoformat(),
        "lag_missing_counts": {
            column: int(feature_frame[column].isna().sum()) for column in EPIDEMIOLOGY_FEATURE_COLUMNS
        },
    }
    return feature_frame, diagnostics


def build_weekly_tick_borne_catboost_dataset(
    *,
    weather_dem_input: Path = DEFAULT_WEATHER_DEM_INPUT,
    clc_input: Path = DEFAULT_CLC_INPUT,
    log_population_input: Path = DEFAULT_LOG_POPULATION_INPUT,
    population_density_input: Path = DEFAULT_POPULATION_DENSITY_INPUT,
    epidemiology_input: Path = DEFAULT_EPIDEMIOLOGY_INPUT,
) -> TickBorneCatBoostTables:
    import pandas as pd

    weather_dem = _load_csv(weather_dem_input, label="Weekly weather + DEM")
    clc = _load_csv(clc_input, label="CLC features")
    log_population = _load_csv(log_population_input, label="SURS log-population")
    population_density = _load_csv(
        population_density_input,
        label="SURS population density",
    )
    epidemiology = _load_csv(epidemiology_input, label="Weekly epidemiology")

    _ensure_columns(
        weather_dem,
        ["week_start", "week_end", "obcina_sifra", "obcina_naziv"],
        label="Weekly weather + DEM",
    )

    combined = weather_dem.copy()
    combined["week_start"] = pd.to_datetime(combined["week_start"], errors="raise")
    combined["week_end"] = pd.to_datetime(combined["week_end"], errors="raise")

    if "year" in combined.columns:
        combined["year"] = pd.to_numeric(combined["year"], errors="raise").astype(int)
    else:
        combined["year"] = combined["week_start"].dt.year.astype(int)

    combined = combined.sort_values(["obcina_sifra", "week_start"], kind="stable").reset_index(drop=True)

    combined, clc_diagnostics = _merge_static_features(
        combined,
        clc,
        label="CLC feature CSV",
        feature_columns=CLC_FEATURE_COLUMNS,
    )
    combined["dominant_clc_code"] = combined["dominant_clc_code"].astype("Int64").astype(str)

    combined, log_population_diagnostics = _attach_latest_yearly_feature(
        combined,
        log_population,
        label="SURS log-population",
        value_column="log_population_total",
        source_year_column="log_population_total_source_year",
    )
    combined, population_density_diagnostics = _attach_latest_yearly_feature(
        combined,
        population_density,
        label="SURS population density",
        value_column="population_density_per_km2",
        source_year_column="population_density_source_year",
    )

    epidemiology_features, epidemiology_diagnostics = _build_epidemiology_features(epidemiology)
    combined = combined.merge(
        epidemiology_features,
        on=["week_start", "obcina_sifra"],
        how="left",
        validate="one_to_one",
        suffixes=("", "_epidemiology"),
    )

    if "obcina_naziv_epidemiology" in combined.columns:
        mismatch = combined[
            combined["obcina_naziv_epidemiology"].notna()
            & (combined["obcina_naziv"].astype(str) != combined["obcina_naziv_epidemiology"].astype(str))
        ]
        if not mismatch.empty:
            sample = mismatch.iloc[0]
            raise ValueError(
                "Municipality name mismatch between base data and epidemiology for code "
                f"{sample['obcina_sifra']}: base='{sample['obcina_naziv']}', "
                f"epidemiology='{sample['obcina_naziv_epidemiology']}'"
            )
        combined = combined.drop(columns=["obcina_naziv_epidemiology"])

    if "week_end_epidemiology" in combined.columns:
        week_end_mismatch = combined[
            combined["week_end_epidemiology"].notna()
            & (combined["week_end"] != combined["week_end_epidemiology"])
        ]
        if not week_end_mismatch.empty:
            sample = week_end_mismatch.iloc[0]
            raise ValueError(
                "Week boundary mismatch between base data and epidemiology for "
                f"{sample['obcina_sifra']} / {sample['week_start'].date().isoformat()}."
            )
        combined = combined.drop(columns=["week_end_epidemiology"])

    missing_targets = combined[TARGET_COLUMNS].isna().any(axis=1)
    if missing_targets.any():
        sample_rows = combined.loc[missing_targets, ["obcina_sifra", "week_start"]].head(10)
        formatted = [
            f"{row.obcina_sifra}:{row.week_start.date().isoformat()}"
            for row in sample_rows.itertuples(index=False)
        ]
        raise ValueError(
            "Missing epidemiology targets after join for municipality/week rows: " + ", ".join(formatted)
        )

    combined = combined.sort_values(["week_start", "obcina_sifra"], kind="stable").reset_index(drop=True)

    ordered_columns = [
        *weather_dem.columns.tolist(),
        *CLC_FEATURE_COLUMNS,
        "log_population_total",
        "log_population_total_source_year",
        "population_density_per_km2",
        "population_density_source_year",
        *EPIDEMIOLOGY_FEATURE_COLUMNS,
        *TARGET_COLUMNS,
    ]
    ordered_columns = [column for column in ordered_columns if column in combined.columns]
    combined = combined[ordered_columns].copy()

    combined["week_start"] = combined["week_start"].dt.date.astype(str)
    combined["week_end"] = combined["week_end"].dt.date.astype(str)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "weather_dem_input": str(weather_dem_input.resolve()),
        "clc_input": str(clc_input.resolve()),
        "log_population_input": str(log_population_input.resolve()),
        "population_density_input": str(population_density_input.resolve()),
        "epidemiology_input": str(epidemiology_input.resolve()),
        "row_count": int(len(combined)),
        "municipality_count": int(combined["obcina_sifra"].astype(str).nunique()),
        "week_count": int(combined["week_start"].nunique()),
        "week_start_min": combined["week_start"].min() if not combined.empty else None,
        "week_start_max": combined["week_start"].max() if not combined.empty else None,
        "added_clc_columns": CLC_FEATURE_COLUMNS,
        "added_surs_columns": [
            "log_population_total",
            "log_population_total_source_year",
            "population_density_per_km2",
            "population_density_source_year",
        ],
        "added_epidemiology_feature_columns": EPIDEMIOLOGY_FEATURE_COLUMNS,
        "target_columns": TARGET_COLUMNS,
        "recommended_feature_columns": [
            column for column in RECOMMENDED_FEATURE_COLUMNS if column in combined.columns
        ],
        "recommended_categorical_columns": [
            column for column in RECOMMENDED_CATEGORICAL_COLUMNS if column in combined.columns
        ],
        "clc_name_mismatch_count": clc_diagnostics["name_mismatch_count"],
        "clc_name_mismatch_codes_sample": clc_diagnostics["name_mismatch_codes_sample"],
        "log_population_name_mismatch_count": log_population_diagnostics["name_mismatch_count"],
        "log_population_name_mismatch_codes_sample": log_population_diagnostics[
            "name_mismatch_codes_sample"
        ],
        "population_density_name_mismatch_count": population_density_diagnostics[
            "name_mismatch_count"
        ],
        "population_density_name_mismatch_codes_sample": population_density_diagnostics[
            "name_mismatch_codes_sample"
        ],
        "log_population_forward_fill_years": log_population_diagnostics["forward_fill_years"],
        "population_density_forward_fill_years": population_density_diagnostics[
            "forward_fill_years"
        ],
        "lag_missing_counts": epidemiology_diagnostics["lag_missing_counts"],
        "methodology_notes": [
            "Weekly targets use the current municipality/week case counts.",
            "All epidemiology lag features are computed only from past weeks.",
            "prev_4w_sum and prev_8w_sum use full prior windows and do not include the current week.",
            "Annual SURS features are attached with the latest available source year that is not in the future.",
            "No current-week Lyme/KME counts are exposed as model features in the exported dataset.",
            "CatBoost training should use time-ordered splits by week_start, not random row splits.",
        ],
        "combined_columns": combined.columns.tolist(),
    }
    return TickBorneCatBoostTables(combined=combined, manifest=manifest)


def write_weekly_tick_borne_catboost_dataset(
    tables: TickBorneCatBoostTables,
    *,
    output_path: Path = DEFAULT_OUTPUT,
    manifest_output: Path = DEFAULT_MANIFEST_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)

    tables.combined.to_csv(output_path, index=False)
    manifest_output.write_text(json.dumps(tables.manifest, indent=2, ensure_ascii=True) + "\n")
