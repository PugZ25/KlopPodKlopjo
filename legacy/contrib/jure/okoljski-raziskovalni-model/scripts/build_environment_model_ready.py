#!/usr/bin/env python3
"""Build the okoljski_raziskovalni_model model-ready panel with reserved validation."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline_utils import format_pct


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_STAGING_DIR = INTERIM_DIR / "model_staging"
OUTPUT_DIR = PROCESSED_DIR / "model_ready"
LIVING_README_PATH = INTERIM_DIR / "Slovenia_local_data_normalized" / "README_LOCAL_DATA_NORMALIZATION.md"

MASTER_PANEL_PATH = MODEL_STAGING_DIR / "master_weekly_panel_enriched_all_sources.csv"
FLAG_REGISTRY_PATH = MODEL_STAGING_DIR / "master_panel_variable_flags.csv"

MODEL_READY_PANEL_PATH = OUTPUT_DIR / "environment_model_ready_panel.csv"
FEATURE_MANIFEST_PATH = OUTPUT_DIR / "environment_feature_manifest.csv"
SPLIT_SUMMARY_PATH = OUTPUT_DIR / "environment_target_split_summary.csv"
REPORT_PATH = OUTPUT_DIR / "ENVIRONMENT_MODEL_READY_REPORT.md"
RUN_SUMMARY_PATH = OUTPUT_DIR / "environment_model_ready_run_summary.json"

FINAL_HOLDOUT_YEAR = 2025
DEVELOPMENT_BACKTEST_YEARS = [2021, 2022, 2023, 2024]
DEVELOPMENT_MIN_BACKTEST_YEAR = min(DEVELOPMENT_BACKTEST_YEARS)

BASE_DATE_COLUMNS = {"week_start", "week_end"}
BASE_TEXT_COLUMNS = {
    "obcina_sifra",
    "obcina_naziv",
    "dominant_clc_code",
    "dominant_clc_label",
    "overlay_method",
    "arso_source_month_key",
}
CURRENT_CASE_COLUMNS = {"lyme_cases", "kme_cases", "tick_borne_cases_total"}
HIDDEN_TIME_CONTROL_USE = "include_hidden_time_control"
HIDDEN_TIME_CONTROL_GROUP = "time_control_hidden"
ANNUAL_CYCLE_DAYS = 365.2425

ARSO_DYNAMIC_COLUMNS = [
    "arso_air_temperature_mean_c",
    "arso_relative_humidity_mean_pct",
    "arso_precipitation_sum_mm",
]
GOZDIS_DYNAMIC_COLUMNS = [
    "gozdis_precipitation_sum_mm",
    "gozdis_relative_humidity_mean_pct",
    "gozdis_relative_humidity_min_pct",
    "gozdis_relative_humidity_max_pct",
    "gozdis_air_temperature_mean_c",
    "gozdis_air_temperature_min_c",
    "gozdis_air_temperature_max_c",
]
LOCAL_DYNAMIC_COLUMN_MAP = {
    "local_arso": ARSO_DYNAMIC_COLUMNS,
    "local_gozdis": GOZDIS_DYNAMIC_COLUMNS,
}
LOCAL_DYNAMIC_COLUMN_TO_GROUP = {
    column: group_name
    for group_name, columns in LOCAL_DYNAMIC_COLUMN_MAP.items()
    for column in columns
}
LOCAL_DYNAMIC_FEATURE_MAP = {
    "arso_air_temperature_mean_c": ("arso", "local_temperature_history", "arso_temperature"),
    "arso_relative_humidity_mean_pct": ("arso", "local_humidity_history", "arso_humidity"),
    "arso_precipitation_sum_mm": ("arso", "local_precipitation_history", "arso_precipitation"),
    "gozdis_air_temperature_mean_c": ("gozdis", "local_temperature_history", "gozdis_temperature"),
    "gozdis_air_temperature_min_c": ("gozdis", "local_temperature_history", "gozdis_temperature"),
    "gozdis_air_temperature_max_c": ("gozdis", "local_temperature_history", "gozdis_temperature"),
    "gozdis_relative_humidity_mean_pct": ("gozdis", "local_humidity_history", "gozdis_humidity"),
    "gozdis_relative_humidity_min_pct": ("gozdis", "local_humidity_history", "gozdis_humidity"),
    "gozdis_relative_humidity_max_pct": ("gozdis", "local_humidity_history", "gozdis_humidity"),
    "gozdis_precipitation_sum_mm": ("gozdis", "local_precipitation_history", "gozdis_precipitation"),
}
ENVIRONMENT_LAG_SUFFIXES = [
    (1, "lag_1w"),
    (2, "lag_2w"),
    (4, "lag_4w"),
]

TARGET_SPECS = [
    {
        "target_name": "tickborne_current4w_per100k",
        "target_column": "target_tick_borne_current_4w_per_100k",
        "split_column": "split_tickborne_current4w_per100k",
        "cases_column": "tick_borne_cases_total",
        "window_weeks": 4,
    },
    {
        "target_name": "lyme_current4w_per100k",
        "target_column": "target_lyme_current_4w_per_100k",
        "split_column": "split_lyme_current4w_per100k",
        "cases_column": "lyme_cases",
        "window_weeks": 4,
    },
    {
        "target_name": "kme_current8w_per100k",
        "target_column": "target_kme_current_8w_per_100k",
        "split_column": "split_kme_current8w_per100k",
        "cases_column": "kme_cases",
        "window_weeks": 8,
    },
]


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_flag_registry() -> pd.DataFrame:
    return pd.read_csv(FLAG_REGISTRY_PATH)


def load_master_panel() -> pd.DataFrame:
    df = pd.read_csv(MASTER_PANEL_PATH, low_memory=False)
    df["week_start"] = pd.to_datetime(df["week_start"], format="%Y-%m-%d")
    df["week_end"] = pd.to_datetime(df["week_end"], format="%Y-%m-%d")

    for column in df.columns:
        if column in BASE_TEXT_COLUMNS or column in BASE_DATE_COLUMNS:
            continue
        df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in BASE_TEXT_COLUMNS:
        if column in df.columns:
            df[column] = df[column].astype("string").fillna("__MISSING__").astype(str)

    df = df.sort_values(["obcina_sifra", "week_start"]).reset_index(drop=True)
    return df


def build_retained_base_columns(flag_df: pd.DataFrame) -> list[str]:
    retained_actions = {
        "group_only",
        "index_only",
        "include_core_predictor",
        "include_local_optional",
    }
    retained = flag_df[flag_df["interpretable_action"].isin(retained_actions)]["column_name"].tolist()
    return [column for column in retained if column not in CURRENT_CASE_COLUMNS]


def add_hidden_time_control_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, str]], list[str]]:
    day_of_year = df["week_start"].dt.dayofyear.astype(float)
    annual_phase = 2.0 * np.pi * (day_of_year - 1.0) / ANNUAL_CYCLE_DAYS

    derived_columns = ["annual_phase_sin", "annual_phase_cos"]
    derived_df = pd.DataFrame(
        {
            "annual_phase_sin": np.sin(annual_phase),
            "annual_phase_cos": np.cos(annual_phase),
        },
        index=df.index,
    )
    df = pd.concat([df, derived_df], axis=1)

    manifest_rows = [
        {
            "column_name": "annual_phase_sin",
            "column_stage": "derived_model_ready",
            "source_group": "pipeline",
            "feature_family": "annual_phase_control",
            "time_alignment": "derived_from_week_start_day_of_year",
            "interpretable_use": HIDDEN_TIME_CONTROL_USE,
            "forecasting_use": HIDDEN_TIME_CONTROL_USE,
            "graph_group": HIDDEN_TIME_CONTROL_GROUP,
            "review_priority": "low",
            "notes": "Hidden seasonal control derived from the municipality-week date so seasonal timing is controlled without ranking raw calendar fields as explanatory factors.",
        },
        {
            "column_name": "annual_phase_cos",
            "column_stage": "derived_model_ready",
            "source_group": "pipeline",
            "feature_family": "annual_phase_control",
            "time_alignment": "derived_from_week_start_day_of_year",
            "interpretable_use": HIDDEN_TIME_CONTROL_USE,
            "forecasting_use": HIDDEN_TIME_CONTROL_USE,
            "graph_group": HIDDEN_TIME_CONTROL_GROUP,
            "review_priority": "low",
            "notes": "Hidden seasonal control derived from the municipality-week date so seasonal timing is controlled without ranking raw calendar fields as explanatory factors.",
        },
    ]
    return df, manifest_rows, derived_columns


def add_local_environment_history_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, str]], list[str]]:
    grouped = df.groupby("obcina_sifra", sort=False)
    derived_frames = []
    manifest_rows = []
    derived_columns: list[str] = []

    for source_group, columns in LOCAL_DYNAMIC_COLUMN_MAP.items():
        for column_name in columns:
            base_series = grouped[column_name]
            derived_map = {}

            for lag_value, suffix in ENVIRONMENT_LAG_SUFFIXES:
                derived_column = f"{column_name}_{suffix}"
                derived_map[derived_column] = base_series.shift(lag_value)

            rolling_column = f"{column_name}_rolling_prev4w_mean"
            derived_map[rolling_column] = base_series.transform(
                lambda series: series.shift(1).rolling(window=4, min_periods=4).mean()
            )

            derived_df = pd.DataFrame(derived_map, index=df.index)
            derived_frames.append(derived_df)
            derived_columns.extend(list(derived_map.keys()))

            source_name, feature_family, graph_group = LOCAL_DYNAMIC_FEATURE_MAP[column_name]
            for derived_column in derived_map:
                manifest_rows.append(
                    {
                        "column_name": derived_column,
                        "column_stage": "derived_model_ready",
                        "source_group": source_name,
                        "feature_family": feature_family,
                        "time_alignment": "lagged_environmental_exposure",
                        "interpretable_use": "include_local_optional",
                        "forecasting_use": "include_local_optional",
                        "graph_group": graph_group,
                        "review_priority": "low",
                        "notes": f"Lagged or rolling environmental history feature derived from earlier {source_name.upper()} weeks only, kept within its factor family rather than merged into a broad local weather block.",
                    }
                )

    if derived_frames:
        df = pd.concat([df] + derived_frames, axis=1)
    return df, manifest_rows, derived_columns


def add_environment_targets(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("obcina_sifra", sort=False)
    population = pd.to_numeric(df["population_total"], errors="coerce")
    derived = {}

    for spec in TARGET_SPECS:
        rolling_cases = grouped[spec["cases_column"]].transform(
            lambda series: series.rolling(window=spec["window_weeks"], min_periods=spec["window_weeks"]).sum()
        )
        derived[spec["target_column"]] = rolling_cases.where(population > 0) / population.where(population > 0) * 100000.0

    derived_df = pd.DataFrame(derived, index=df.index)
    return pd.concat([df, derived_df], axis=1)


def assign_target_split(df: pd.DataFrame, target_column: str) -> pd.Series:
    eligible = df[target_column].notna()
    years = df["week_start"].dt.year
    split = pd.Series("not_eligible", index=df.index, dtype="string")
    split.loc[eligible & (years < DEVELOPMENT_MIN_BACKTEST_YEAR)] = "historical_training_only"
    split.loc[eligible & years.isin(DEVELOPMENT_BACKTEST_YEARS)] = "development_backtest"
    split.loc[eligible & (years == FINAL_HOLDOUT_YEAR)] = "final_holdout"
    return split.astype(str)


def build_feature_manifest(
    flag_df: pd.DataFrame,
    retained_base_columns: list[str],
    derived_manifest_rows: list[dict[str, str]],
) -> pd.DataFrame:
    retained_base = flag_df[flag_df["column_name"].isin(retained_base_columns)].copy()
    retained_base["column_stage"] = "base_master_panel"
    retained_base = retained_base.rename(
        columns={
            "interpretable_action": "interpretable_use",
            "forecasting_action": "forecasting_use",
            "rationale": "notes",
        }
    )[
        [
            "column_name",
            "column_stage",
            "source_group",
            "feature_family",
            "time_alignment",
            "interpretable_use",
            "forecasting_use",
            "graph_group",
            "review_priority",
            "notes",
        ]
    ]

    derived_rows = list(derived_manifest_rows)
    for spec in TARGET_SPECS:
        derived_rows.append(
            {
                "column_name": spec["target_column"],
                "column_stage": "derived_model_ready",
                "source_group": "nijz",
                "feature_family": "environmental_target",
                "time_alignment": f"rolling_current_{spec['window_weeks']}w_window",
                "interpretable_use": "target_only",
                "forecasting_use": "target_only",
                "graph_group": "not_in_graph",
                "review_priority": "low",
                "notes": "Observed disease burden target aligned to the current municipality-week using a full rolling window ending at that week.",
            }
        )
        derived_rows.append(
            {
                "column_name": spec["split_column"],
                "column_stage": "derived_model_ready",
                "source_group": "pipeline",
                "feature_family": "reserved_split_label",
                "time_alignment": "derived_from_current_target_eligibility_and_year",
                "interpretable_use": "split_only",
                "forecasting_use": "split_only",
                "graph_group": "not_in_graph",
                "review_priority": "low",
                "notes": "Frozen split label that reserves the 2025 validation year before any environmental model tuning.",
            }
        )

    derived_df = pd.DataFrame(derived_rows)
    return pd.concat([retained_base, derived_df], ignore_index=True)


def build_split_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for spec in TARGET_SPECS:
        target_column = spec["target_column"]
        split_column = spec["split_column"]
        target_name = spec["target_name"]
        for split_label, subset in df.groupby(split_column, dropna=False):
            if subset.empty:
                continue
            eligible_subset = subset[subset[target_column].notna()]
            positive_rows = (eligible_subset[target_column] > 0).sum() if not eligible_subset.empty else 0
            rows.append(
                {
                    "target_name": target_name,
                    "target_column": target_column,
                    "split_label": split_label,
                    "rows": int(len(subset)),
                    "eligible_rows": int(eligible_subset.shape[0]),
                    "positive_rows": int(positive_rows),
                    "positive_rows_pct": format_pct(int(positive_rows), int(eligible_subset.shape[0])),
                    "municipalities": int(subset["obcina_sifra"].nunique()),
                    "weeks": int(subset["week_start"].nunique()),
                    "min_week_start": subset["week_start"].min().date().isoformat(),
                    "max_week_start": subset["week_start"].max().date().isoformat(),
                }
            )
    return pd.DataFrame(rows).sort_values(["target_name", "split_label"]).reset_index(drop=True)


def write_report(feature_manifest_df: pd.DataFrame, split_summary_df: pd.DataFrame) -> None:
    retained_features = feature_manifest_df[
        feature_manifest_df["interpretable_use"].isin(
            {"include_core_predictor", "include_local_optional", HIDDEN_TIME_CONTROL_USE}
        )
    ]
    family_counts = (
        retained_features.groupby(["source_group", "feature_family"], dropna=False)["column_name"]
        .count()
        .reset_index(name="column_count")
        .sort_values(["source_group", "feature_family"])
    )

    lines = [
        "# Environmental Model-Ready Panel",
        "",
        "This stage creates the okoljski_raziskovalni_model environmental-explanation table.",
        "",
        "## Scientific Purpose",
        "",
        "- model current disease burden aligned to each municipality-week",
        "- allow lagged environmental exposure features because infection and reporting are delayed in time",
        "- keep disease counts as target source only, not as explanatory inputs",
        "- replace redundant raw calendar columns with one hidden annual-phase seasonal control",
        "- reserve the final validation year before any more model tuning",
        "",
        "## Target Definition",
        "",
        "- `tickborne_current4w_per100k` = current rolling 4-week combined tick-borne burden per 100,000 ending at the row week",
        "- `lyme_current4w_per100k` = current rolling 4-week Lyme burden per 100,000 ending at the row week",
        "- `kme_current8w_per100k` = current rolling 8-week KME burden per 100,000 ending at the row week",
        "",
        "Why rolling targets were chosen:",
        "",
        "- same-week single-case counts are noisy, especially for KME",
        "- rolling current burden is still date-aligned but more stable for environmental interpretation",
        "",
        "## Validation Reservation",
        "",
        f"- final holdout year: `{FINAL_HOLDOUT_YEAR}`",
        f"- development backtest years: `{', '.join(str(year) for year in DEVELOPMENT_BACKTEST_YEARS)}`",
        f"- historical training-only years: before `{DEVELOPMENT_MIN_BACKTEST_YEAR}`",
        "",
        "## Split Summary",
        "",
        "| Target | Split | Rows | Eligible Rows | Positive Rows % | Municipalities | Weeks | Min Week | Max Week |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]

    for _, row in split_summary_df.iterrows():
        lines.append(
            f"| {row['target_name']} | {row['split_label']} | {int(row['rows'])} | {int(row['eligible_rows'])} | {row['positive_rows_pct']} | {int(row['municipalities'])} | {int(row['weeks'])} | {row['min_week_start']} | {row['max_week_start']} |"
        )

    lines.extend(
        [
            "",
            "## Retained Predictor Families",
            "",
            "| Source Group | Feature Family | Columns |",
            "| --- | --- | ---: |",
        ]
    )
    for _, row in family_counts.iterrows():
        lines.append(f"| {row['source_group']} | {row['feature_family']} | {int(row['column_count'])} |")

    lines.extend(
        [
            "",
            "## Plain-Language Reading",
            "",
            "- This panel is no longer a future-risk target table. It is a date-aligned environmental explanation table.",
            "- Current disease counts are used only to build the rolling targets, not as predictors.",
            "- Local weather is kept both in current form and in derived lagged-history form so incubation-delay logic can be represented in the model.",
            "- Raw time fields such as month and ISO week are not passed directly into the model. They are replaced by a minimal hidden annual-phase control.",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def update_living_readme(feature_manifest_df: pd.DataFrame, split_summary_df: pd.DataFrame) -> None:
    if not LIVING_README_PATH.exists():
        return

    retained_predictor_count = int(
        feature_manifest_df["interpretable_use"].isin({"include_core_predictor", "include_local_optional", HIDDEN_TIME_CONTROL_USE}).sum()
    )
    local_predictor_count = int(feature_manifest_df["interpretable_use"].eq("include_local_optional").sum())
    hidden_time_control_count = int(feature_manifest_df["interpretable_use"].eq(HIDDEN_TIME_CONTROL_USE).sum())

    sections = [
        "",
        "## Environmental Model-Ready Stage",
        "",
        "okoljski_raziskovalni_model now includes a date-aligned model-ready panel.",
        "",
        "New script:",
        "",
        "- `scripts/build_environment_model_ready.py`",
        "",
        "Key outputs in `data/processed/model_ready/`:",
        "",
        "- `environment_model_ready_panel.csv`",
        "- `environment_feature_manifest.csv`",
        "- `environment_target_split_summary.csv`",
        "- `ENVIRONMENT_MODEL_READY_REPORT.md`",
        "- `environment_model_ready_run_summary.json`",
        "",
        f"- retained environmental predictors: `{retained_predictor_count}`",
        f"- retained optional local predictors and lagged local weather history columns: `{local_predictor_count}`",
        f"- hidden annual-phase control columns: `{hidden_time_control_count}`",
        f"- reserved final holdout year: `{FINAL_HOLDOUT_YEAR}`",
    ]

    for spec in TARGET_SPECS:
        subset = split_summary_df[
            (split_summary_df["target_name"] == spec["target_name"])
            & (split_summary_df["split_label"] == "final_holdout")
        ]
        if subset.empty:
            continue
        row = subset.iloc[0]
        sections.append(f"- `{spec['target_name']}` holdout window: `{row['min_week_start']}` to `{row['max_week_start']}`")

    existing = LIVING_README_PATH.read_text(encoding="utf-8")
    marker = "\n## Environmental Model-Ready Stage\n"
    if marker in existing:
        existing = existing.split(marker)[0].rstrip()
    updated = existing.rstrip() + "\n" + "\n".join(sections) + "\n"
    LIVING_README_PATH.write_text(updated, encoding="utf-8")


def main() -> None:
    ensure_output_dir()

    print("Loading master panel and approved variable flags ...")
    flag_df = load_flag_registry()
    retained_base_columns = build_retained_base_columns(flag_df)

    df = load_master_panel()
    print("Deriving hidden annual-phase control features ...")
    df, hidden_time_manifest_rows, hidden_time_columns = add_hidden_time_control_features(df)
    print("Deriving lagged local environmental history features ...")
    df, derived_manifest_rows, derived_columns = add_local_environment_history_features(df)
    print("Building current rolling disease burden targets ...")
    df = add_environment_targets(df)

    split_df = pd.DataFrame(
        {
            spec["split_column"]: assign_target_split(df, spec["target_column"])
            for spec in TARGET_SPECS
        },
        index=df.index,
    )
    df = pd.concat([df, split_df], axis=1)

    model_ready_columns = retained_base_columns + hidden_time_columns + derived_columns
    target_columns = [spec["target_column"] for spec in TARGET_SPECS]
    split_columns = [spec["split_column"] for spec in TARGET_SPECS]

    model_ready_df = df[model_ready_columns + target_columns + split_columns].copy()
    feature_manifest_df = build_feature_manifest(
        flag_df,
        retained_base_columns,
        hidden_time_manifest_rows + derived_manifest_rows,
    )
    split_summary_df = build_split_summary(model_ready_df)

    model_ready_df.to_csv(MODEL_READY_PANEL_PATH, index=False, encoding="utf-8-sig")
    feature_manifest_df.to_csv(FEATURE_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    split_summary_df.to_csv(SPLIT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    write_report(feature_manifest_df, split_summary_df)
    update_living_readme(feature_manifest_df, split_summary_df)

    run_summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": str(Path(__file__).resolve()),
        "input_master_panel": str(MASTER_PANEL_PATH.resolve()),
        "input_variable_flags": str(FLAG_REGISTRY_PATH.resolve()),
        "output_dir": str(OUTPUT_DIR.resolve()),
        "target_specs": TARGET_SPECS,
        "final_holdout_year": FINAL_HOLDOUT_YEAR,
        "development_backtest_years": DEVELOPMENT_BACKTEST_YEARS,
        "retained_base_columns": retained_base_columns,
        "hidden_time_control_columns": hidden_time_columns,
        "derived_environment_history_columns": derived_columns,
        "output_files": [
            MODEL_READY_PANEL_PATH.name,
            FEATURE_MANIFEST_PATH.name,
            SPLIT_SUMMARY_PATH.name,
            REPORT_PATH.name,
            RUN_SUMMARY_PATH.name,
        ],
    }
    RUN_SUMMARY_PATH.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    print("Environmental model-ready outputs written to:")
    print(MODEL_READY_PANEL_PATH)
    print(FEATURE_MANIFEST_PATH)
    print(SPLIT_SUMMARY_PATH)
    print(REPORT_PATH)
    print(RUN_SUMMARY_PATH)


if __name__ == "__main__":
    main()
