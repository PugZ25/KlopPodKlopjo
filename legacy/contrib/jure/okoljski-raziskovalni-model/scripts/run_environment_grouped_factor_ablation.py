#!/usr/bin/env python3
"""Run grouped environmental/source ablations for okoljski_raziskovalni_model."""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from catboost import CatBoostRegressor, Pool

from pipeline_utils import CATBOOST_PARAMS, mae, rmse, spearman_corr


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_READY_DIR = PROCESSED_DIR / "model_ready"
OUTPUT_DIR = PROCESSED_DIR / "model_grouped_evaluation"
LIVING_README_PATH = INTERIM_DIR / "Slovenia_local_data_normalized" / "README_LOCAL_DATA_NORMALIZATION.md"

MODEL_READY_PANEL_PATH = MODEL_READY_DIR / "environment_model_ready_panel.csv"
FEATURE_MANIFEST_PATH = MODEL_READY_DIR / "environment_feature_manifest.csv"

GROUP_MANIFEST_PATH = OUTPUT_DIR / "environment_group_feature_manifest.csv"
FOLD_RESULTS_PATH = OUTPUT_DIR / "environment_grouped_ablation_fold_results.csv"
VARIANT_SUMMARY_PATH = OUTPUT_DIR / "environment_grouped_ablation_variant_summary.csv"
GROUP_SCORE_PATH = OUTPUT_DIR / "environment_graph_ready_group_scores.csv"
REPORT_PATH = OUTPUT_DIR / "ENVIRONMENT_GROUPED_ABLATION_REPORT.md"
RUN_SUMMARY_PATH = OUTPUT_DIR / "environment_grouped_ablation_run_summary.json"

DEVELOPMENT_BACKTEST_YEARS = [2021, 2022, 2023, 2024]
REFERENCE_VARIANT = "full_environment_core"

TARGET_SPECS = [
    {
        "target_name": "tickborne_current4w_per100k",
        "target_column": "target_tick_borne_current_4w_per_100k",
        "split_column": "split_tickborne_current4w_per100k",
    },
    {
        "target_name": "lyme_current4w_per100k",
        "target_column": "target_lyme_current_4w_per_100k",
        "split_column": "split_lyme_current4w_per100k",
    },
    {
        "target_name": "kme_current8w_per100k",
        "target_column": "target_kme_current_8w_per_100k",
        "split_column": "split_kme_current8w_per100k",
    },
]

PREDICTOR_USES = {
    "include_core_predictor",
    "include_local_optional",
    "include_hidden_time_control",
}
CORE_GROUPS = [
    "copernicus_temperature",
    "copernicus_humidity",
    "copernicus_precipitation",
    "copernicus_soil",
    "topography",
    "land_cover",
    "population",
]
HIDDEN_CONTROL_GROUPS = ["time_control_hidden"]
LOCAL_GROUPS = [
    "arso_temperature",
    "arso_humidity",
    "arso_precipitation",
    "gozdis_temperature",
    "gozdis_humidity",
    "gozdis_precipitation",
    "obrod_summary",
]
CATEGORICAL_COLUMNS = ["dominant_clc_code"]
TEXT_COLUMNS = {
    "week_start",
    "week_end",
    "obcina_sifra",
    "obcina_naziv",
    "dominant_clc_code",
    "split_tickborne_current4w_per100k",
    "split_lyme_current4w_per100k",
    "split_kme_current8w_per100k",
}


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_feature_manifest() -> pd.DataFrame:
    manifest_df = pd.read_csv(FEATURE_MANIFEST_PATH)
    predictor_manifest = manifest_df[manifest_df["interpretable_use"].isin(PREDICTOR_USES)].copy()
    predictor_manifest = predictor_manifest.reset_index(drop=True)
    return predictor_manifest


def load_panel() -> pd.DataFrame:
    df = pd.read_csv(MODEL_READY_PANEL_PATH, low_memory=False)
    df["week_start"] = pd.to_datetime(df["week_start"], format="%Y-%m-%d")
    df["week_end"] = pd.to_datetime(df["week_end"], format="%Y-%m-%d")

    for column in df.columns:
        if column in TEXT_COLUMNS:
            continue
        df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in TEXT_COLUMNS - {"week_start", "week_end"}:
        if column in df.columns:
            df[column] = df[column].astype("string").fillna("__MISSING__").astype(str)

    df = df.sort_values(["obcina_sifra", "week_start"]).reset_index(drop=True).copy()
    df["year"] = df["week_start"].dt.year.astype(int)
    return df


