#!/usr/bin/env python3
"""Create a reviewable variable-flag registry for the master weekly panel."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
INTERIM_DIR = DATA_DIR / "interim"
MODEL_STAGING_DIR = INTERIM_DIR / "model_staging"
LIVING_README_PATH = INTERIM_DIR / "Slovenia_local_data_normalized" / "README_LOCAL_DATA_NORMALIZATION.md"

MASTER_PANEL_PATH = MODEL_STAGING_DIR / "master_weekly_panel_enriched_all_sources.csv"
FLAG_REGISTRY_PATH = MODEL_STAGING_DIR / "master_panel_variable_flags.csv"
FLAG_SUMMARY_PATH = MODEL_STAGING_DIR / "master_panel_variable_flag_summary.csv"
HIGH_PRIORITY_PATH = MODEL_STAGING_DIR / "master_panel_variable_flags_high_priority.csv"
REPORT_PATH = MODEL_STAGING_DIR / "MASTER_PANEL_VARIABLE_FLAGS_REPORT.md"

KEY_COLUMNS = {"obcina_sifra", "obcina_naziv"}
INDEX_ONLY_COLUMNS = {"week_start", "week_end"}
TIME_CONTROL_COLUMNS = {"year", "month", "iso_year", "iso_week", "week_of_year_sin", "week_of_year_cos"}
CURRENT_CASE_COLUMNS = {"lyme_cases", "kme_cases", "tick_borne_cases_total"}
POPULATION_COLUMNS = {"population_total", "population_density_per_km2"}
LAND_COVER_COLUMNS = {
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
}
PROCESSING_METADATA_COLUMNS = {
    "observation_days_count",
    "grid_cell_count",
    "municipality_area_m2",
    "covered_area_pct",
    "overlay_method",
    "population_total_source_year",
    "population_density_source_year",
    "dominant_clc_label",
    "arso_source_month_key",
    "obrod_source_calendar_year",
}
COVERAGE_FLAG_COLUMNS = {
    "has_clc_static",
    "has_arso_local",
    "has_gozdis_local",
    "has_obrod_local",
    "local_sources_present_count",
}
REMOVED_TICK_ACTIVITY_PREFIXES = ("tick_activity_", "growing_degree_", "tick_favorable_")
COPERNICUS_WEATHER_PREFIXES = (
    "air_temperature_",
    "relative_humidity_",
    "precipitation_",
    "soil_temperature_",
    "soil_water_",
    "humidity_hours_",
    "wet_hours_",
    "rainy_days_",
    "humid_days_",
)

COPERNICUS_TEMPERATURE_PREFIXES = ("air_temperature_",)
COPERNICUS_HUMIDITY_PREFIXES = ("relative_humidity_", "humidity_hours_", "humid_days_")
COPERNICUS_PRECIPITATION_PREFIXES = ("precipitation_", "rainy_days_", "wet_hours_")
COPERNICUS_SOIL_PREFIXES = ("soil_temperature_", "soil_water_")

ARSO_GROUP_MAP = {
    "arso_air_temperature_mean_c": ("local_temperature", "arso_temperature"),
    "arso_relative_humidity_mean_pct": ("local_humidity", "arso_humidity"),
    "arso_precipitation_sum_mm": ("local_precipitation", "arso_precipitation"),
}
GOZDIS_TEMPERATURE_COLUMNS = {
    "gozdis_air_temperature_mean_c",
    "gozdis_air_temperature_min_c",
    "gozdis_air_temperature_max_c",
}
GOZDIS_HUMIDITY_COLUMNS = {
    "gozdis_relative_humidity_mean_pct",
    "gozdis_relative_humidity_min_pct",
    "gozdis_relative_humidity_max_pct",
}
GOZDIS_PRECIPITATION_COLUMNS = {"gozdis_precipitation_sum_mm"}


def classify_copernicus_weather(column_name: str) -> tuple[str, str]:
    if column_name.startswith(COPERNICUS_TEMPERATURE_PREFIXES):
        return "weather_temperature", "copernicus_temperature"
    if column_name.startswith(COPERNICUS_HUMIDITY_PREFIXES):
        return "weather_humidity", "copernicus_humidity"
    if column_name.startswith(COPERNICUS_PRECIPITATION_PREFIXES):
        return "weather_precipitation", "copernicus_precipitation"
    if column_name.startswith(COPERNICUS_SOIL_PREFIXES):
        return "weather_soil", "copernicus_soil"
    return "weather", "copernicus_weather_unclassified"


def classify_local_weather(column_name: str) -> tuple[str, str]:
    if column_name in ARSO_GROUP_MAP:
        return ARSO_GROUP_MAP[column_name]
    if column_name in GOZDIS_TEMPERATURE_COLUMNS:
        return "local_temperature", "gozdis_temperature"
    if column_name in GOZDIS_HUMIDITY_COLUMNS:
        return "local_humidity", "gozdis_humidity"
    if column_name in GOZDIS_PRECIPITATION_COLUMNS:
        return "local_precipitation", "gozdis_precipitation"
    return "local_weather", "local_weather_unclassified"


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def flag_row(
    column_name: str,
    source_group: str,
    feature_family: str,
    time_alignment: str,
    interpretable_action: str,
    forecasting_action: str,
    graph_group: str,
    review_priority: str,
    rationale: str,
) -> dict[str, str]:
    return {
        "column_name": column_name,
        "source_group": source_group,
        "feature_family": feature_family,
        "time_alignment": time_alignment,
        "interpretable_action": interpretable_action,
        "forecasting_action": forecasting_action,
        "graph_group": graph_group,
        "review_priority": review_priority,
        "rationale": rationale,
    }


def classify_column(column_name: str) -> dict[str, str]:
    if column_name == "obcina_sifra":
        return flag_row(
            column_name=column_name,
            source_group="panel_index",
            feature_family="location_key",
            time_alignment="weekly_panel_index",
            interpretable_action="group_only",
            forecasting_action="optional_predictive_only",
            graph_group="not_in_graph",
            review_priority="high",
            rationale="Municipality code is needed for joins and grouped lag generation, but it should not be treated as an explanatory factor.",
        )

    if column_name == "obcina_naziv":
        return flag_row(
            column_name=column_name,
            source_group="panel_index",
            feature_family="location_label",
            time_alignment="weekly_panel_index",
            interpretable_action="group_only",
            forecasting_action="group_only",
            graph_group="not_in_graph",
            review_priority="low",
            rationale="Municipality name is a human-readable label for validation and joins, not a modeling feature.",
        )

    if column_name in INDEX_ONLY_COLUMNS:
        return flag_row(
            column_name=column_name,
            source_group="panel_index",
            feature_family="time_index",
            time_alignment="weekly_panel_index",
            interpretable_action="index_only",
            forecasting_action="index_only",
            graph_group="not_in_graph",
            review_priority="low",
            rationale="Raw date fields keep the panel ordered and auditable, but engineered time controls should be used instead of raw dates in the model matrix.",
        )

    if column_name in TIME_CONTROL_COLUMNS:
        return flag_row(
            column_name=column_name,
            source_group="pipeline",
            feature_family="raw_calendar_control",
            time_alignment="derived_from_week_index",
            interpretable_action="replace_with_hidden_time_control",
            forecasting_action="replace_with_hidden_time_control",
            graph_group="not_in_graph",
            review_priority="medium",
            rationale="These raw calendar fields are redundant as direct predictors in this branch. They are replaced downstream by a minimal hidden annual-phase control derived from the weekly date.",
        )

    if column_name in CURRENT_CASE_COLUMNS:
        return flag_row(
            column_name=column_name,
            source_group="nijz",
            feature_family="current_epidemiology",
            time_alignment="weekly_direct",
            interpretable_action="target_source_only",
            forecasting_action="target_source_only",
            graph_group="not_in_graph",
            review_priority="high",
            rationale="Current disease counts are part of the observed outcome source. In the environmental explanation track they should define the target, not act as explanatory predictors.",
        )

    if column_name in PROCESSING_METADATA_COLUMNS:
        return flag_row(
            column_name=column_name,
            source_group="pipeline",
            feature_family="processing_metadata",
            time_alignment="mixed_support_metadata",
            interpretable_action="exclude_metadata",
            forecasting_action="exclude_metadata",
            graph_group="not_in_graph",
            review_priority="low",
            rationale="This column mainly describes source construction, spatial coverage, or bookkeeping rather than biology or exposure.",
        )

    if column_name in COVERAGE_FLAG_COLUMNS:
        return flag_row(
            column_name=column_name,
            source_group="pipeline",
            feature_family="coverage_flag",
            time_alignment="source_availability_marker",
            interpretable_action="exclude_coverage_flag",
            forecasting_action="review_missingness_proxy",
            graph_group="not_in_graph",
            review_priority="medium",
            rationale="Coverage flags are useful for auditing source presence. They should stay out of the interpretable factor ranking, though some predictive runs may later test them as missingness proxies.",
        )

    if column_name.startswith(REMOVED_TICK_ACTIVITY_PREFIXES):
        return flag_row(
            column_name=column_name,
            source_group="copernicus",
            feature_family="retired_tick_activity_proxy",
            time_alignment="weekly_direct_or_precomputed_history",
            interpretable_action="exclude_retired_tick_activity_proxy",
            forecasting_action="exclude_retired_tick_activity_proxy",
            graph_group="not_in_graph",
            review_priority="low",
            rationale="This Copernicus tick-activity proxy block is intentionally retired from okoljski_raziskovalni_model so it does not mix derived tick-activity assumptions into the main factor comparison.",
        )

    if column_name.startswith("arso_"):
        feature_family, graph_group = classify_local_weather(column_name)
        return flag_row(
            column_name=column_name,
            source_group="arso",
            feature_family=feature_family,
            time_alignment="monthly_to_weekly",
            interpretable_action="include_local_optional",
            forecasting_action="include_local_optional",
            graph_group=graph_group,
            review_priority="low",
            rationale="ARSO remains in the pipeline as a local optional source, but it is now split by weather factor so temperature, humidity, and precipitation can be judged separately.",
        )

    if column_name.startswith("gozdis_"):
        feature_family, graph_group = classify_local_weather(column_name)
        return flag_row(
            column_name=column_name,
            source_group="gozdis",
            feature_family=feature_family,
            time_alignment="weekly_local_direct",
            interpretable_action="include_local_optional",
            forecasting_action="include_local_optional",
            graph_group=graph_group,
            review_priority="low",
            rationale="GOZDIS remains in the pipeline as a local optional source, but it is now split by weather factor so temperature, humidity, and precipitation can be judged separately.",
        )

    if column_name == "obrod_species_nonmissing_count" or column_name.startswith("obrod_species_"):
        return flag_row(
            column_name=column_name,
            source_group="obrod",
            feature_family="local_forestry_species_detail",
            time_alignment="yearly_to_weekly",
            interpretable_action="exclude_sparse_detail",
            forecasting_action="review_sparse_detail",
            graph_group="not_in_graph",
            review_priority="medium",
            rationale="Species-level OBROD detail is sparse and hard to compare consistently across municipalities, so it should be reviewed separately from the main interpretable pipeline.",
        )

    if column_name.startswith("obrod_"):
        return flag_row(
            column_name=column_name,
            source_group="obrod",
            feature_family="local_forestry_summary",
            time_alignment="yearly_to_weekly",
            interpretable_action="include_local_optional",
            forecasting_action="include_local_optional",
            graph_group="obrod_summary",
            review_priority="low",
            rationale="OBROD summary measures preserve the local forestry signal without forcing sparse species-level detail into the main model.",
        )

    if column_name.startswith("elevation_"):
        return flag_row(
            column_name=column_name,
            source_group="copernicus",
            feature_family="topography",
            time_alignment="static_repeated_to_week",
            interpretable_action="include_core_predictor",
            forecasting_action="include_core_predictor",
            graph_group="topography",
            review_priority="low",
            rationale="Topography is stable environmental context and should stay in the core predictor set.",
        )

    if column_name in POPULATION_COLUMNS:
        return flag_row(
            column_name=column_name,
            source_group="copernicus",
            feature_family="population",
            time_alignment="yearly_repeated_to_week",
            interpretable_action="include_core_predictor",
            forecasting_action="include_core_predictor",
            graph_group="population",
            review_priority="low",
            rationale="Population context is needed for exposure scale and municipality comparability.",
        )

    if column_name in LAND_COVER_COLUMNS:
        review_priority = "medium" if column_name == "dominant_clc_code" else "low"
        return flag_row(
            column_name=column_name,
            source_group="copernicus",
            feature_family="land_cover",
            time_alignment="static_repeated_to_week",
            interpretable_action="include_core_predictor",
            forecasting_action="include_core_predictor",
            graph_group="land_cover",
            review_priority=review_priority,
            rationale="Land-cover structure is a core ecological signal and should remain available for interpretable environmental analysis.",
        )

    if column_name.startswith(COPERNICUS_WEATHER_PREFIXES):
        feature_family, graph_group = classify_copernicus_weather(column_name)
        return flag_row(
            column_name=column_name,
            source_group="copernicus",
            feature_family=feature_family,
            time_alignment="weekly_direct_or_precomputed_history",
            interpretable_action="include_core_predictor",
            forecasting_action="include_core_predictor",
            graph_group=graph_group,
            review_priority="low",
            rationale="Copernicus weather remains the national backbone, but it is now split into smaller scientific factor families so broad mixed weather blocks do not hide which signal is helping.",
        )

    return flag_row(
        column_name=column_name,
        source_group="unclassified",
        feature_family="review_needed",
        time_alignment="review_needed",
        interpretable_action="review",
        forecasting_action="review",
        graph_group="review_needed",
        review_priority="high",
        rationale="This column was not matched by the canonical rules and needs manual review before we proceed.",
    )


def build_registry_rows(header: list[str]) -> list[dict[str, str]]:
    return [classify_column(column_name) for column_name in header]


def build_summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    dimensions = ["source_group", "feature_family", "interpretable_action", "forecasting_action", "graph_group", "review_priority"]
    summary_rows: list[dict[str, str]] = []
    for dimension in dimensions:
        counts = Counter(row[dimension] for row in rows)
        for value, count in sorted(counts.items()):
            summary_rows.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "column_count": str(count),
                }
            )
    return summary_rows


def write_report(rows: list[dict[str, str]], summary_rows: list[dict[str, str]]) -> None:
    high_priority_rows = [row for row in rows if row["review_priority"] == "high"]
    excluded_rows = [
        row
        for row in rows
        if row["interpretable_action"] in {"exclude_metadata", "exclude_coverage_flag", "exclude_sparse_detail", "exclude_retired_tick_activity_proxy"}
    ]
    local_optional_rows = [row for row in rows if row["interpretable_action"] == "include_local_optional"]

    lines = [
        "# Master Panel Variable Flags",
        "",
        "This report classifies every column in the canonical weekly municipality panel so we can manually review what should be grouped, excluded, or modeled.",
        "",
        "## What The Flags Mean",
        "",
        "- `interpretable_action`: how the column should behave in the main explanatory pipeline.",
        "- `forecasting_action`: how the column may behave later in a predictive-only track.",
            "- `graph_group`: the factor family the final source/factor graph would use, except for hidden controls and excluded columns.",
            "- `review_priority`: where manual validation matters most before we continue refactoring the pipeline.",
            "",
        "## Summary Counts",
        "",
        "| Dimension | Value | Columns |",
        "| --- | --- | ---: |",
    ]

    for row in summary_rows:
        lines.append(f"| {row['dimension']} | {row['value']} | {row['column_count']} |")

    lines.extend(
        [
            "",
            "## High-Priority Manual Review",
            "",
            "These are the columns most worth checking before we freeze the canonical modeling rules.",
            "",
            "| Column | Interpretable Action | Forecasting Action | Why Review It |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in high_priority_rows:
        lines.append(
            f"| {row['column_name']} | {row['interpretable_action']} | {row['forecasting_action']} | {row['rationale']} |"
        )

    lines.extend(
        [
            "",
            "## Local Optional Predictor Families",
            "",
            "These are the local-source columns we keep available because locality matters even when coverage is incomplete.",
            "",
            "| Column | Source Group | Time Alignment | Graph Group |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in local_optional_rows:
        lines.append(
            f"| {row['column_name']} | {row['source_group']} | {row['time_alignment']} | {row['graph_group']} |"
        )

    lines.extend(
        [
            "",
            "## Proposed Exclusions From Interpretable Modeling",
            "",
            "These columns are still useful for auditing the panel, but they should stay out of the main explanatory model matrix unless we explicitly revisit them.",
            "",
            "| Column | Feature Family | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for row in excluded_rows:
        lines.append(f"| {row['column_name']} | {row['feature_family']} | {row['rationale']} |")

    lines.extend(
        [
            "",
            "## Current Canonical Reading",
            "",
            "- `Copernicus` remains the national backbone, but weather is now split into smaller scientific factor families rather than one broad mixed block.",
            "- The Copernicus tick-activity proxy block is intentionally retired from this branch so the main comparison stays focused on direct environmental factor families.",
            "- `ARSO` and `GOZDIS` stay in the pipeline as optional local predictor families, split by temperature, humidity, and precipitation where the data allow.",
            "- `OBROD` stays in the pipeline only through its summary forestry features in the main interpretable branch.",
            "- Municipality identity stays available for grouping and validation, but not for the interpretable factor ranking.",
            "- Raw current disease counts stay outcome-source only in this branch. They define the environmental target but are not used as explanatory predictors.",
            "- Raw calendar variables are not fed directly into the model matrix. They are replaced downstream by a minimal hidden annual-phase control.",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def update_living_readme(rows: list[dict[str, str]]) -> None:
    if not LIVING_README_PATH.exists():
        return

    counts = Counter(row["interpretable_action"] for row in rows)
    high_priority_count = sum(1 for row in rows if row["review_priority"] == "high")
    local_optional_count = counts.get("include_local_optional", 0)
    core_count = counts.get("include_core_predictor", 0)
    excluded_count = (
        counts.get("exclude_metadata", 0)
        + counts.get("exclude_coverage_flag", 0)
        + counts.get("exclude_sparse_detail", 0)
        + counts.get("exclude_retired_tick_activity_proxy", 0)
    )

    sections = [
        "",
        "## Variable Flag Review Stage",
        "",
        "The workflow now includes a canonical variable-flag registry for the master weekly panel.",
        "",
        "New script:",
        "",
        "- `scripts/build_master_panel_variable_flags.py`",
        "",
        "New review outputs in `data/interim/model_staging/`:",
        "",
        "- `master_panel_variable_flags.csv`",
        "- `master_panel_variable_flag_summary.csv`",
        "- `master_panel_variable_flags_high_priority.csv`",
        "- `MASTER_PANEL_VARIABLE_FLAGS_REPORT.md`",
        "",
        "Current flag snapshot:",
        "",
        f"- `{core_count}` columns flagged as core interpretable predictors",
        f"- `{local_optional_count}` columns flagged as optional local predictors",
        f"- `{excluded_count}` columns flagged for exclusion from the interpretable model matrix",
        f"- `{high_priority_count}` columns flagged as high-priority manual review items",
        "",
        "Current canonical flow is now intentionally minimal:",
        "",
        "- raw source folders stay unchanged",
        "- `scripts/normalize_slovenia_local_data.py` creates normalized local staging files",
        "- `scripts/build_master_weekly_panel.py` creates the weekly municipality master panel",
        "- `scripts/build_master_panel_variable_flags.py` defines what each master-panel column is allowed to do next",
        "",
        "The old CatBoost output folders remain exploratory for now and are not the canonical next step while the flags are under review.",
    ]

    existing = LIVING_README_PATH.read_text(encoding="utf-8")
    marker = "\n## Variable Flag Review Stage\n"
    if marker in existing:
        existing = existing.split(marker)[0].rstrip()
    updated = existing.rstrip() + "\n" + "\n".join(sections) + "\n"
    LIVING_README_PATH.write_text(updated, encoding="utf-8")


def main() -> None:
    header = read_header(MASTER_PANEL_PATH)
    rows = build_registry_rows(header)
    summary_rows = build_summary_rows(rows)
    high_priority_rows = [row for row in rows if row["review_priority"] == "high"]

    write_csv(
        FLAG_REGISTRY_PATH,
        [
            "column_name",
            "source_group",
            "feature_family",
            "time_alignment",
            "interpretable_action",
            "forecasting_action",
            "graph_group",
            "review_priority",
            "rationale",
        ],
        rows,
    )
    write_csv(
        FLAG_SUMMARY_PATH,
        ["dimension", "value", "column_count"],
        summary_rows,
    )
    write_csv(
        HIGH_PRIORITY_PATH,
        [
            "column_name",
            "source_group",
            "feature_family",
            "time_alignment",
            "interpretable_action",
            "forecasting_action",
            "graph_group",
            "review_priority",
            "rationale",
        ],
        high_priority_rows,
    )
    write_report(rows, summary_rows)
    update_living_readme(rows)

    print("Master panel variable flags written to:")
    print(FLAG_REGISTRY_PATH)
    print(FLAG_SUMMARY_PATH)
    print(HIGH_PRIORITY_PATH)
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
