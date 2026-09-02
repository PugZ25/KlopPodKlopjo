from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

from pipeline_utils import (
    CLC_SUMMARY_OUTPUT,
    DEM_SUMMARY_OUTPUT,
    MUNICIPALITY_MONTHLY_PANEL_OUTPUT,
    MUNICIPALITY_WEEKLY_PANEL_OUTPUT,
    PANEL_MANIFEST_OUTPUT,
    REFERENCE_NIJZ_WEEKLY,
    REFERENCE_POPULATION,
    SLOVENIA_MONTHLY_PANEL_OUTPUT,
    SLOVENIA_YEARLY_PANEL_OUTPUT,
    WEATHER_WEEKLY_OUTPUT,
    ensure_project_dirs,
    timestamp_utc,
    write_json,
)


WEATHER_MEAN_COLUMNS = [
    "air_temperature_c_mean",
    "air_temperature_c_min",
    "air_temperature_c_max",
    "air_temperature_c_std",
    "relative_humidity_pct_mean",
    "relative_humidity_pct_min",
    "relative_humidity_pct_max",
    "soil_temperature_level_1_c_mean",
    "soil_temperature_level_2_c_mean",
    "soil_water_layer_1_m3_m3_mean",
    "soil_water_layer_2_m3_m3_mean",
    "air_temperature_c_range",
    "covered_area_pct",
]

WEATHER_SUM_COLUMNS = [
    "observation_days_count",
    "precipitation_sum_mm",
    "humidity_hours_ge_80_sum",
    "humidity_hours_ge_90_sum",
    "wet_hours_ge_0_1mm_sum",
    "tick_activity_window_hours_sum",
    "growing_degree_hours_base_5_c_sum",
    "rainy_days_ge_1mm_count",
    "humid_days_ge_16h_count",
    "tick_favorable_days_ge_6h_count",
]

WEATHER_MAX_COLUMNS = [
    "precipitation_daily_max_mm",
]

STATIC_FIRST_COLUMNS = [
    "obcina_naziv",
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
]

CASE_COLUMNS = ["lyme_cases", "kme_cases", "tick_borne_cases_total"]

MONTHLY_ENV_COLUMNS = WEATHER_MEAN_COLUMNS + WEATHER_SUM_COLUMNS + WEATHER_MAX_COLUMNS
MONTHLY_STATIC_COLUMNS = [column for column in STATIC_FIRST_COLUMNS if column != "obcina_naziv"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build municipality-week, municipality-month, Slovenia-month, and Slovenia-year "
            "predictive panels in the predictive workspace."
        )
    )
    parser.add_argument("--weather-input", default=str(WEATHER_WEEKLY_OUTPUT))
    parser.add_argument("--dem-input", default=str(DEM_SUMMARY_OUTPUT))
    parser.add_argument("--clc-input", default=str(CLC_SUMMARY_OUTPUT))
    parser.add_argument("--epi-input", default=str(REFERENCE_NIJZ_WEEKLY))
    parser.add_argument("--population-input", default=str(REFERENCE_POPULATION))
    parser.add_argument("--weekly-output", default=str(MUNICIPALITY_WEEKLY_PANEL_OUTPUT))
    parser.add_argument("--municipality-monthly-output", default=str(MUNICIPALITY_MONTHLY_PANEL_OUTPUT))
    parser.add_argument("--slovenia-monthly-output", default=str(SLOVENIA_MONTHLY_PANEL_OUTPUT))
    parser.add_argument("--slovenia-yearly-output", default=str(SLOVENIA_YEARLY_PANEL_OUTPUT))
    parser.add_argument("--manifest-output", default=str(PANEL_MANIFEST_OUTPUT))
    return parser