def ordered_unique(columns: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for column in columns:
        if column not in seen:
            ordered.append(column)
            seen.add(column)
    return ordered


def build_group_columns(manifest_df: pd.DataFrame) -> dict[str, list[str]]:
    group_columns: dict[str, list[str]] = {}
    for group_name, subset in manifest_df.groupby("graph_group", sort=False):
        group_columns[group_name] = ordered_unique(subset["column_name"].tolist())

    missing_core = [group for group in CORE_GROUPS if group not in group_columns]
    missing_local = [group for group in LOCAL_GROUPS if group not in group_columns]
    missing_hidden = [group for group in HIDDEN_CONTROL_GROUPS if group not in group_columns]
    if missing_core or missing_local or missing_hidden:
        raise ValueError(
            "Missing expected groups in environmental feature manifest. "
            f"Missing core={missing_core}, missing local={missing_local}, missing hidden={missing_hidden}"
        )
    return group_columns


def build_variants(group_columns: dict[str, list[str]]) -> list[dict[str, object]]:
    hidden_control_columns = ordered_unique(
        [column for group_name in HIDDEN_CONTROL_GROUPS for column in group_columns[group_name]]
    )
    full_core_columns = ordered_unique(
        hidden_control_columns + [column for group_name in CORE_GROUPS for column in group_columns[group_name]]
    )

    variants = [
        {
            "variant": REFERENCE_VARIANT,
            "comparison_type": "reference",
            "group_name": "full_environment_core",
            "group_class": "reference",
            "reference_variant": "",
            "feature_columns": full_core_columns,
            "coverage_columns": full_core_columns,
        }
    ]

    for group_name in LOCAL_GROUPS:
        variants.append(
            {
                "variant": f"{REFERENCE_VARIANT}_plus_{group_name}",
                "comparison_type": "add_local_group",
                "group_name": group_name,
                "group_class": "local_optional",
                "reference_variant": REFERENCE_VARIANT,
                "feature_columns": ordered_unique(full_core_columns + group_columns[group_name]),
                "coverage_columns": group_columns[group_name],
            }
        )

    for group_name in CORE_GROUPS:
        retained_groups = [name for name in CORE_GROUPS if name != group_name]
        retained_columns = ordered_unique(
            hidden_control_columns
            + [column for retained_group in retained_groups for column in group_columns[retained_group]]
        )
        variants.append(
            {
                "variant": f"{REFERENCE_VARIANT}_without_{group_name}",
                "comparison_type": "drop_core_group",
                "group_name": group_name,
                "group_class": "core",
                "reference_variant": REFERENCE_VARIANT,
                "feature_columns": retained_columns,
                "coverage_columns": group_columns[group_name],
            }
        )

    return variants


def coverage_pct(df: pd.DataFrame, columns: list[str]) -> float:
    if df.empty or not columns:
        return 0.0
    coverage = df[columns].notna().any(axis=1).mean() * 100.0
    return round(float(coverage), 4)


def run_fold_evaluations(df: pd.DataFrame, variants: list[dict[str, object]]) -> pd.DataFrame:
    fold_rows: list[dict[str, object]] = []

    for spec in TARGET_SPECS:
        eligible_df = df[
            df[spec["split_column"]].isin(["historical_training_only", "development_backtest"])
            & df[spec["target_column"]].notna()
        ].copy()

        for variant in variants:
            feature_columns = variant["feature_columns"]
            variant_name = variant["variant"]
            print(f"Running {variant_name} for {spec['target_name']} ...")

            for test_year in DEVELOPMENT_BACKTEST_YEARS:
                train_df = eligible_df.loc[eligible_df["year"] < test_year].copy()
                valid_df = eligible_df.loc[eligible_df["year"] == test_year].copy()

                if train_df.empty or valid_df.empty:
                    fold_rows.append(
                        {
                            "target_name": spec["target_name"],
                            "target_column": spec["target_column"],
                            "variant": variant_name,
                            "reference_variant": variant["reference_variant"],
                            "comparison_type": variant["comparison_type"],
                            "group_name": variant["group_name"],
                            "group_class": variant["group_class"],
                            "fold_year": test_year,
                            "train_rows": len(train_df),
                            "valid_rows": len(valid_df),
                            "feature_count": len(feature_columns),
                            "group_validation_coverage_pct": coverage_pct(valid_df, variant["coverage_columns"]),
                            "rmse": math.nan,
                            "mae": math.nan,
                            "spearman": math.nan,
                            "best_iteration": math.nan,
                            "fit_seconds": math.nan,
                        }
                    )
                    continue

                X_train = train_df[feature_columns].copy()
                y_train = train_df[spec["target_column"]].astype(float)
                X_valid = valid_df[feature_columns].copy()
                y_valid = valid_df[spec["target_column"]].astype(float)

                cat_features = [column for column in CATEGORICAL_COLUMNS if column in feature_columns]
                for column in cat_features:
                    X_train[column] = X_train[column].astype("string").fillna("__MISSING__").astype(str)
                    X_valid[column] = X_valid[column].astype("string").fillna("__MISSING__").astype(str)

                train_pool = Pool(X_train, label=y_train, cat_features=cat_features)
                valid_pool = Pool(X_valid, label=y_valid, cat_features=cat_features)

                model = CatBoostRegressor(**CATBOOST_PARAMS)
                start = time.perf_counter()
                model.fit(train_pool, eval_set=valid_pool, use_best_model=True, early_stopping_rounds=40)
                fit_seconds = time.perf_counter() - start

                prediction = model.predict(valid_pool)
                fold_rows.append(
                    {
                        "target_name": spec["target_name"],
                        "target_column": spec["target_column"],
                        "variant": variant_name,
                        "reference_variant": variant["reference_variant"],
                        "comparison_type": variant["comparison_type"],
                        "group_name": variant["group_name"],
                        "group_class": variant["group_class"],
                        "fold_year": test_year,
                        "train_rows": len(train_df),
                        "valid_rows": len(valid_df),
                        "feature_count": len(feature_columns),
                        "group_validation_coverage_pct": coverage_pct(valid_df, variant["coverage_columns"]),
                        "rmse": round(rmse(y_valid.to_numpy(), prediction), 6),
                        "mae": round(mae(y_valid.to_numpy(), prediction), 6),
                        "spearman": round(spearman_corr(y_valid, pd.Series(prediction)), 6),
                        "best_iteration": int(model.get_best_iteration()),
                        "fit_seconds": round(fit_seconds, 3),
                    }
                )

    return pd.DataFrame(fold_rows)


def build_variant_summary(fold_results_df: pd.DataFrame) -> pd.DataFrame:
    summary_df = (
        fold_results_df.groupby(
            ["target_name", "variant", "reference_variant", "comparison_type", "group_name", "group_class"],
            dropna=False,
        )
        .agg(
            folds_completed=("rmse", lambda values: int(pd.notna(values).sum())),
            feature_count=("feature_count", "max"),
            mean_rmse=("rmse", "mean"),
            std_rmse=("rmse", "std"),
            mean_mae=("mae", "mean"),
            mean_spearman=("spearman", "mean"),
            mean_best_iteration=("best_iteration", "mean"),
            mean_fit_seconds=("fit_seconds", "mean"),
            mean_group_validation_coverage_pct=("group_validation_coverage_pct", "mean"),
        )
        .reset_index()
        .sort_values(["target_name", "mean_rmse", "variant"])
        .reset_index(drop=True)
    )
    return summary_df


def build_group_scores(fold_results_df: pd.DataFrame) -> pd.DataFrame:
    reference_df = fold_results_df[fold_results_df["variant"] == REFERENCE_VARIANT].copy()
    reference_df = reference_df.rename(
        columns={
            "rmse": "reference_rmse",
            "mae": "reference_mae",
            "spearman": "reference_spearman",
        }
    )[
        [
            "target_name",
            "fold_year",
            "reference_rmse",
            "reference_mae",
            "reference_spearman",
        ]
    ]

    comparison_df = fold_results_df[fold_results_df["comparison_type"] != "reference"].copy()
    effect_df = comparison_df.merge(reference_df, on=["target_name", "fold_year"], how="left")

    def compute_rmse_effect(row: pd.Series) -> float:
        if pd.isna(row["reference_rmse"]) or pd.isna(row["rmse"]):
            return math.nan
        if row["comparison_type"] == "add_local_group":
            return float(row["reference_rmse"] - row["rmse"])
        return float(row["rmse"] - row["reference_rmse"])

    effect_df["rmse_effect_vs_reference"] = effect_df.apply(compute_rmse_effect, axis=1)
    effect_df["rmse_effect_pct_vs_reference"] = effect_df.apply(
        lambda row: math.nan
        if pd.isna(row["rmse_effect_vs_reference"]) or pd.isna(row["reference_rmse"]) or row["reference_rmse"] == 0
        else float(row["rmse_effect_vs_reference"]) / float(row["reference_rmse"]) * 100.0,
        axis=1,
    )
    effect_df["helpful_fold"] = effect_df["rmse_effect_vs_reference"] > 0

    summary_df = (
        effect_df.groupby(
            ["target_name", "group_name", "group_class", "comparison_type", "variant", "reference_variant"],
            dropna=False,
        )
        .agg(
            folds_completed=("rmse_effect_vs_reference", lambda values: int(pd.notna(values).sum())),
            mean_variant_rmse=("rmse", "mean"),
            mean_reference_rmse=("reference_rmse", "mean"),
            mean_rmse_effect_vs_reference=("rmse_effect_vs_reference", "mean"),
            mean_rmse_effect_pct_vs_reference=("rmse_effect_pct_vs_reference", "mean"),
            helpful_folds=("helpful_fold", lambda values: int(values.fillna(False).sum())),
            mean_group_validation_coverage_pct=("group_validation_coverage_pct", "mean"),
        )
        .reset_index()
    )
    summary_df["helpful_folds_pct"] = summary_df.apply(
        lambda row: round(float(row["helpful_folds"]) / float(row["folds_completed"]) * 100.0, 4)
        if row["folds_completed"] else 0.0,
        axis=1,
    )
    summary_df = summary_df.sort_values(
        ["target_name", "mean_rmse_effect_vs_reference", "helpful_folds_pct"],
        ascending=[True, False, False],
    ).reset_index(drop=True)
    summary_df["target_group_rank"] = summary_df.groupby("target_name").cumcount() + 1
    return summary_df


def write_group_manifest(manifest_df: pd.DataFrame) -> pd.DataFrame:
    group_manifest_df = (
        manifest_df.groupby(["graph_group", "source_group", "feature_family"], dropna=False)["column_name"]
        .agg(column_count="count", columns=lambda values: " | ".join(values))
        .reset_index()
        .rename(columns={"graph_group": "group_name"})
        .sort_values(["group_name", "source_group", "feature_family"])
        .reset_index(drop=True)
    )
    group_manifest_df.to_csv(GROUP_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return group_manifest_df


def write_report(
    group_manifest_df: pd.DataFrame,
    variant_summary_df: pd.DataFrame,
    group_score_df: pd.DataFrame,
) -> None:
    lines = [
        "# Environmental Grouped Ablation",
        "",
        "This report belongs to okoljski_raziskovalni_model.",
        "",
        "## What This Stage Answers",
        "",
        "- which environmental factor families matter most for current rolling combined tick-borne burden, KME burden, and Lyme burden",
        "- which local data sources add useful explanatory signal beyond the national backbone",
        "- how strong, stable, and widely-covered each source is in development backtesting",
        "",
        "## Evaluation Design",
        "",
        f"- reference model: `{REFERENCE_VARIANT}`",
        "- development folds only: `2021`, `2022`, `2023`, `2024`",
        "- no past disease-count predictors are included in this branch",
        "- the reference model includes a hidden annual-phase seasonal control in every variant",
        "- local tests compare the environmental backbone against one local factor family at a time",
        "",
        "## Group Definitions",
        "",
        "| Group | Source Group | Feature Family | Columns |",
        "| --- | --- | --- | ---: |",
    ]

    for _, row in group_manifest_df.iterrows():
        lines.append(
            f"| {row['group_name']} | {row['source_group']} | {row['feature_family']} | {int(row['column_count'])} |"
        )

    lines.extend(
        [
            "",
            "## Mean Development Metrics By Variant",
            "",
            "| Target | Variant | Comparison | Group | Features | Mean RMSE | Mean Group Coverage % |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for _, row in variant_summary_df.iterrows():
        lines.append(
            f"| {row['target_name']} | {row['variant']} | {row['comparison_type']} | {row['group_name']} | {int(row['feature_count'])} | {round(float(row['mean_rmse']), 6)} | {round(float(row['mean_group_validation_coverage_pct']), 4)} |"
        )

    lines.extend(
        [
            "",
            "## Graph-Ready Group Scores",
            "",
            "| Target | Rank | Group | Class | Mean RMSE Effect | Helpful Folds % | Mean Coverage % |",
            "| --- | ---: | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for _, row in group_score_df.iterrows():
        lines.append(
            f"| {row['target_name']} | {int(row['target_group_rank'])} | {row['group_name']} | {row['group_class']} | {round(float(row['mean_rmse_effect_vs_reference']), 6)} | {round(float(row['helpful_folds_pct']), 4)} | {round(float(row['mean_group_validation_coverage_pct']), 4)} |"
        )

    lines.extend(
        [
            "",
            "## Reading The Score",
            "",
            "- positive values are good",
            "- for local groups, positive means adding the source helped",
            "- for core groups, positive means removing the factor family hurt performance, so the group was useful",
            "- the hidden annual-phase control is part of the reference design but is not itself scored as a main factor",
            "- coverage and helpful-fold rate should be interpreted alongside mean effect size",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def update_living_readme(group_score_df: pd.DataFrame) -> None:
    if not LIVING_README_PATH.exists():
        return

    sections = [
        "",
        "## Environmental Grouped Evaluation Stage",
        "",
        "okoljski_raziskovalni_model now includes grouped factor ablations without disease-history predictors and without the older mixed weather/local blocks.",
        "",
        "New script:",
        "",
        "- `scripts/run_environment_grouped_factor_ablation.py`",
        "",
        "Key outputs in `data/processed/model_grouped_evaluation/`:",
        "",
        "- `environment_group_feature_manifest.csv`",
        "- `environment_grouped_ablation_fold_results.csv`",
        "- `environment_grouped_ablation_variant_summary.csv`",
        "- `environment_graph_ready_group_scores.csv`",
        "- `ENVIRONMENT_GROUPED_ABLATION_REPORT.md`",
        "- `environment_grouped_ablation_run_summary.json`",
    ]

    for target_name in group_score_df["target_name"].drop_duplicates():
        best_row = group_score_df[group_score_df["target_name"] == target_name].iloc[0]
        sections.extend(
            [
                "",
                f"- Top current environmental grouped result for `{target_name}`: `{best_row['group_name']}`",
                f"  - mean RMSE effect vs `{REFERENCE_VARIANT}`: `{round(float(best_row['mean_rmse_effect_vs_reference']), 6)}`",
                f"  - helpful folds: `{int(best_row['helpful_folds'])}` / `{int(best_row['folds_completed'])}`",
                f"  - mean group coverage: `{round(float(best_row['mean_group_validation_coverage_pct']), 4)}`%",
            ]
        )

    existing = LIVING_README_PATH.read_text(encoding="utf-8")
    marker = "\n## Environmental Grouped Evaluation Stage\n"
    if marker in existing:
        existing = existing.split(marker)[0].rstrip()
    updated = existing.rstrip() + "\n" + "\n".join(sections) + "\n"
    LIVING_README_PATH.write_text(updated, encoding="utf-8")


def main() -> None:
    ensure_output_dir()

    print("Loading environmental model-ready panel and feature manifest ...")
    manifest_df = load_feature_manifest()
    group_manifest_df = write_group_manifest(manifest_df)
    group_columns = build_group_columns(manifest_df)
    variants = build_variants(group_columns)

    df = load_panel()

    print("Running grouped environmental CatBoost ablations on development folds ...")
    fold_results_df = run_fold_evaluations(df, variants)
    variant_summary_df = build_variant_summary(fold_results_df)
    group_score_df = build_group_scores(fold_results_df)

    fold_results_df.to_csv(FOLD_RESULTS_PATH, index=False, encoding="utf-8-sig")
    variant_summary_df.to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    group_score_df.to_csv(GROUP_SCORE_PATH, index=False, encoding="utf-8-sig")
    write_report(group_manifest_df, variant_summary_df, group_score_df)
    update_living_readme(group_score_df)

    run_summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": str(Path(__file__).resolve()),
        "input_panel": str(MODEL_READY_PANEL_PATH.resolve()),
        "input_feature_manifest": str(FEATURE_MANIFEST_PATH.resolve()),
        "output_dir": str(OUTPUT_DIR.resolve()),
        "development_backtest_years": DEVELOPMENT_BACKTEST_YEARS,
        "reference_variant": REFERENCE_VARIANT,
        "core_groups": CORE_GROUPS,
        "local_groups": LOCAL_GROUPS,
        "variant_count": len(variants),
        "target_specs": TARGET_SPECS,
        "output_files": [
            GROUP_MANIFEST_PATH.name,
            FOLD_RESULTS_PATH.name,
            VARIANT_SUMMARY_PATH.name,
            GROUP_SCORE_PATH.name,
            REPORT_PATH.name,
            RUN_SUMMARY_PATH.name,
        ],
    }
    RUN_SUMMARY_PATH.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    print("Environmental grouped evaluation outputs written to:")
    print(GROUP_MANIFEST_PATH)
    print(FOLD_RESULTS_PATH)
    print(VARIANT_SUMMARY_PATH)
    print(GROUP_SCORE_PATH)
    print(REPORT_PATH)
    print(RUN_SUMMARY_PATH)


if __name__ == "__main__":
    main()
