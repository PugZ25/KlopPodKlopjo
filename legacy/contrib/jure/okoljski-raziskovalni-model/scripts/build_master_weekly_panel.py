#!/usr/bin/env python3
"""Build a reproducible master weekly municipality panel and coverage report."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
COPERNICUS_DIR = RAW_DIR / "Copernicus"
NIJZ_DIR = RAW_DIR / "NIJZ"
LOCAL_NORM_DIR = INTERIM_DIR / "Slovenia_local_data_normalized"
OUTPUT_DIR = INTERIM_DIR / "model_staging"

BASE_PATH = COPERNICUS_DIR / "obcina_weekly_weather_dem_surs_features.csv"
NIJZ_PATH = NIJZ_DIR / "obcina_weekly_epidemiology_KME_Boreliosis.csv"
CLC_PATH = COPERNICUS_DIR / "obcina_clc_features.csv"
ARSO_PATH = LOCAL_NORM_DIR / "arso_weekly_weather_from_monthly.csv"
GOZDIS_PATH = LOCAL_NORM_DIR / "gozdis_weekly_weather_wide.csv"
OBROD_PATH = LOCAL_NORM_DIR / "obrod_weekly_features_from_yearly.csv"

REMOVED_COPERNICUS_TICK_ACTIVITY_COLUMNS = {
    "tick_activity_window_hours_sum",
    "growing_degree_hours_base_5_c_sum",
    "tick_favorable_days_ge_6h_count",
    "tick_activity_window_hours_sum_lag_1w",
    "tick_activity_window_hours_sum_lag_2w",
    "tick_activity_window_hours_sum_lag_4w",
    "tick_activity_window_hours_sum_rolling_4w_mean",
}


BASE_KEYS = ("week_start", "obcina_sifra")
CLC_KEY = ("obcina_sifra",)

NIJZ_FIELDS = ["lyme_cases", "kme_cases", "tick_borne_cases_total"]
CLC_FIELDS = [
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
ARSO_FIELDS = [
    "source_month_key",
    "arso_air_temperature_mean_c",
    "arso_relative_humidity_mean_pct",
    "arso_precipitation_sum_mm",
]
GOZDIS_FIELDS = [
    "gozdis_precipitation_sum_mm",
    "gozdis_relative_humidity_mean_pct",
    "gozdis_relative_humidity_min_pct",
    "gozdis_relative_humidity_max_pct",
    "gozdis_air_temperature_mean_c",
    "gozdis_air_temperature_min_c",
    "gozdis_air_temperature_max_c",
]


@dataclass(frozen=True)
class SourceMergeConfig:
    name: str
    path: Path
    key_fields: tuple[str, ...]
    select_fields: list[str]
    rename_map: dict[str, str]
    feature_fields: list[str]
    source_type: str
    flag_column: str | None = None

    @property
    def output_fields(self) -> list[str]:
        return [self.rename_map.get(field, field) for field in self.select_fields]

    @property
    def output_feature_fields(self) -> list[str]:
        return [self.rename_map.get(field, field) for field in self.feature_fields]


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def load_lookup(config: SourceMergeConfig) -> tuple[dict[tuple[str, ...], dict[str, str]], int]:
    lookup: dict[tuple[str, ...], dict[str, str]] = {}
    row_count = 0
    with config.path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_count += 1
            key = tuple((row.get(field) or "").strip() for field in config.key_fields)
            selected = {}
            for field in config.select_fields:
                output_field = config.rename_map.get(field, field)
                selected[output_field] = (row.get(field) or "").strip()
            if key in lookup:
                raise ValueError(f"Duplicate key detected in {config.path.name}: {key}")
            lookup[key] = selected
    return lookup, row_count


def determine_obrod_fields() -> tuple[list[str], list[str]]:
    header = read_header(OBROD_PATH)
    select_fields = []
    feature_fields = []
    excluded = {
        "week_start",
        "week_end",
        "iso_year",
        "iso_week",
        "week_mid_date",
        "obcina_sifra",
        "obcina_naziv",
    }
    for field in header:
        if field in excluded:
            continue
        select_fields.append(field)
        if field != "calendar_year":
            feature_fields.append(field)
    return select_fields, feature_fields


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> int:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return len(rows)


def format_pct(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((count / total) * 100.0, 4)


def build_source_configs() -> list[SourceMergeConfig]:
    obrod_select_fields, obrod_feature_fields = determine_obrod_fields()
    return [
        SourceMergeConfig(
            name="nijz_targets",
            path=NIJZ_PATH,
            key_fields=BASE_KEYS,
            select_fields=NIJZ_FIELDS,
            rename_map={},
            feature_fields=NIJZ_FIELDS,
            source_type="weekly",
        ),
        SourceMergeConfig(
            name="copernicus_clc",
            path=CLC_PATH,
            key_fields=CLC_KEY,
            select_fields=CLC_FIELDS,
            rename_map={},
            feature_fields=CLC_FIELDS,
            source_type="static",
            flag_column="has_clc_static",
        ),
        SourceMergeConfig(
            name="arso_local",
            path=ARSO_PATH,
            key_fields=BASE_KEYS,
            select_fields=ARSO_FIELDS,
            rename_map={"source_month_key": "arso_source_month_key"},
            feature_fields=[
                "arso_air_temperature_mean_c",
                "arso_relative_humidity_mean_pct",
                "arso_precipitation_sum_mm",
            ],
            source_type="weekly",
            flag_column="has_arso_local",
        ),
        SourceMergeConfig(
            name="gozdis_local",
            path=GOZDIS_PATH,
            key_fields=BASE_KEYS,
            select_fields=GOZDIS_FIELDS,
            rename_map={},
            feature_fields=GOZDIS_FIELDS,
            source_type="weekly",
            flag_column="has_gozdis_local",
        ),
        SourceMergeConfig(
            name="obrod_local",
            path=OBROD_PATH,
            key_fields=BASE_KEYS,
            select_fields=obrod_select_fields,
            rename_map={"calendar_year": "obrod_source_calendar_year"},
            feature_fields=obrod_feature_fields,
            source_type="weekly",
            flag_column="has_obrod_local",
        ),
    ]


def build_panels_and_stats() -> dict[str, object]:
    ensure_output_dir()
    raw_base_header = read_header(BASE_PATH)
    base_header = [column for column in raw_base_header if column not in REMOVED_COPERNICUS_TICK_ACTIVITY_COLUMNS]
    configs = build_source_configs()
    config_by_name = {config.name: config for config in configs}

    lookups: dict[str, dict[tuple[str, ...], dict[str, str]]] = {}
    lookup_row_counts: dict[str, int] = {}
    for config in configs:
        lookup, row_count = load_lookup(config)
        lookups[config.name] = lookup
        lookup_row_counts[config.name] = row_count

    baseline_fieldnames = base_header + config_by_name["nijz_targets"].output_fields + config_by_name["copernicus_clc"].output_fields + ["has_clc_static"]
    enriched_fieldnames = (
        baseline_fieldnames
        + config_by_name["arso_local"].output_fields
        + [config_by_name["arso_local"].flag_column]
        + config_by_name["gozdis_local"].output_fields
        + [config_by_name["gozdis_local"].flag_column]
        + config_by_name["obrod_local"].output_fields
        + [config_by_name["obrod_local"].flag_column]
        + ["local_sources_present_count"]
    )

    source_feature_columns = {
        "copernicus_weekly_dem_surs": [
            column
            for column in base_header
            if column not in {"week_start", "week_end", "obcina_sifra", "obcina_naziv"}
        ],
        "nijz_targets": config_by_name["nijz_targets"].output_feature_fields,
        "copernicus_clc": config_by_name["copernicus_clc"].output_feature_fields,
        "arso_local": config_by_name["arso_local"].output_feature_fields,
        "gozdis_local": config_by_name["gozdis_local"].output_feature_fields,
        "obrod_local": config_by_name["obrod_local"].output_feature_fields,
    }

    source_types = {
        "copernicus_weekly_dem_surs": "weekly",
        "nijz_targets": "weekly",
        "copernicus_clc": "static",
        "arso_local": "weekly",
        "gozdis_local": "weekly",
        "obrod_local": "weekly_from_yearly",
    }

    source_stats = {
        source: {
            "rows_with_any_data": 0,
            "municipalities": set(),
            "weeks": set(),
            "first_week_with_data": None,
            "last_week_with_data": None,
        }
        for source in source_feature_columns
    }
    source_year_stats: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    column_stats = {
        column: {"source_group": source, "nonmissing_rows": 0}
        for source, columns in source_feature_columns.items()
        for column in columns
    }

    panel_rows = 0
    panel_weeks: set[str] = set()
    panel_municipalities: set[str] = set()
    dropped_base_rows_without_nijz = 0

    baseline_rows: list[dict[str, str]] = []
    enriched_rows: list[dict[str, str]] = []

    with BASE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for base_row in reader:
            key = ((base_row.get("week_start") or "").strip(), (base_row.get("obcina_sifra") or "").strip())
            if not all(key):
                continue

            nijz_lookup = lookups["nijz_targets"].get(key)
            if nijz_lookup is None:
                dropped_base_rows_without_nijz += 1
                continue

            clc_lookup = lookups["copernicus_clc"].get((key[1],), {})
            arso_lookup = lookups["arso_local"].get(key, {})
            gozdis_lookup = lookups["gozdis_local"].get(key, {})
            obrod_lookup = lookups["obrod_local"].get(key, {})

            baseline_row = {field: (base_row.get(field) or "").strip() for field in base_header}
            baseline_row.update(nijz_lookup)
            for field in config_by_name["copernicus_clc"].output_fields:
                baseline_row[field] = clc_lookup.get(field, "")
            baseline_row["has_clc_static"] = "1" if any(clc_lookup.get(field, "") for field in config_by_name["copernicus_clc"].output_feature_fields) else "0"

            enriched_row = dict(baseline_row)
            for field in config_by_name["arso_local"].output_fields:
                enriched_row[field] = arso_lookup.get(field, "")
            for field in config_by_name["gozdis_local"].output_fields:
                enriched_row[field] = gozdis_lookup.get(field, "")
            for field in config_by_name["obrod_local"].output_fields:
                enriched_row[field] = obrod_lookup.get(field, "")

            arso_present = any(arso_lookup.get(field, "") for field in config_by_name["arso_local"].output_feature_fields)
            gozdis_present = any(gozdis_lookup.get(field, "") for field in config_by_name["gozdis_local"].output_feature_fields)
            obrod_present = any(obrod_lookup.get(field, "") for field in config_by_name["obrod_local"].output_feature_fields)
            enriched_row["has_arso_local"] = "1" if arso_present else "0"
            enriched_row["has_gozdis_local"] = "1" if gozdis_present else "0"
            enriched_row["has_obrod_local"] = "1" if obrod_present else "0"
            enriched_row["local_sources_present_count"] = str(int(arso_present) + int(gozdis_present) + int(obrod_present))

            baseline_rows.append(baseline_row)
            enriched_rows.append(enriched_row)

            panel_rows += 1
            panel_weeks.add(key[0])
            panel_municipalities.add(key[1])

            year_value = (baseline_row.get("year") or "").strip()
            week_start = baseline_row["week_start"]
            municipality = baseline_row["obcina_sifra"]

            for source, columns in source_feature_columns.items():
                any_present = False
                row_for_stats = baseline_row if source in {"copernicus_weekly_dem_surs", "nijz_targets", "copernicus_clc"} else enriched_row
                for column in columns:
                    if row_for_stats.get(column, "") != "":
                        column_stats[column]["nonmissing_rows"] += 1
                        any_present = True
                if any_present:
                    source_stats[source]["rows_with_any_data"] += 1
                    source_stats[source]["municipalities"].add(municipality)
                    source_stats[source]["weeks"].add(week_start)
                    current_min = source_stats[source]["first_week_with_data"]
                    current_max = source_stats[source]["last_week_with_data"]
                    source_stats[source]["first_week_with_data"] = week_start if current_min is None or week_start < current_min else current_min
                    source_stats[source]["last_week_with_data"] = week_start if current_max is None or week_start > current_max else current_max
                    year_bucket = source_year_stats[source].setdefault(
                        year_value,
                        {"rows_with_any_data": 0, "municipalities": set()},
                    )
                    year_bucket["rows_with_any_data"] += 1
                    year_bucket["municipalities"].add(municipality)

    baseline_path = OUTPUT_DIR / "master_weekly_panel_baseline_nijz_copernicus.csv"
    enriched_path = OUTPUT_DIR / "master_weekly_panel_enriched_all_sources.csv"
    baseline_count = write_csv(baseline_path, baseline_fieldnames, baseline_rows)
    enriched_count = write_csv(enriched_path, enriched_fieldnames, enriched_rows)

    source_summary_rows = []
    for source in [
        "copernicus_weekly_dem_surs",
        "nijz_targets",
        "copernicus_clc",
        "arso_local",
        "gozdis_local",
        "obrod_local",
    ]:
        stat = source_stats[source]
        source_summary_rows.append(
            {
                "source_group": source,
                "source_type": source_types[source],
                "feature_column_count": len(source_feature_columns[source]),
                "rows_with_any_data": stat["rows_with_any_data"],
                "rows_with_any_data_pct": format_pct(stat["rows_with_any_data"], panel_rows),
                "municipalities_with_any_data": len(stat["municipalities"]),
                "weeks_with_any_data": len(stat["weeks"]),
                "first_week_with_data": stat["first_week_with_data"] or "",
                "last_week_with_data": stat["last_week_with_data"] or "",
            }
        )

    source_summary_path = OUTPUT_DIR / "source_coverage_summary.csv"
    write_csv(
        source_summary_path,
        [
            "source_group",
            "source_type",
            "feature_column_count",
            "rows_with_any_data",
            "rows_with_any_data_pct",
            "municipalities_with_any_data",
            "weeks_with_any_data",
            "first_week_with_data",
            "last_week_with_data",
        ],
        source_summary_rows,
    )

    column_summary_rows = []
    for source in [
        "copernicus_weekly_dem_surs",
        "nijz_targets",
        "copernicus_clc",
        "arso_local",
        "gozdis_local",
        "obrod_local",
    ]:
        for column in source_feature_columns[source]:
            nonmissing = column_stats[column]["nonmissing_rows"]
            column_summary_rows.append(
                {
                    "source_group": source,
                    "column_name": column,
                    "nonmissing_rows": nonmissing,
                    "missing_rows": panel_rows - nonmissing,
                    "nonmissing_rows_pct": format_pct(nonmissing, panel_rows),
                    "missing_rows_pct": format_pct(panel_rows - nonmissing, panel_rows),
                }
            )

    column_summary_path = OUTPUT_DIR / "source_column_missingness.csv"
    write_csv(
        column_summary_path,
        [
            "source_group",
            "column_name",
            "nonmissing_rows",
            "missing_rows",
            "nonmissing_rows_pct",
            "missing_rows_pct",
        ],
        column_summary_rows,
    )

    column_summary_lookup = {
        (row["source_group"], row["column_name"]): row for row in column_summary_rows
    }

    source_year_rows = []
    for source in [
        "copernicus_weekly_dem_surs",
        "nijz_targets",
        "copernicus_clc",
        "arso_local",
        "gozdis_local",
        "obrod_local",
    ]:
        for year_value in sorted(source_year_stats[source]):
            bucket = source_year_stats[source][year_value]
            source_year_rows.append(
                {
                    "source_group": source,
                    "year": year_value,
                    "rows_with_any_data": bucket["rows_with_any_data"],
                    "municipalities_with_any_data": len(bucket["municipalities"]),
                }
            )

    source_year_path = OUTPUT_DIR / "source_year_coverage_summary.csv"
    write_csv(
        source_year_path,
        ["source_group", "year", "rows_with_any_data", "municipalities_with_any_data"],
        source_year_rows,
    )

    run_summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": str(Path(__file__).resolve()),
        "base_input": str(BASE_PATH),
        "output_dir": str(OUTPUT_DIR.resolve()),
        "removed_copernicus_tick_activity_columns": sorted(REMOVED_COPERNICUS_TICK_ACTIVITY_COLUMNS),
        "panel_row_count": panel_rows,
        "panel_municipality_count": len(panel_municipalities),
        "panel_week_count": len(panel_weeks),
        "panel_week_start_min": min(panel_weeks) if panel_weeks else None,
        "panel_week_start_max": max(panel_weeks) if panel_weeks else None,
        "baseline_output_rows": baseline_count,
        "enriched_output_rows": enriched_count,
        "baseline_column_count": len(baseline_fieldnames),
        "enriched_column_count": len(enriched_fieldnames),
        "dropped_base_rows_without_nijz_match": dropped_base_rows_without_nijz,
        "lookup_row_counts": lookup_row_counts,
        "source_groups": source_summary_rows,
        "output_files": [
            baseline_path.name,
            enriched_path.name,
            source_summary_path.name,
            column_summary_path.name,
            source_year_path.name,
            "master_weekly_panel_merge_summary.json",
            "MASTER_WEEKLY_PANEL_REPORT.md",
        ],
        "notes": [
            "The master panel is built from the Copernicus weekly weather/dem/surs table as the base row calendar.",
            "Copernicus tick-activity proxy columns are removed at panel-build time in this environmental branch because they are treated as a separate analytic question rather than part of the core environmental comparison.",
            "NIJZ targets are inner-joined to the Copernicus base on week_start and municipality.",
            "CLC is joined by municipality as a static feature layer.",
            "ARSO is joined as monthly-derived weekly data using the previously normalized file.",
            "GOZDIS is joined as weekly local weather using the previously normalized file.",
            "OBROD is joined as yearly-derived weekly forestry data using the previously normalized file.",
            "This pipeline intentionally avoids the pre-built catboost_ready table so the merge logic remains explicit.",
        ],
    }
    summary_path = OUTPUT_DIR / "master_weekly_panel_merge_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(run_summary, handle, indent=2)

    report_path = OUTPUT_DIR / "MASTER_WEEKLY_PANEL_REPORT.md"
    report_lines = [
        "# Master Weekly Panel Report",
        "",
        "This report describes the merged weekly municipality panel used as the next staging layer for modeling.",
        "",
        "## What Was Built",
        "",
        "- `master_weekly_panel_baseline_nijz_copernicus.csv`",
        "  - weekly `municipality x week` baseline panel",
        "  - includes Copernicus weekly weather/DEM/SURS features except the retired tick-activity proxy block, plus NIJZ targets and static CLC features",
        "- `master_weekly_panel_enriched_all_sources.csv`",
        "  - baseline panel plus normalized ARSO, GOZDIS, and OBROD feature layers",
        "- `source_coverage_summary.csv`",
        "  - source-level row, municipality, and week coverage counts",
        "- `source_column_missingness.csv`",
        "  - per-column non-missing and missing row counts",
        "- `source_year_coverage_summary.csv`",
        "  - yearly overlap summary by source group",
        "",
        "## Base Design",
        "",
        "- Base row calendar: `Copernicus/obcina_weekly_weather_dem_surs_features.csv`",
        "- Base join key: `week_start + obcina_sifra`",
        "- Base join type with NIJZ: inner join",
        "- Local source joins: left joins onto the baseline panel",
        "",
        "Reasoning:",
        "",
        "- Copernicus weekly weather/DEM/SURS already provides a clean national weekly panel for all 212 municipalities.",
        "- The Copernicus tick-activity proxy fields are intentionally removed in this branch so they do not blur the pure environmental-factor comparison.",
        "- NIJZ provides the disease targets on the same municipality-week concept.",
        "- The local sources are useful enrichment layers, but they are much sparser and should not define the national panel structure.",
        "",
        "## Resulting Panel Window",
        "",
        f"- Row count: `{panel_rows}`",
        f"- Baseline column count: `{len(baseline_fieldnames)}`",
        f"- Enriched column count: `{len(enriched_fieldnames)}`",
        f"- Municipalities: `{len(panel_municipalities)}`",
        f"- Weeks: `{len(panel_weeks)}`",
        f"- Week range: `{min(panel_weeks) if panel_weeks else ''}` to `{max(panel_weeks) if panel_weeks else ''}`",
        f"- Dropped base rows without NIJZ match: `{dropped_base_rows_without_nijz}`",
        "",
        "## Source Coverage Summary",
        "",
        "| Source Group | Type | Feature Columns | Rows With Any Data | Row Coverage % | Municipalities | Weeks | First Week | Last Week |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in source_summary_rows:
        report_lines.append(
            f"| {row['source_group']} | {row['source_type']} | {row['feature_column_count']} | {row['rows_with_any_data']} | {row['rows_with_any_data_pct']} | {row['municipalities_with_any_data']} | {row['weeks_with_any_data']} | {row['first_week_with_data']} | {row['last_week_with_data']} |"
        )

    report_lines.extend(
        [
            "",
            "## Missingness Highlights Inside Local Sources",
            "",
            f"- `ARSO` precipitation is present on `{column_summary_lookup[('arso_local', 'arso_precipitation_sum_mm')]['nonmissing_rows_pct']}`% of panel rows, while ARSO temperature and humidity are each present on `{column_summary_lookup[('arso_local', 'arso_air_temperature_mean_c')]['nonmissing_rows_pct']}`% of rows.",
            f"- `GOZDIS` temperature columns are present on `{column_summary_lookup[('gozdis_local', 'gozdis_air_temperature_mean_c')]['nonmissing_rows_pct']}`% of panel rows; GOZDIS precipitation is present on `{column_summary_lookup[('gozdis_local', 'gozdis_precipitation_sum_mm')]['nonmissing_rows_pct']}`% of rows.",
            f"- `OBROD` yearly summary features are present on `{column_summary_lookup[('obrod_local', 'obrod_value_mean')]['nonmissing_rows_pct']}`% of panel rows, but individual species columns are much sparser.",
            f"- The sparsest OBROD species columns are below 1% row coverage, while `obrod_species_unknown` reaches `{column_summary_lookup[('obrod_local', 'obrod_species_unknown')]['nonmissing_rows_pct']}`% of panel rows.",
            "",
            "## Coverage Pattern Over Time",
            "",
            "- `ARSO` contributes throughout most of the national modeling window but stops before the last 2025 weeks.",
            "- `GOZDIS` touches all 508 panel weeks because the 11 covered municipalities remain present across the entire baseline period.",
            "- `OBROD` contributes only through the 2023 calendar year, so the 2024-2025 tail of the panel has no OBROD signal.",
        ]
    )

    report_lines.extend(
        [
            "",
            "## Interpretation Notes",
            "",
            "- `copernicus_weekly_dem_surs`, `nijz_targets`, and `copernicus_clc` act as the national backbone and should be nearly or fully complete across the final panel.",
            "- `arso_local` is monthly data expanded to weekly rows, so it adds national-subset context but not true municipality-week measurements for every municipality.",
            "- `gozdis_local` is true weekly local weather, but only for a very small municipality subset.",
            "- `obrod_local` is yearly forestry data expanded to weeks, so it carries slower annual context rather than week-to-week signal.",
            "",
            "## Behind-The-Scenes Merge Rules",
            "",
            "- NIJZ is matched on `week_start` and `obcina_sifra`.",
            "- CLC is matched on `obcina_sifra` only because it is static.",
            "- ARSO fields come from the normalized weekly file where month values were assigned to NIJZ weeks using `week_mid_date`.",
            "- GOZDIS fields come from the normalized weekly file with ISO week dates converted to `week_start` and `week_end`.",
            "- OBROD fields come from the normalized weekly file where yearly values were assigned to weeks using the calendar year of `week_mid_date`.",
            "",
            "## What This Means For Modeling",
            "",
            "- The baseline panel is ready for national training and validation.",
            "- The enriched panel is ready for ablation testing to see whether local-source layers improve performance enough to justify their sparsity.",
            "- Coverage and missingness should guide which local sources become permanent model features and which are better treated as optional experiments.",
        ]
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "panel_rows": panel_rows,
        "panel_municipalities": len(panel_municipalities),
        "panel_weeks": len(panel_weeks),
        "baseline_path": baseline_path,
        "enriched_path": enriched_path,
        "source_summary_path": source_summary_path,
        "column_summary_path": column_summary_path,
        "source_year_path": source_year_path,
        "summary_path": summary_path,
        "report_path": report_path,
    }


def main() -> None:
    result = build_panels_and_stats()
    print("Master weekly panel outputs written to:")
    print(OUTPUT_DIR)
    print(f"- {result['baseline_path'].name}")
    print(f"- {result['enriched_path'].name}")
    print(f"- {result['source_summary_path'].name}")
    print(f"- {result['column_summary_path'].name}")
    print(f"- {result['source_year_path'].name}")
    print(f"- {result['summary_path'].name}")
    print(f"- {result['report_path'].name}")
    print(f"Panel rows: {result['panel_rows']}")
    print(f"Municipalities: {result['panel_municipalities']}")
    print(f"Weeks: {result['panel_weeks']}")


if __name__ == "__main__":
    main()