def normalize_code(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.astype("Int64").astype(str).str.replace("<NA>", "", regex=False)


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def attach_population(weekly_df: pd.DataFrame, population_df: pd.DataFrame) -> pd.DataFrame:
    pop = population_df.copy()
    pop["obcina_sifra"] = normalize_code(pop["obcina_sifra"])
    pop["year"] = pd.to_numeric(pop["year"], errors="coerce").astype("Int64")
    pop["population_total"] = pd.to_numeric(pop["population_total"], errors="coerce")
    pop["population_density_per_km2"] = pd.to_numeric(
        pop["population_density_per_km2"], errors="coerce"
    )
    pop = pop.sort_values(["obcina_sifra", "year"])

    required_keys = weekly_df[["obcina_sifra", "year"]].drop_duplicates().copy()
    required_keys["year"] = pd.to_numeric(required_keys["year"], errors="coerce").astype("Int64")
    merged = required_keys.merge(
        pop[["obcina_sifra", "year", "population_total", "population_density_per_km2"]],
        on=["obcina_sifra", "year"],
        how="left",
    )
    merged["population_source_year"] = merged["year"]
    merged = merged.sort_values(["obcina_sifra", "year"])
    merged[["population_total", "population_density_per_km2", "population_source_year"]] = (
        merged.groupby("obcina_sifra")[
            ["population_total", "population_density_per_km2", "population_source_year"]
        ].ffill()
    )

    return weekly_df.merge(
        merged,
        on=["obcina_sifra", "year"],
        how="left",
    )


def join_weekly_panel(
    weather_df: pd.DataFrame,
    dem_df: pd.DataFrame,
    clc_df: pd.DataFrame,
    epi_df: pd.DataFrame,
    population_df: pd.DataFrame,
) -> pd.DataFrame:
    weather = weather_df.copy()
    weather["obcina_sifra"] = normalize_code(weather["obcina_sifra"])
    weather["week_start"] = pd.to_datetime(weather["week_start"])
    weather["week_end"] = pd.to_datetime(weather["week_end"])
    weather["year"] = pd.to_numeric(weather["year"], errors="coerce").astype("Int64")

    dem = dem_df.copy()
    dem["obcina_sifra"] = normalize_code(dem["obcina_sifra"])

    clc = clc_df.copy()
    clc["obcina_sifra"] = normalize_code(clc["obcina_sifra"])

    epi = epi_df.copy()
    epi["obcina_sifra"] = normalize_code(epi["obcina_sifra"])
    epi["week_start"] = pd.to_datetime(epi["week_start"])
    epi["week_end"] = pd.to_datetime(epi["week_end"])
    for column in CASE_COLUMNS:
        epi[column] = pd.to_numeric(epi[column], errors="coerce").fillna(0.0)

    weekly = weather.merge(
        epi[["week_start", "week_end", "obcina_sifra", *CASE_COLUMNS]],
        on=["week_start", "week_end", "obcina_sifra"],
        how="left",
    )
    weekly[CASE_COLUMNS] = weekly[CASE_COLUMNS].fillna(0.0)
    weekly = attach_population(weekly, population_df)
    weekly = weekly.merge(
        dem[["obcina_sifra", "elevation_m_mean", "elevation_m_std", "elevation_m_range"]],
        on="obcina_sifra",
        how="left",
    )
    weekly = weekly.merge(
        clc[
            [
                "obcina_sifra",
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
            ]
        ],
        on="obcina_sifra",
        how="left",
    )

    weekly["month_midpoint"] = weekly["week_start"] + pd.to_timedelta(3, unit="D")
    weekly["month_start"] = weekly["month_midpoint"].dt.to_period("M").dt.to_timestamp()
    weekly["month"] = weekly["month_start"].dt.month
    weekly["month_of_year_sin"] = weekly["month"].map(
        lambda value: math.sin((2.0 * math.pi * value) / 12.0)
    )
    weekly["month_of_year_cos"] = weekly["month"].map(
        lambda value: math.cos((2.0 * math.pi * value) / 12.0)
    )
    return weekly


def build_municipality_monthly_panel(weekly_df: pd.DataFrame) -> pd.DataFrame:
    group_keys = ["obcina_sifra", "month_start"]
    monthly = weekly_df.groupby(group_keys, as_index=False).agg(
        {
            **{column: "mean" for column in WEATHER_MEAN_COLUMNS},
            **{column: "sum" for column in WEATHER_SUM_COLUMNS},
            **{column: "max" for column in WEATHER_MAX_COLUMNS},
            **{column: "first" for column in STATIC_FIRST_COLUMNS},
            **{column: "sum" for column in CASE_COLUMNS},
        }
    )
    monthly["year"] = monthly["month_start"].dt.year
    monthly["month"] = monthly["month_start"].dt.month
    monthly["month_end"] = monthly["month_start"] + pd.offsets.MonthEnd(1)
    monthly["month_of_year_sin"] = monthly["month"].map(
        lambda value: math.sin((2.0 * math.pi * value) / 12.0)
    )
    monthly["month_of_year_cos"] = monthly["month"].map(
        lambda value: math.cos((2.0 * math.pi * value) / 12.0)
    )
    monthly["lyme_cases_per_100k"] = (
        monthly["lyme_cases"] / monthly["population_total"] * 100000.0
    )
    monthly["kme_cases_per_100k"] = (
        monthly["kme_cases"] / monthly["population_total"] * 100000.0
    )
    monthly["tick_borne_cases_total_per_100k"] = (
        monthly["tick_borne_cases_total"] / monthly["population_total"] * 100000.0
    )
    return monthly.sort_values(["obcina_sifra", "month_start"]).reset_index(drop=True)


def _weighted_average(frame: pd.DataFrame, column: str, weight_column: str) -> float:
    values = pd.to_numeric(frame[column], errors="coerce")
    weights = pd.to_numeric(frame[weight_column], errors="coerce")
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return float("nan")
    return float((values[valid] * weights[valid]).sum() / weights[valid].sum())


def build_slovenia_monthly_panel(municipality_monthly_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month_start, frame in municipality_monthly_df.groupby("month_start", sort=True):
        row: dict[str, object] = {
            "month_start": month_start,
            "year": int(frame["year"].iloc[0]),
            "month": int(frame["month"].iloc[0]),
            "month_end": frame["month_end"].iloc[0],
            "municipality_count": int(frame["obcina_sifra"].nunique()),
            "population_total": float(pd.to_numeric(frame["population_total"], errors="coerce").sum()),
            "lyme_cases": float(pd.to_numeric(frame["lyme_cases"], errors="coerce").sum()),
            "kme_cases": float(pd.to_numeric(frame["kme_cases"], errors="coerce").sum()),
            "tick_borne_cases_total": float(
                pd.to_numeric(frame["tick_borne_cases_total"], errors="coerce").sum()
            ),
            "month_of_year_sin": float(frame["month_of_year_sin"].iloc[0]),
            "month_of_year_cos": float(frame["month_of_year_cos"].iloc[0]),
        }
        for column in MONTHLY_ENV_COLUMNS + MONTHLY_STATIC_COLUMNS:
            row[column] = _weighted_average(frame, column, "population_total")
        row["lyme_cases_per_100k"] = row["lyme_cases"] / row["population_total"] * 100000.0
        row["kme_cases_per_100k"] = row["kme_cases"] / row["population_total"] * 100000.0
        row["tick_borne_cases_total_per_100k"] = (
            row["tick_borne_cases_total"] / row["population_total"] * 100000.0
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("month_start").reset_index(drop=True)


def build_slovenia_yearly_panel(slovenia_monthly_df: pd.DataFrame) -> pd.DataFrame:
    yearly = slovenia_monthly_df.groupby("year", as_index=False).agg(
        {
            **{column: "mean" for column in WEATHER_MEAN_COLUMNS},
            **{column: "sum" for column in WEATHER_SUM_COLUMNS},
            **{column: "max" for column in WEATHER_MAX_COLUMNS},
            **{column: "mean" for column in MONTHLY_STATIC_COLUMNS},
            "population_total": "mean",
            "lyme_cases": "sum",
            "kme_cases": "sum",
            "tick_borne_cases_total": "sum",
            "municipality_count": "max",
        }
    )
    yearly["year_start"] = pd.to_datetime(yearly["year"].astype(str) + "-01-01")
    yearly["year_end"] = pd.to_datetime(yearly["year"].astype(str) + "-12-31")
    yearly["lyme_cases_per_100k"] = yearly["lyme_cases"] / yearly["population_total"] * 100000.0
    yearly["kme_cases_per_100k"] = yearly["kme_cases"] / yearly["population_total"] * 100000.0
    yearly["tick_borne_cases_total_per_100k"] = (
        yearly["tick_borne_cases_total"] / yearly["population_total"] * 100000.0
    )
    return yearly.sort_values("year").reset_index(drop=True)


def dataframe_summary(df: pd.DataFrame, *, date_column: str | None = None) -> dict[str, object]:
    summary = {"row_count": int(len(df)), "column_count": int(len(df.columns))}
    if date_column is not None and date_column in df.columns and not df.empty:
        summary["min_date"] = str(pd.to_datetime(df[date_column]).min().date())
        summary["max_date"] = str(pd.to_datetime(df[date_column]).max().date())
    return summary


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ensure_project_dirs()

    try:
        weather_df = load_csv(Path(args.weather_input))
        dem_df = load_csv(Path(args.dem_input))
        clc_df = load_csv(Path(args.clc_input))
        epi_df = load_csv(Path(args.epi_input))
        population_df = load_csv(Path(args.population_input))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    weekly_panel = join_weekly_panel(weather_df, dem_df, clc_df, epi_df, population_df)
    municipality_monthly = build_municipality_monthly_panel(weekly_panel)
    slovenia_monthly = build_slovenia_monthly_panel(municipality_monthly)
    slovenia_yearly = build_slovenia_yearly_panel(slovenia_monthly)

    weekly_output = Path(args.weekly_output)
    municipality_monthly_output = Path(args.municipality_monthly_output)
    slovenia_monthly_output = Path(args.slovenia_monthly_output)
    slovenia_yearly_output = Path(args.slovenia_yearly_output)
    manifest_output = Path(args.manifest_output)

    weekly_output.parent.mkdir(parents=True, exist_ok=True)
    slovenia_monthly_output.parent.mkdir(parents=True, exist_ok=True)

    weekly_panel.to_csv(weekly_output, index=False, encoding="utf-8-sig")
    municipality_monthly.to_csv(municipality_monthly_output, index=False, encoding="utf-8-sig")
    slovenia_monthly.to_csv(slovenia_monthly_output, index=False, encoding="utf-8-sig")
    slovenia_yearly.to_csv(slovenia_yearly_output, index=False, encoding="utf-8-sig")

    manifest = {
        "generated_at_utc": timestamp_utc(),
        "inputs": {
            "weather_input": str(Path(args.weather_input)),
            "dem_input": str(Path(args.dem_input)),
            "clc_input": str(Path(args.clc_input)),
            "epi_input": str(Path(args.epi_input)),
            "population_input": str(Path(args.population_input)),
        },
        "outputs": {
            "weekly_panel": str(weekly_output),
            "municipality_monthly_panel": str(municipality_monthly_output),
            "slovenia_monthly_panel": str(slovenia_monthly_output),
            "slovenia_yearly_panel": str(slovenia_yearly_output),
        },
        "weekly_panel_summary": dataframe_summary(weekly_panel, date_column="week_start"),
        "municipality_monthly_summary": dataframe_summary(
            municipality_monthly, date_column="month_start"
        ),
        "slovenia_monthly_summary": dataframe_summary(slovenia_monthly, date_column="month_start"),
        "slovenia_yearly_summary": dataframe_summary(slovenia_yearly, date_column="year_start"),
    }
    write_json(manifest_output, manifest)

    print("Predictive panels built successfully.")
    print(f"- weekly panel rows: {len(weekly_panel)}")
    print(f"- municipality-month rows: {len(municipality_monthly)}")
    print(f"- slovenia-month rows: {len(slovenia_monthly)}")
    print(f"- slovenia-year rows: {len(slovenia_yearly)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
