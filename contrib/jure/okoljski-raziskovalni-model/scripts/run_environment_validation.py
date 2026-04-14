#!/usr/bin/env python3
"""Validate okoljski_raziskovalni_model on development stability and final holdout."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
from catboost import CatBoostRegressor, Pool

from pipeline_utils import CATBOOST_PARAMS, mae, rmse, spearman_corr
from run_environment_grouped_factor_ablation import (
    CATEGORICAL_COLUMNS,
    REFERENCE_VARIANT,
    TARGET_SPECS,
    build_group_columns,
    build_variants,
    coverage_pct,
    load_feature_manifest,
    load_panel,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
GROUPED_EVAL_DIR = PROCESSED_DIR / "model_grouped_evaluation"
OUTPUT_DIR = PROCESSED_DIR / "model_validation"

FOLD_RESULTS_PATH = GROUPED_EVAL_DIR / "environment_grouped_ablation_fold_results.csv"
VARIANT_SUMMARY_PATH = GROUPED_EVAL_DIR / "environment_grouped_ablation_variant_summary.csv"
GROUP_SCORE_PATH = GROUPED_EVAL_DIR / "environment_graph_ready_group_scores.csv"

DEVELOPMENT_VALIDATION_PATH = OUTPUT_DIR / "environment_development_validation_summary.csv"
HOLDOUT_VARIANT_RESULTS_PATH = OUTPUT_DIR / "environment_holdout_variant_results.csv"
HOLDOUT_GROUP_SCORE_PATH = OUTPUT_DIR / "environment_holdout_group_scores.csv"
SIGNAL_SUMMARY_PATH = OUTPUT_DIR / "environment_validation_signal_summary.csv"
REPORT_PATH = OUTPUT_DIR / "ENVIRONMENT_VALIDATION_REPORT.md"
RUN_SUMMARY_PATH = OUTPUT_DIR / "environment_validation_run_summary.json"

TRAIN_SPLIT_LABELS = {"historical_training_only", "development_backtest"}
FINAL_HOLDOUT_LABEL = "final_holdout"


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_existing_results() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fold_results_df = pd.read_csv(FOLD_RESULTS_PATH)
    variant_summary_df = pd.read_csv(VARIANT_SUMMARY_PATH)
    group_score_df = pd.read_csv(GROUP_SCORE_PATH)
    return fold_results_df, variant_summary_df, group_score_df


def classify_coverage_evidence(coverage_pct_value: float, group_class: str) -> str:
    if group_class == "core" and coverage_pct_value >= 95.0:
        return "national_coverage"
    if coverage_pct_value < 10.0:
        return "exploratory_low_coverage"
    if coverage_pct_value < 25.0:
        return "partial_local_coverage"
    if coverage_pct_value < 95.0:
        return "moderate_subnational_coverage"
    return "broad_coverage"


def classify_development_signal(row: pd.Series) -> str:
    if row["group_class"] == "core":
        if row["mean_rmse_effect_vs_reference"] > 0 and row["helpful_folds_pct"] >= 75.0:
            return "stable_core_signal"
        if row["mean_rmse_effect_vs_reference"] > 0:
            return "mixed_core_signal"
        return "not_stably_useful"

    if row["mean_rmse_effect_vs_reference"] > 0 and row["helpful_folds_pct"] >= 75.0:
        if row["coverage_evidence_label"] == "exploratory_low_coverage":
            return "exploratory_positive_local_signal"
        return "promising_local_signal"
    if row["mean_rmse_effect_vs_reference"] > 0:
        return "weak_or_mixed_local_signal"
    return "no_stable_added_value"


def build_effect_rows(fold_results_df: pd.DataFrame) -> pd.DataFrame:
    reference_df = fold_results_df[fold_results_df["variant"] == REFERENCE_VARIANT].copy()
    reference_df = reference_df.rename(columns={"rmse": "reference_rmse"})[
        ["target_name", "fold_year", "reference_rmse"]
    ]

    effect_df = fold_results_df[fold_results_df["comparison_type"] != "reference"].copy()
    effect_df = effect_df.merge(reference_df, on=["target_name", "fold_year"], how="left")
    effect_df["rmse_effect_vs_reference"] = effect_df.apply(
        lambda row: math.nan
        if pd.isna(row["rmse"]) or pd.isna(row["reference_rmse"])
        else (
            float(row["reference_rmse"] - row["rmse"])
            if row["comparison_type"] == "add_local_group"
            else float(row["rmse"] - row["reference_rmse"])
        ),
        axis=1,
    )
    effect_df["helpful_fold"] = effect_df["rmse_effect_vs_reference"] > 0
    return effect_df


def build_development_validation_summary(fold_results_df: pd.DataFrame) -> pd.DataFrame:
    effect_df = build_effect_rows(fold_results_df)
    summary_df = (
        effect_df.groupby(
            ["target_name", "variant", "reference_variant", "comparison_type", "group_name", "group_class"],
            dropna=False,
        )
        .agg(
            folds_completed=("rmse_effect_vs_reference", lambda values: int(pd.notna(values).sum())),
            mean_rmse_effect_vs_reference=("rmse_effect_vs_reference", "mean"),
            std_rmse_effect_vs_reference=("rmse_effect_vs_reference", "std"),
            min_rmse_effect_vs_reference=("rmse_effect_vs_reference", "min"),
            max_rmse_effect_vs_reference=("rmse_effect_vs_reference", "max"),
            helpful_folds=("helpful_fold", lambda values: int(values.fillna(False).sum())),
            mean_group_validation_coverage_pct=("group_validation_coverage_pct", "mean"),
            mean_variant_rmse=("rmse", "mean"),
            mean_reference_rmse=("reference_rmse", "mean"),
        )
        .reset_index()
    )
    summary_df["helpful_folds_pct"] = summary_df.apply(
        lambda row: round(float(row["helpful_folds"]) / float(row["folds_completed"]) * 100.0, 4)
        if row["folds_completed"] else 0.0,
        axis=1,
    )
    summary_df["coverage_evidence_label"] = summary_df.apply(
        lambda row: classify_coverage_evidence(float(row["mean_group_validation_coverage_pct"]), str(row["group_class"])),
        axis=1,
    )
    summary_df["development_signal_label"] = summary_df.apply(classify_development_signal, axis=1)
    summary_df = summary_df.sort_values(
        ["target_name", "mean_rmse_effect_vs_reference", "helpful_folds_pct"],
        ascending=[True, False, False],
    ).reset_index(drop=True)
    return summary_df


def build_holdout_iteration_lookup(variant_summary_df: pd.DataFrame) -> dict[tuple[str, str], int]:
    iteration_lookup: dict[tuple[str, str], int] = {}
    for _, row in variant_summary_df.iterrows():
        mean_best_iteration = row.get("mean_best_iteration")
        if pd.isna(mean_best_iteration):
            frozen_iterations = int(CATBOOST_PARAMS["iterations"])
        else:
            frozen_iterations = max(25, int(round(float(mean_best_iteration))))
        iteration_lookup[(str(row["target_name"]), str(row["variant"]))] = frozen_iterations
    return iteration_lookup


def run_holdout_validation(
    df: pd.DataFrame,
    variants: list[dict[str, object]],
    iteration_lookup: dict[tuple[str, str], int],
) -> pd.DataFrame:
    holdout_rows: list[dict[str, object]] = []

    for spec in TARGET_SPECS:
        train_df = df[
            df[spec["split_column"]].isin(TRAIN_SPLIT_LABELS)
            & df[spec["target_column"]].notna()
        ].copy()
        holdout_df = df[
            (df[spec["split_column"]] == FINAL_HOLDOUT_LABEL)
            & df[spec["target_column"]].notna()
        ].copy()

        for variant in variants:
            feature_columns = list(variant["feature_columns"])
            variant_name = str(variant["variant"])

            if train_df.empty or holdout_df.empty:
                holdout_rows.append(
                    {
                        "target_name": spec["target_name"],
                        "target_column": spec["target_column"],
                        "variant": variant_name,
                        "reference_variant": variant["reference_variant"],
                        "comparison_type": variant["comparison_type"],
                        "group_name": variant["group_name"],
                        "group_class": variant["group_class"],
                        "train_rows": len(train_df),
                        "holdout_rows": len(holdout_df),
                        "feature_count": len(feature_columns),
                        "group_holdout_coverage_pct": coverage_pct(holdout_df, variant["coverage_columns"]),
                        "frozen_iterations": iteration_lookup.get(
                            (spec["target_name"], variant_name),
                            int(CATBOOST_PARAMS["iterations"]),
                        ),
                        "rmse": math.nan,
                        "mae": math.nan,
                        "spearman": math.nan,
                    }
                )
                continue

            X_train = train_df[feature_columns].copy()
            y_train = train_df[spec["target_column"]].astype(float)
            X_holdout = holdout_df[feature_columns].copy()
            y_holdout = holdout_df[spec["target_column"]].astype(float)

            cat_features = [column for column in CATEGORICAL_COLUMNS if column in feature_columns]
            for column in cat_features:
                X_train[column] = X_train[column].astype("string").fillna("__MISSING__").astype(str)
                X_holdout[column] = X_holdout[column].astype("string").fillna("__MISSING__").astype(str)

            frozen_iterations = iteration_lookup.get(
                (spec["target_name"], variant_name),
                int(CATBOOST_PARAMS["iterations"]),
            )
            model_params = dict(CATBOOST_PARAMS)
            model_params["iterations"] = frozen_iterations
            model = CatBoostRegressor(**model_params)

            train_pool = Pool(X_train, label=y_train, cat_features=cat_features)
            holdout_pool = Pool(X_holdout, label=y_holdout, cat_features=cat_features)
            model.fit(train_pool)
            prediction = model.predict(holdout_pool)

            holdout_rows.append(
                {
                    "target_name": spec["target_name"],
                    "target_column": spec["target_column"],
                    "variant": variant_name,
                    "reference_variant": variant["reference_variant"],
                    "comparison_type": variant["comparison_type"],
                    "group_name": variant["group_name"],
                    "group_class": variant["group_class"],
                    "train_rows": len(train_df),
                    "holdout_rows": len(holdout_df),
                    "feature_count": len(feature_columns),
                    "group_holdout_coverage_pct": coverage_pct(holdout_df, variant["coverage_columns"]),
                    "frozen_iterations": frozen_iterations,
                    "rmse": round(rmse(y_holdout.to_numpy(), prediction), 6),
                    "mae": round(mae(y_holdout.to_numpy(), prediction), 6),
                    "spearman": round(spearman_corr(y_holdout, pd.Series(prediction)), 6),
                }
            )

    return pd.DataFrame(holdout_rows)


def build_holdout_group_scores(holdout_variant_df: pd.DataFrame) -> pd.DataFrame:
    reference_df = holdout_variant_df[holdout_variant_df["variant"] == REFERENCE_VARIANT].copy()
    reference_df = reference_df.rename(columns={"rmse": "reference_rmse"})[
        ["target_name", "reference_rmse"]
    ]

    comparison_df = holdout_variant_df[holdout_variant_df["comparison_type"] != "reference"].copy()
    score_df = comparison_df.merge(reference_df, on=["target_name"], how="left")
    score_df["holdout_rmse_effect_vs_reference"] = score_df.apply(
        lambda row: math.nan
        if pd.isna(row["rmse"]) or pd.isna(row["reference_rmse"])
        else (
            float(row["reference_rmse"] - row["rmse"])
            if row["comparison_type"] == "add_local_group"
            else float(row["rmse"] - row["reference_rmse"])
        ),
        axis=1,
    )
    score_df["holdout_effect_direction"] = score_df["holdout_rmse_effect_vs_reference"].apply(
        lambda value: "positive" if pd.notna(value) and value > 0 else "non_positive"
    )
    score_df["coverage_evidence_label"] = score_df.apply(
        lambda row: classify_coverage_evidence(float(row["group_holdout_coverage_pct"]), str(row["group_class"])),
        axis=1,
    )
    score_df = score_df.sort_values(
        ["target_name", "holdout_rmse_effect_vs_reference"],
        ascending=[True, False],
    ).reset_index(drop=True)
    score_df["holdout_rank"] = score_df.groupby("target_name").cumcount() + 1
    return score_df


def classify_confirmation(row: pd.Series) -> str:
    dev_positive = float(row["mean_rmse_effect_vs_reference"]) > 0
    holdout_positive = float(row["holdout_rmse_effect_vs_reference"]) > 0

    if dev_positive and holdout_positive:
        return "confirmed_on_holdout"
    if dev_positive and not holdout_positive:
        return "did_not_confirm_on_holdout"
    if (not dev_positive) and holdout_positive:
        return "holdout_positive_but_not_dev_stable"
    return "consistently_not_helpful"


def build_signal_summary(
    development_summary_df: pd.DataFrame,
    holdout_group_score_df: pd.DataFrame,
) -> pd.DataFrame:
    merged_df = development_summary_df.merge(
        holdout_group_score_df[
            [
                "target_name",
                "variant",
                "group_name",
                "holdout_rank",
                "reference_rmse",
                "rmse",
                "holdout_rmse_effect_vs_reference",
                "group_holdout_coverage_pct",
                "coverage_evidence_label",
            ]
        ],
        on=["target_name", "variant", "group_name"],
        how="left",
        suffixes=("_development", "_holdout"),
    )
    merged_df = merged_df.rename(
        columns={
            "reference_rmse": "holdout_reference_rmse",
            "rmse": "holdout_variant_rmse",
            "coverage_evidence_label_holdout": "holdout_coverage_evidence_label",
            "coverage_evidence_label_development": "development_coverage_evidence_label",
        }
    )
    if "holdout_coverage_evidence_label" not in merged_df.columns:
        merged_df["holdout_coverage_evidence_label"] = ""
    if "development_coverage_evidence_label" not in merged_df.columns:
        merged_df["development_coverage_evidence_label"] = ""

    merged_df["effect_sign_match"] = merged_df.apply(
        lambda row: (
            pd.notna(row["holdout_rmse_effect_vs_reference"])
            and ((float(row["mean_rmse_effect_vs_reference"]) > 0) == (float(row["holdout_rmse_effect_vs_reference"]) > 0))
        ),
        axis=1,
    )
    merged_df["holdout_confirmation_label"] = merged_df.apply(classify_confirmation, axis=1)
    merged_df["effect_shift_holdout_minus_development"] = (
        merged_df["holdout_rmse_effect_vs_reference"] - merged_df["mean_rmse_effect_vs_reference"]
    )
    merged_df = merged_df.sort_values(
        ["target_name", "mean_rmse_effect_vs_reference"],
        ascending=[True, False],
    ).reset_index(drop=True)
    return merged_df


def write_report(
    development_summary_df: pd.DataFrame,
    holdout_variant_df: pd.DataFrame,
    holdout_group_score_df: pd.DataFrame,
    signal_summary_df: pd.DataFrame,
) -> None:
    lines = [
        "# Environmental Validation Report",
        "",
        "This report validates okoljski_raziskovalni_model in two layers:",
        "",
        "1. development stability across the existing `2021-2024` grouped backtests",
        "2. final holdout performance on the reserved `2025` data",
        "",
        "Important design note:",
        "",
        "- the holdout evaluation freezes model complexity from the development stage using each variant's mean development `best_iteration`",
        "- the `2025` holdout is therefore not used for early stopping or tuning",
        "",
        "## Step 1: Development Stability",
        "",
        "| Target | Group | Class | Mean RMSE Effect | Helpful Folds % | Coverage % | Coverage Evidence | Development Label |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]

    for _, row in development_summary_df.iterrows():
        lines.append(
            f"| {row['target_name']} | {row['group_name']} | {row['group_class']} | {round(float(row['mean_rmse_effect_vs_reference']), 6)} | {round(float(row['helpful_folds_pct']), 4)} | {round(float(row['mean_group_validation_coverage_pct']), 4)} | {row['coverage_evidence_label']} | {row['development_signal_label']} |"
        )

    lines.extend(
        [
            "",
            "## Step 2: Final Holdout Metrics",
            "",
            "| Target | Variant | Comparison | Group | Frozen Iterations | Holdout RMSE | Holdout MAE | Holdout Spearman | Coverage % |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for _, row in holdout_variant_df.iterrows():
        lines.append(
            f"| {row['target_name']} | {row['variant']} | {row['comparison_type']} | {row['group_name']} | {int(row['frozen_iterations'])} | {round(float(row['rmse']), 6)} | {round(float(row['mae']), 6)} | {round(float(row['spearman']), 6)} | {round(float(row['group_holdout_coverage_pct']), 4)} |"
        )

    lines.extend(
        [
            "",
            "## Development To Holdout Confirmation",
            "",
            "| Target | Group | Development Effect | Holdout Effect | Sign Match | Confirmation | Holdout Coverage Evidence |",
            "| --- | --- | ---: | ---: | --- | --- | --- |",
        ]
    )

    for _, row in signal_summary_df.iterrows():
        lines.append(
            f"| {row['target_name']} | {row['group_name']} | {round(float(row['mean_rmse_effect_vs_reference']), 6)} | {round(float(row['holdout_rmse_effect_vs_reference']), 6)} | {str(bool(row['effect_sign_match']))} | {row['holdout_confirmation_label']} | {row.get('holdout_coverage_evidence_label', '')} |"
        )

    lines.extend(
        [
            "",
            "## How To Read This Report",
            "",
            "- the grouped ablation already compares multiple model variants with and without specific factor families",
            "- this validation stage does not replace that logic; it checks whether those variant comparisons are stable and whether they survive the reserved holdout year",
            "- positive effect for a core group means removing it hurt performance",
            "- positive effect for a local group means adding it helped",
            "- local-source claims should always be read together with their coverage-evidence label",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_output_dir()

    print("Loading existing grouped-evaluation outputs ...")
    fold_results_df, variant_summary_df, _ = load_existing_results()
    development_summary_df = build_development_validation_summary(fold_results_df)

    print("Preparing final holdout validation design ...")
    manifest_df = load_feature_manifest()
    group_columns = build_group_columns(manifest_df)
    variants = build_variants(group_columns)
    df = load_panel()
    iteration_lookup = build_holdout_iteration_lookup(variant_summary_df)

    print("Running frozen-configuration holdout evaluation on 2025 ...")
    holdout_variant_df = run_holdout_validation(df, variants, iteration_lookup)
    holdout_group_score_df = build_holdout_group_scores(holdout_variant_df)
    signal_summary_df = build_signal_summary(development_summary_df, holdout_group_score_df)

    development_summary_df.to_csv(DEVELOPMENT_VALIDATION_PATH, index=False, encoding="utf-8-sig")
    holdout_variant_df.to_csv(HOLDOUT_VARIANT_RESULTS_PATH, index=False, encoding="utf-8-sig")
    holdout_group_score_df.to_csv(HOLDOUT_GROUP_SCORE_PATH, index=False, encoding="utf-8-sig")
    signal_summary_df.to_csv(SIGNAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    write_report(development_summary_df, holdout_variant_df, holdout_group_score_df, signal_summary_df)

    run_summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": str(Path(__file__).resolve()),
        "input_files": [
            str(FOLD_RESULTS_PATH.resolve()),
            str(VARIANT_SUMMARY_PATH.resolve()),
            str(GROUP_SCORE_PATH.resolve()),
        ],
        "frozen_reference_variant": REFERENCE_VARIANT,
        "target_specs": TARGET_SPECS,
        "train_split_labels": sorted(TRAIN_SPLIT_LABELS),
        "holdout_split_label": FINAL_HOLDOUT_LABEL,
        "variant_count": len(variants),
        "output_files": [
            DEVELOPMENT_VALIDATION_PATH.name,
            HOLDOUT_VARIANT_RESULTS_PATH.name,
            HOLDOUT_GROUP_SCORE_PATH.name,
            SIGNAL_SUMMARY_PATH.name,
            REPORT_PATH.name,
            RUN_SUMMARY_PATH.name,
        ],
    }
    RUN_SUMMARY_PATH.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    print("Environmental validation outputs written to:")
    print(DEVELOPMENT_VALIDATION_PATH)
    print(HOLDOUT_VARIANT_RESULTS_PATH)
    print(HOLDOUT_GROUP_SCORE_PATH)
    print(SIGNAL_SUMMARY_PATH)
    print(REPORT_PATH)
    print(RUN_SUMMARY_PATH)


if __name__ == "__main__":
    main()
