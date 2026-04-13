from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = Path(tempfile.gettempdir()) / "kloppodklopjo-report-cache"
CACHE_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_ROOT / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_ROOT))

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from catboost import CatBoostClassifier, Pool
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_curve,
    r2_score,
    roc_auc_score,
    roc_curve,
)

DATASET_PATH = ROOT / "data/processed/training/obcina_weekly_tick_borne_catboost_ready.csv"
REPORT_HTML_PATH = ROOT / "docs/presentation/hackathon-research-report.html"
ASSETS_DIR = ROOT / "docs/presentation/hackathon-research-report-assets"

COLORS = {
    "train": "#1f6f8b",
    "validation": "#d97706",
    "test": "#c2410c",
    "accent": "#8b2c2a",
    "accent_soft": "#d28b79",
    "ink": "#1f2937",
    "muted": "#6b7280",
    "paper": "#f6f2ea",
    "panel": "#fffdf8",
    "grid": "#e7dfd1",
    "success": "#2f7f63",
}

PLOT_DPI = 180
SEED = 42


@dataclass(frozen=True)
class ModelBundle:
    slug: str
    label: str
    artifact_dir: Path
    metadata: dict
    predictions: pd.DataFrame
    target_column: str
    prediction_column: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a presentation-ready HTML research report with exported charts "
            "for the KlopPodKlopjo hackathon models."
        )
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=1200,
        help="Maximum number of test rows used for SHAP plots per model.",
    )
    parser.add_argument(
        "--html-path",
        type=Path,
        default=REPORT_HTML_PATH,
        help="Output HTML file.",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=ASSETS_DIR,
        help="Directory where chart assets will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.html_path.parent.mkdir(parents=True, exist_ok=True)
    args.assets_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(build_matplotlib_theme())

    lyme_v1 = load_bundle(
        slug="lyme_v1",
        label="Borelioza baseline v1",
        artifact_dir=ROOT / "data/processed/training/catboost_tick_borne_lyme_v1",
        target_column="target_lyme_cases",
        prediction_column="prediction",
    )
    lyme_env_v2 = load_bundle(
        slug="lyme_env_v2",
        label="Borelioza env v2",
        artifact_dir=ROOT / "data/processed/training/catboost_tick_borne_lyme_env_v2",
        target_column="target_lyme_presence_next_4w",
        prediction_column="prediction_probability",
    )
    kme_v2 = load_bundle(
        slug="kme_v2",
        label="KME ranking v2",
        artifact_dir=ROOT / "data/processed/training/catboost_tick_borne_kme_presence_v2",
        target_column="target_kme_presence",
        prediction_column="prediction_probability",
    )

    figure_map = {
        "split_timeline": plot_split_timeline(
            [lyme_v1, lyme_env_v2, kme_v2],
            args.assets_dir / "split-timeline.svg",
        ),
        "lyme_weekly_traces": plot_lyme_weekly_traces(
            lyme_v1,
            args.assets_dir / "lyme-weekly-traces.svg",
        ),
        "lyme_row_scatter": plot_lyme_row_scatter(
            lyme_v1,
            args.assets_dir / "lyme-row-scatter.svg",
        ),
        "feature_importance_comparison": plot_feature_importance_comparison(
            lyme_v1,
            lyme_env_v2,
            args.assets_dir / "feature-importance-comparison.svg",
        ),
    }

    lyme_env_shap = compute_shap_payload(
        lyme_env_v2,
        DATASET_PATH,
        sample_size=args.sample_size,
    )
    figure_map["lyme_env_beeswarm"] = plot_shap_beeswarm(
        lyme_env_v2,
        lyme_env_shap,
        args.assets_dir / "lyme-env-v2-beeswarm.svg",
    )
    figure_map["lyme_env_effects"] = plot_shap_dependence_grid(
        lyme_env_v2,
        lyme_env_shap,
        args.assets_dir / "lyme-env-v2-effects.svg",
    )

    figure_map["kme_pr_calibration"] = plot_kme_pr_and_calibration(
        kme_v2,
        args.assets_dir / "kme-pr-calibration.svg",
    )
    figure_map["kme_lift_importance"] = plot_kme_lift_and_importance(
        kme_v2,
        args.assets_dir / "kme-lift-importance.svg",
    )

    summary = build_summary_payload(lyme_v1, lyme_env_v2, kme_v2)
    html = build_html(summary, figure_map)
    args.html_path.write_text(html, encoding="utf-8")

    print(f"HTML report: {args.html_path}")
    print(f"Assets dir: {args.assets_dir}")
    return 0


def build_matplotlib_theme() -> dict[str, object]:
    return {
        "font.size": 10,
        "figure.facecolor": COLORS["panel"],
        "axes.facecolor": COLORS["panel"],
        "axes.edgecolor": COLORS["grid"],
        "axes.labelcolor": COLORS["ink"],
        "axes.titlecolor": COLORS["ink"],
        "axes.grid": True,
        "grid.color": COLORS["grid"],
        "grid.linewidth": 0.8,
        "grid.alpha": 0.75,
        "text.color": COLORS["ink"],
        "xtick.color": COLORS["ink"],
        "ytick.color": COLORS["ink"],
        "legend.frameon": False,
        "savefig.facecolor": COLORS["panel"],
        "savefig.bbox": "tight",
    }


def load_bundle(
    slug: str,
    label: str,
    artifact_dir: Path,
    target_column: str,
    prediction_column: str,
) -> ModelBundle:
    metadata = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
    predictions = pd.read_csv(artifact_dir / "holdout_predictions.csv")
    if "week_start" in predictions.columns:
        predictions["week_start"] = pd.to_datetime(predictions["week_start"])
    return ModelBundle(
        slug=slug,
        label=label,
        artifact_dir=artifact_dir,
        metadata=metadata,
        predictions=predictions,
        target_column=target_column,
        prediction_column=prediction_column,
    )


def plot_split_timeline(models: list[ModelBundle], output_path: Path) -> str:
    fig, ax = plt.subplots(figsize=(12.5, 4.6))
    row_height = 8
    row_gap = 4
    split_order = ["train", "validation", "test"]

    for index, model in enumerate(models):
        y_base = index * (row_height + row_gap)
        for split_name in split_order:
            split = model.metadata["split_summary"][split_name]
            start = pd.to_datetime(split["start_time"])
            end = pd.to_datetime(split["end_time"])
            start_num = mdates.date2num(start)
            width = mdates.date2num(end) - start_num
            ax.broken_barh(
                [(start_num, width)],
                (y_base, row_height),
                facecolors=COLORS[split_name],
                edgecolors=COLORS["panel"],
                linewidth=1.6,
            )
            ax.text(
                start_num + width / 2,
                y_base + row_height / 2,
                split_name.capitalize(),
                ha="center",
                va="center",
                fontsize=10,
                color="white",
                weight="bold",
            )

    ax.set_yticks(
        [
            index * (row_height + row_gap) + row_height / 2
            for index in range(len(models))
        ],
        [model.label for model in models],
    )
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_title(
        "Time-ordered evaluation windows",
        loc="left",
        fontsize=18,
        pad=14,
        weight="bold",
    )
    ax.set_xlabel("Calendar time")
    ax.set_ylabel("")
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(
        0,
        -0.22,
        (
            "Random split is intentionally excluded. The presentation only reports "
            "future holdout performance."
        ),
        transform=ax.transAxes,
        color=COLORS["muted"],
        fontsize=10,
    )
    save_figure(fig, output_path)
    return output_path.name


def plot_lyme_weekly_traces(bundle: ModelBundle, output_path: Path) -> str:
    fig, axes = plt.subplots(2, 1, figsize=(12.5, 7.6), sharey=True)

    for ax, split_name in zip(axes, ["validation", "test"], strict=True):
        grouped = (
            bundle.predictions[bundle.predictions["split"] == split_name]
            .groupby("week_start")[[bundle.target_column, bundle.prediction_column]]
            .sum()
            .reset_index()
        )
        r2 = r2_score(grouped[bundle.target_column], grouped[bundle.prediction_column])
        corr = grouped[bundle.target_column].corr(grouped[bundle.prediction_column])

        ax.plot(
            grouped["week_start"],
            grouped[bundle.target_column],
            color=COLORS["ink"],
            linewidth=2.2,
            label="Actual weekly cases",
        )
        ax.plot(
            grouped["week_start"],
            grouped[bundle.prediction_column],
            color=COLORS["accent"],
            linewidth=2.0,
            label="Predicted weekly cases",
        )
        ax.fill_between(
            grouped["week_start"],
            grouped[bundle.prediction_column],
            grouped[bundle.target_column],
            color=COLORS["accent_soft"],
            alpha=0.18,
        )
        ax.set_title(
            f"{split_name.capitalize()} holdout",
            loc="left",
            fontsize=13,
            weight="bold",
        )
        ax.set_ylabel("Cases per week")
        ax.text(
            0.995,
            0.95,
            f"Weekly R² {r2:.3f}\nCorrelation {corr:.3f}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=10,
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": COLORS["paper"],
                "edgecolor": COLORS["grid"],
            },
        )
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].legend(loc="upper left", ncol=2)
    axes[-1].set_xlabel("Week start")
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.suptitle(
        "Borelioza baseline follows weekly national dynamics on future weeks",
        x=0.05,
        y=0.99,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    save_figure(fig, output_path)
    return output_path.name


def plot_lyme_row_scatter(bundle: ModelBundle, output_path: Path) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.6), sharex=True, sharey=True)
    series_max = max(
        np.percentile(bundle.predictions[bundle.target_column], 99.7),
        np.percentile(bundle.predictions[bundle.prediction_column], 99.7),
    )

    colorbar_handle = None
    for ax, split_name in zip(axes, ["validation", "test"], strict=True):
        split_predictions = bundle.predictions[bundle.predictions["split"] == split_name]
        mae = mean_absolute_error(
            split_predictions[bundle.target_column],
            split_predictions[bundle.prediction_column],
        )
        rmse = math.sqrt(
            mean_squared_error(
                split_predictions[bundle.target_column],
                split_predictions[bundle.prediction_column],
            )
        )
        r2 = r2_score(
            split_predictions[bundle.target_column],
            split_predictions[bundle.prediction_column],
        )

        colorbar_handle = ax.hexbin(
            split_predictions[bundle.target_column],
            split_predictions[bundle.prediction_column],
            gridsize=34,
            cmap="YlOrBr",
            mincnt=1,
        )
        ax.plot([0, series_max], [0, series_max], linestyle="--", color=COLORS["ink"])
        ax.set_xlim(0, series_max)
        ax.set_ylim(0, series_max)
        ax.set_title(
            split_name.capitalize(),
            loc="left",
            fontsize=13,
            weight="bold",
        )
        ax.text(
            0.98,
            0.95,
            f"RMSE {rmse:.3f}\nMAE {mae:.3f}\nR² {r2:.3f}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=10,
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": COLORS["paper"],
                "edgecolor": COLORS["grid"],
            },
        )
        ax.set_xlabel("Actual municipality-week cases")
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].set_ylabel("Predicted municipality-week cases")
    fig.suptitle(
        "Row-level holdout fit remains structured beyond a single aggregate trace",
        x=0.05,
        y=0.995,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    fig.colorbar(colorbar_handle, ax=axes.ravel().tolist(), label="Rows")
    save_figure(fig, output_path)
    return output_path.name


def plot_feature_importance_comparison(
    lyme_v1: ModelBundle,
    lyme_env_v2: ModelBundle,
    output_path: Path,
) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 8.2))

    for ax, bundle, color, subtitle in [
        (
            axes[0],
            lyme_v1,
            COLORS["accent"],
            "Predictive baseline: epidemiological lag features dominate.",
        ),
        (
            axes[1],
            lyme_env_v2,
            COLORS["train"],
            "Environmental model: seasonality, land cover and relief dominate.",
        ),
    ]:
        df = feature_importance_frame(bundle.metadata).head(12).iloc[::-1]
        ax.barh(df["feature_label"], df["importance"], color=color, alpha=0.92)
        ax.set_title(
            bundle.label,
            loc="left",
            fontsize=14,
            weight="bold",
        )
        ax.set_xlabel("CatBoost feature importance")
        ax.text(
            0.0,
            -0.12,
            subtitle,
            transform=ax.transAxes,
            color=COLORS["muted"],
            fontsize=10,
        )
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle(
        "Feature story changes once epidemiological lags are removed",
        x=0.05,
        y=0.99,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    save_figure(fig, output_path)
    return output_path.name


def feature_importance_frame(metadata: dict) -> pd.DataFrame:
    df = pd.DataFrame(metadata["feature_importances"])
    df["feature_label"] = df["feature"].map(format_feature_label)
    return df.sort_values("importance", ascending=False)


def compute_shap_payload(
    bundle: ModelBundle,
    dataset_path: Path,
    sample_size: int,
) -> dict[str, object]:
    feature_columns = bundle.metadata["feature_columns"]
    categorical_columns = bundle.metadata["categorical_columns"]
    usecols = ["week_start", bundle.target_column, *feature_columns]

    df = pd.read_csv(dataset_path, usecols=usecols)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df[df[bundle.target_column].notna()].copy()

    test_start = pd.to_datetime(bundle.metadata["split_summary"]["test"]["start_time"])
    test_end = pd.to_datetime(bundle.metadata["split_summary"]["test"]["end_time"])
    df = df[df["week_start"].between(test_start, test_end)].copy()

    for column in categorical_columns:
        df[column] = df[column].fillna("MISSING").astype(str)

    if len(df) > sample_size:
        df = df.sample(sample_size, random_state=SEED)

    model = CatBoostClassifier()
    model.load_model(bundle.artifact_dir / "model.cbm")

    pool = Pool(
        df[feature_columns],
        label=df[bundle.target_column],
        cat_features=categorical_columns,
    )
    shap_values = model.get_feature_importance(pool, type="ShapValues")
    sample_features = df[feature_columns].reset_index(drop=True)
    sample_display = sample_features.copy()
    for column in categorical_columns:
        sample_display[column] = sample_display[column].astype("category").cat.codes

    return {
        "feature_columns": feature_columns,
        "categorical_columns": categorical_columns,
        "sample_features": sample_features,
        "sample_display": sample_display,
        "shap_values": shap_values[:, :-1],
        "base_value": shap_values[:, -1].mean(),
    }


def plot_shap_beeswarm(
    bundle: ModelBundle,
    payload: dict[str, object],
    output_path: Path,
) -> str:
    sample_display = payload["sample_display"]
    shap_values = payload["shap_values"]

    plt.figure(figsize=(11.5, 7.4))
    shap.summary_plot(
        shap_values,
        sample_display,
        plot_type="dot",
        max_display=12,
        show=False,
    )
    fig = plt.gcf()
    fig.suptitle(
        f"{bundle.label}: top SHAP contributions on the test holdout sample",
        x=0.05,
        y=0.98,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    fig.text(
        0.05,
        0.92,
        "Each point is one municipality-week. Horizontal position shows contribution to the model score.",
        fontsize=10,
        color=COLORS["muted"],
    )
    save_figure(fig, output_path)
    plt.close(fig)
    return output_path.name


def plot_shap_dependence_grid(
    bundle: ModelBundle,
    payload: dict[str, object],
    output_path: Path,
) -> str:
    feature_columns = payload["feature_columns"]
    categorical_columns = set(payload["categorical_columns"])
    sample_features = payload["sample_features"]
    shap_values = payload["shap_values"]

    ranked = (
        pd.Series(np.abs(shap_values).mean(axis=0), index=feature_columns)
        .sort_values(ascending=False)
        .index.tolist()
    )
    preferred = [
        "urban_cover_pct",
        "elevation_m_range",
        "air_temperature_c_mean_rolling_4w_mean",
        "soil_temperature_level_2_c_mean",
        "week_of_year_cos",
        "mixed_forest_cover_pct",
    ]
    selected: list[str] = []
    for feature in preferred + ranked:
        if feature in categorical_columns:
            continue
        if feature not in selected and feature in feature_columns:
            selected.append(feature)
        if len(selected) == 3:
            break

    fig, axes = plt.subplots(1, len(selected), figsize=(15.2, 4.9))
    if len(selected) == 1:
        axes = [axes]

    for index, (ax, feature_name) in enumerate(zip(axes, selected, strict=True)):
        feature_values = pd.to_numeric(sample_features[feature_name], errors="coerce")
        shap_series = pd.Series(shap_values[:, feature_columns.index(feature_name)])
        plot_df = pd.DataFrame({"feature": feature_values, "shap": shap_series}).dropna()

        ax.scatter(
            plot_df["feature"],
            plot_df["shap"],
            s=18,
            alpha=0.34,
            color=COLORS["accent"],
            edgecolors="none",
        )

        bin_count = min(12, plot_df["feature"].nunique())
        if bin_count >= 4:
            trend = (
                plot_df.assign(
                    bucket=pd.qcut(
                        plot_df["feature"],
                        q=bin_count,
                        duplicates="drop",
                    )
                )
                .groupby("bucket", observed=False)
                .agg(feature_mean=("feature", "mean"), shap_median=("shap", "median"))
                .sort_values("feature_mean")
            )
            ax.plot(
                trend["feature_mean"],
                trend["shap_median"],
                color=COLORS["ink"],
                linewidth=2.1,
            )

        ax.axhline(0, linestyle="--", linewidth=1.0, color=COLORS["muted"])
        ax.set_title(format_feature_label(feature_name), fontsize=12, loc="left", weight="bold")
        ax.set_xlabel("Feature value")
        if index == 0:
            ax.set_ylabel("SHAP contribution")
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle(
        f"{bundle.label}: directional feature effects on model score",
        x=0.05,
        y=0.995,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    fig.text(
        0.05,
        0.92,
        "The black line is the median SHAP contribution inside quantile bins.",
        fontsize=10,
        color=COLORS["muted"],
    )
    save_figure(fig, output_path)
    return output_path.name


def plot_kme_pr_and_calibration(bundle: ModelBundle, output_path: Path) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.5))

    ax_pr, ax_cal = axes
    calibration_summary: list[str] = []
    for split_name, color in [("validation", COLORS["validation"]), ("test", COLORS["accent"])]:
        split_df = bundle.predictions[bundle.predictions["split"] == split_name]
        targets = split_df[bundle.target_column].to_numpy()
        scores = split_df[bundle.prediction_column].to_numpy()

        precision, recall, _ = precision_recall_curve(targets, scores)
        pr_auc = average_precision_score(targets, scores)
        roc_auc = roc_auc_score(targets, scores)

        ax_pr.plot(recall, precision, color=color, linewidth=2.3, label=f"{split_name.capitalize()} PR-AUC {pr_auc:.3f}")
        ax_pr.hlines(
            targets.mean(),
            0,
            1,
            colors=color,
            linestyles="dashed",
            linewidth=1.1,
            alpha=0.5,
        )

        prob_true, prob_pred = calibration_curve(targets, scores, n_bins=10, strategy="quantile")
        ax_cal.plot(
            prob_pred,
            prob_true,
            marker="o",
            linewidth=2.1,
            color=color,
            label=f"{split_name.capitalize()}",
        )
        calibration_summary.append(
            (
                f"{split_name.capitalize()}: ROC AUC {roc_auc:.3f}, "
                f"mean p̂ {scores.mean():.3f}, prevalence {targets.mean():.3f}"
            )
        )

    ax_pr.set_title("Precision-recall", loc="left", fontsize=14, weight="bold")
    ax_pr.set_xlabel("Recall")
    ax_pr.set_ylabel("Precision")
    ax_pr.set_xlim(0, 1)
    ax_pr.set_ylim(0, 0.45)
    ax_pr.legend(loc="upper right")

    ax_cal.plot([0, 1], [0, 1], linestyle="--", color=COLORS["ink"], linewidth=1.0)
    ax_cal.set_title("Calibration", loc="left", fontsize=14, weight="bold")
    ax_cal.set_xlabel("Mean predicted probability")
    ax_cal.set_ylabel("Observed positive rate")
    ax_cal.set_xlim(0, 1)
    ax_cal.set_ylim(0, 0.16)
    ax_cal.legend(loc="upper left")
    ax_cal.text(
        0.98,
        0.05,
        "\n".join(calibration_summary),
        transform=ax_cal.transAxes,
        ha="right",
        va="bottom",
        fontsize=9.5,
        bbox={
            "boxstyle": "round,pad=0.35",
            "facecolor": COLORS["paper"],
            "edgecolor": COLORS["grid"],
        },
    )

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle(
        "KME v2 has ranking signal, but raw probabilities are not calibrated",
        x=0.05,
        y=0.995,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    save_figure(fig, output_path)
    return output_path.name


def plot_kme_lift_and_importance(bundle: ModelBundle, output_path: Path) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 6.2))
    ax_lift, ax_imp = axes

    kme_stats = []
    for split_name, color in [("validation", COLORS["validation"]), ("test", COLORS["accent"])]:
        split_df = bundle.predictions[bundle.predictions["split"] == split_name].copy()
        split_df = split_df.sort_values(bundle.prediction_column, ascending=False).reset_index(drop=True)
        targets = split_df[bundle.target_column].to_numpy()
        prevalence = targets.mean()
        cumulative_positive = np.cumsum(targets)
        ranks = np.arange(1, len(split_df) + 1)
        fraction = ranks / len(split_df)
        precision = cumulative_positive / ranks
        lift = np.divide(precision, prevalence, out=np.zeros_like(precision, dtype=float), where=prevalence > 0)
        mask = fraction <= 0.20

        ax_lift.plot(
            fraction[mask],
            lift[mask],
            color=color,
            linewidth=2.3,
            label=f"{split_name.capitalize()}",
        )

        top_one_pct_n = max(1, int(len(split_df) * 0.01))
        top_one_pct_precision = split_df.head(top_one_pct_n)[bundle.target_column].mean()
        kme_stats.append(
            f"{split_name.capitalize()}: top 1% precision {top_one_pct_precision:.3f}, lift {top_one_pct_precision / prevalence:.1f}x"
        )

    ax_lift.axhline(1.0, linestyle="--", color=COLORS["ink"], linewidth=1.0)
    ax_lift.set_title("Cumulative lift curve", loc="left", fontsize=14, weight="bold")
    ax_lift.set_xlabel("Share of municipality-week rows ranked highest")
    ax_lift.set_ylabel("Lift vs base rate")
    ax_lift.set_xlim(0, 0.20)
    ax_lift.set_ylim(0, 28)
    ax_lift.legend(loc="upper right")
    ax_lift.text(
        0.98,
        0.95,
        "\n".join(kme_stats),
        transform=ax_lift.transAxes,
        ha="right",
        va="top",
        fontsize=9.5,
        bbox={
            "boxstyle": "round,pad=0.35",
            "facecolor": COLORS["paper"],
            "edgecolor": COLORS["grid"],
        },
    )

    importance_df = feature_importance_frame(bundle.metadata).head(12).iloc[::-1]
    ax_imp.barh(importance_df["feature_label"], importance_df["importance"], color=COLORS["train"], alpha=0.92)
    ax_imp.set_title("Top drivers", loc="left", fontsize=14, weight="bold")
    ax_imp.set_xlabel("CatBoost feature importance")

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle(
        "KME v2 is useful for hotspot prioritization, not for direct probability claims",
        x=0.05,
        y=0.995,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    save_figure(fig, output_path)
    return output_path.name


def save_figure(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=PLOT_DPI)
    plt.close(fig)


def build_summary_payload(
    lyme_v1: ModelBundle,
    lyme_env_v2: ModelBundle,
    kme_v2: ModelBundle,
) -> dict[str, object]:
    lyme_test_weekly = (
        lyme_v1.predictions[lyme_v1.predictions["split"] == "test"]
        .groupby("week_start")[[lyme_v1.target_column, lyme_v1.prediction_column]]
        .sum()
        .reset_index()
    )
    lyme_test_weekly_r2 = r2_score(
        lyme_test_weekly[lyme_v1.target_column],
        lyme_test_weekly[lyme_v1.prediction_column],
    )
    lyme_test_weekly_corr = lyme_test_weekly[lyme_v1.target_column].corr(
        lyme_test_weekly[lyme_v1.prediction_column]
    )

    kme_test = kme_v2.predictions[kme_v2.predictions["split"] == "test"].copy()
    top_one_pct_n = max(1, int(len(kme_test) * 0.01))
    top_one_pct_precision = kme_test.sort_values(kme_v2.prediction_column, ascending=False).head(top_one_pct_n)[
        kme_v2.target_column
    ].mean()
    kme_prevalence = kme_test[kme_v2.target_column].mean()

    return {
        "generated_on": pd.Timestamp.now(tz="Europe/Ljubljana").strftime("%Y-%m-%d %H:%M %Z"),
        "lyme_v1": {
            "test_rmse": lyme_v1.metadata["metrics"]["test"]["rmse"],
            "test_mae": lyme_v1.metadata["metrics"]["test"]["mae"],
            "test_r2": lyme_v1.metadata["metrics"]["test"]["r2"],
            "weekly_test_r2": lyme_test_weekly_r2,
            "weekly_test_corr": lyme_test_weekly_corr,
        },
        "lyme_env_v2": {
            "test_accuracy": lyme_env_v2.metadata["metrics"]["test"]["accuracy"],
            "test_precision": lyme_env_v2.metadata["metrics"]["test"]["precision"],
            "test_recall": lyme_env_v2.metadata["metrics"]["test"]["recall"],
            "test_f1": lyme_env_v2.metadata["metrics"]["test"]["f1"],
            "test_roc_auc": lyme_env_v2.metadata["metrics"]["test"]["roc_auc"],
            "test_pr_auc": lyme_env_v2.metadata["metrics"]["test"]["pr_auc"],
        },
        "kme_v2": {
            "test_roc_auc": roc_auc_score(
                kme_test[kme_v2.target_column],
                kme_test[kme_v2.prediction_column],
            ),
            "test_pr_auc": average_precision_score(
                kme_test[kme_v2.target_column],
                kme_test[kme_v2.prediction_column],
            ),
            "test_prevalence": kme_prevalence,
            "test_mean_predicted_probability": kme_test[kme_v2.prediction_column].mean(),
            "test_top_one_pct_precision": top_one_pct_precision,
            "test_top_one_pct_lift": top_one_pct_precision / kme_prevalence,
        },
    }


def build_html(summary: dict[str, object], figure_map: dict[str, str]) -> str:
    lyme_v1 = summary["lyme_v1"]
    lyme_env_v2 = summary["lyme_env_v2"]
    kme_v2 = summary["kme_v2"]

    return f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>KlopPodKlopjo: Hackathon research report</title>
  <style>
    :root {{
      --paper: #f6f2ea;
      --panel: #fffdf8;
      --ink: #1f2937;
      --muted: #6b7280;
      --grid: #e7dfd1;
      --train: #1f6f8b;
      --validation: #d97706;
      --test: #c2410c;
      --accent: #8b2c2a;
      --success: #2f7f63;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #efe6da 0%, #f6f2ea 14%, #f9f6ef 100%);
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    a {{ color: inherit; }}
    .deck {{
      width: min(1200px, 94vw);
      margin: 0 auto;
      padding: 28px 0 40px;
    }}
    .slide {{
      background: rgba(255, 253, 248, 0.92);
      border: 1px solid rgba(231, 223, 209, 0.95);
      border-radius: 28px;
      box-shadow: 0 24px 60px rgba(66, 37, 18, 0.08);
      padding: 34px 38px 36px;
      margin-bottom: 26px;
      min-height: 70vh;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .kicker {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(31, 111, 139, 0.08);
      color: var(--train);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-weight: 700;
    }}
    h1, h2, h3 {{
      margin: 0;
      line-height: 1.08;
    }}
    h1 {{
      font-size: clamp(2.2rem, 5vw, 4.5rem);
      max-width: 900px;
    }}
    h2 {{
      font-size: clamp(1.6rem, 3vw, 2.35rem);
      margin-top: 14px;
    }}
    p.lead {{
      font-size: 1.1rem;
      max-width: 900px;
      color: var(--muted);
      margin: 18px 0 0;
    }}
    .hero-grid, .metric-grid, .two-up, .three-up {{
      display: grid;
      gap: 16px;
    }}
    .hero-grid {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin-top: 28px;
    }}
    .metric-grid {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin-top: 22px;
    }}
    .two-up {{
      grid-template-columns: 1.2fr 0.8fr;
      align-items: start;
      margin-top: 18px;
    }}
    .three-up {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin-top: 18px;
    }}
    .card {{
      background: white;
      border: 1px solid var(--grid);
      border-radius: 22px;
      padding: 18px 18px 16px;
    }}
    .metric {{
      font-size: 2rem;
      font-weight: 800;
      margin-top: 6px;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .figure {{
      background: white;
      border: 1px solid var(--grid);
      border-radius: 22px;
      padding: 14px;
    }}
    .figure img {{
      width: 100%;
      display: block;
      border-radius: 14px;
    }}
    .caption {{
      font-size: 0.94rem;
      color: var(--muted);
      margin-top: 10px;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    li + li {{
      margin-top: 8px;
    }}
    .truth-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-top: 18px;
    }}
    .truth-card.good {{
      border-left: 6px solid var(--success);
    }}
    .truth-card.bad {{
      border-left: 6px solid var(--accent);
    }}
    .footer {{
      font-size: 0.92rem;
      color: var(--muted);
      margin-top: 18px;
    }}
    @media (max-width: 960px) {{
      .hero-grid, .metric-grid, .two-up, .three-up, .truth-grid {{
        grid-template-columns: 1fr;
      }}
      .slide {{
        min-height: auto;
        padding: 24px 22px;
      }}
    }}
    @media print {{
      body {{ background: white; }}
      .deck {{ width: auto; padding: 0; }}
      .slide {{
        break-after: page;
        box-shadow: none;
        border-radius: 0;
        margin: 0;
        min-height: 100vh;
      }}
    }}
  </style>
</head>
<body>
  <main class="deck">
    <section class="slide">
      <div>
        <span class="kicker">Hackathon research deck</span>
        <h1>KlopPodKlopjo: data-driven tick risk modeling for Slovenia</h1>
        <p class="lead">
          Presentation-ready research report generated from local model artifacts, holdout
          predictions and CatBoost SHAP analysis. This file is meant to be opened directly in
          a browser and reused as source material for slides.
        </p>
        <div class="hero-grid">
          <div class="card">
            <div class="metric-label">Borelioza baseline</div>
            <div class="metric">{lyme_v1["test_r2"]:.3f}</div>
            <div class="metric-label">Test R² on municipality-week rows</div>
          </div>
          <div class="card">
            <div class="metric-label">Borelioza baseline</div>
            <div class="metric">{lyme_v1["weekly_test_r2"]:.3f}</div>
            <div class="metric-label">Weekly national R² on future holdout</div>
          </div>
          <div class="card">
            <div class="metric-label">Borelioza env v2</div>
            <div class="metric">{lyme_env_v2["test_roc_auc"]:.3f}</div>
            <div class="metric-label">Test ROC AUC for 4-week presence signal</div>
          </div>
          <div class="card">
            <div class="metric-label">KME ranking v2</div>
            <div class="metric">{kme_v2["test_top_one_pct_lift"]:.1f}x</div>
            <div class="metric-label">Lift in the highest-scoring 1% of rows</div>
          </div>
        </div>
      </div>
      <div class="footer">
        Generated on {summary["generated_on"]}. HTML file and chart assets were produced locally from
        data in <code>data/processed/training/</code>.
      </div>
    </section>

    <section class="slide">
      <div>
        <span class="kicker">1. Methodology</span>
        <h2>Evaluation is time-ordered, not random</h2>
        <div class="two-up">
          <figure class="figure">
            <img src="hackathon-research-report-assets/{figure_map["split_timeline"]}" alt="Split timeline" />
            <figcaption class="caption">
              All headline results come from future holdout weeks. This is the first visual you should
              show if the jury asks about leakage or overfitting.
            </figcaption>
          </figure>
          <div class="card">
            <h3>Talking points</h3>
            <ul>
              <li>Training ends on 2023-01-16 for the main benchmark models.</li>
              <li>Validation and test windows contain only future weeks.</li>
              <li>Random split is intentionally excluded from the main story.</li>
              <li>The same temporal evaluation protocol is reused across disease targets.</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <section class="slide">
      <div>
        <span class="kicker">2. Borelioza baseline</span>
        <h2>The baseline tracks weekly national dynamics on unseen future data</h2>
        <div class="metric-grid">
          <div class="card">
            <div class="metric-label">Test RMSE</div>
            <div class="metric">{lyme_v1["test_rmse"]:.3f}</div>
          </div>
          <div class="card">
            <div class="metric-label">Test MAE</div>
            <div class="metric">{lyme_v1["test_mae"]:.3f}</div>
          </div>
          <div class="card">
            <div class="metric-label">Weekly test R²</div>
            <div class="metric">{lyme_v1["weekly_test_r2"]:.3f}</div>
          </div>
          <div class="card">
            <div class="metric-label">Weekly test correlation</div>
            <div class="metric">{lyme_v1["weekly_test_corr"]:.3f}</div>
          </div>
        </div>
        <figure class="figure" style="margin-top:18px;">
          <img src="hackathon-research-report-assets/{figure_map["lyme_weekly_traces"]}" alt="Lyme weekly traces" />
          <figcaption class="caption">
            Use this figure as the central proof slide. It shows that the model follows real epidemic
            timing, not only isolated municipality rows.
          </figcaption>
        </figure>
      </div>
    </section>

    <section class="slide">
      <div>
        <span class="kicker">3. Borelioza baseline</span>
        <h2>Signal persists at municipality-week resolution</h2>
        <div class="two-up">
          <figure class="figure">
            <img src="hackathon-research-report-assets/{figure_map["lyme_row_scatter"]}" alt="Lyme row scatter" />
            <figcaption class="caption">
              Hexbins prevent the plot from collapsing into overdraw. The diagonal shows ideal fit.
            </figcaption>
          </figure>
          <div class="card">
            <h3>How to narrate it</h3>
            <ul>
              <li>The model is not perfect, but the structure is clearly non-random.</li>
              <li>Holdout error rises from validation to test, which is expected and believable.</li>
              <li>This baseline is strong for prediction, but it is not the cleanest causal explanation model.</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <section class="slide">
      <div>
        <span class="kicker">4. Model comparison</span>
        <h2>Predictive baseline and environmental model do not tell the same story</h2>
        <figure class="figure">
          <img src="hackathon-research-report-assets/{figure_map["feature_importance_comparison"]}" alt="Feature importance comparison" />
          <figcaption class="caption">
            The left panel is excellent for prediction, but heavily supported by epidemiological lag features.
            The right panel is more interpretable for an environmental risk narrative.
          </figcaption>
        </figure>
      </div>
    </section>

    <section class="slide">
      <div>
        <span class="kicker">5. Feature effects</span>
        <h2>SHAP shows which environmental signals move the borelioza env v2 score</h2>
        <div class="two-up">
          <figure class="figure">
            <img src="hackathon-research-report-assets/{figure_map["lyme_env_beeswarm"]}" alt="Lyme env beeswarm" />
            <figcaption class="caption">
              Beeswarm summary over a test sample. Horizontal position is contribution to the model score.
            </figcaption>
          </figure>
          <figure class="figure">
            <img src="hackathon-research-report-assets/{figure_map["lyme_env_effects"]}" alt="Lyme env feature effects" />
            <figcaption class="caption">
              Directional SHAP plots provide the “research slide” that makes feature effects concrete.
            </figcaption>
          </figure>
        </div>
      </div>
    </section>

    <section class="slide">
      <div>
        <span class="kicker">6. KME v2</span>
        <h2>Ranking works, raw probability does not</h2>
        <div class="metric-grid">
          <div class="card">
            <div class="metric-label">Test ROC AUC</div>
            <div class="metric">{kme_v2["test_roc_auc"]:.3f}</div>
          </div>
          <div class="card">
            <div class="metric-label">Test PR-AUC</div>
            <div class="metric">{kme_v2["test_pr_auc"]:.3f}</div>
          </div>
          <div class="card">
            <div class="metric-label">Observed prevalence</div>
            <div class="metric">{100 * kme_v2["test_prevalence"]:.2f}%</div>
          </div>
          <div class="card">
            <div class="metric-label">Mean predicted probability</div>
            <div class="metric">{100 * kme_v2["test_mean_predicted_probability"]:.1f}%</div>
          </div>
        </div>
        <figure class="figure" style="margin-top:18px;">
          <img src="hackathon-research-report-assets/{figure_map["kme_pr_calibration"]}" alt="KME PR and calibration" />
          <figcaption class="caption">
            This is the slide that makes the story scientifically honest: useful ranking signal, poor
            calibration, therefore not a literal personal probability.
          </figcaption>
        </figure>
      </div>
    </section>

    <section class="slide">
      <div>
        <span class="kicker">7. KME v2</span>
        <h2>High-score rows are enriched with real positives</h2>
        <div class="two-up">
          <figure class="figure">
            <img src="hackathon-research-report-assets/{figure_map["kme_lift_importance"]}" alt="KME lift and importance" />
            <figcaption class="caption">
              The first 1% of test rows is enriched by {kme_v2["test_top_one_pct_lift"]:.1f}x versus the base rate.
              This supports a hotspot-ranking use case.
            </figcaption>
          </figure>
          <div class="card">
            <h3>How to phrase it</h3>
            <ul>
              <li>The model is valid for ranking municipality-week hotspots.</li>
              <li>The model is not valid as a literal “30% probability of KME”.</li>
              <li>Rare-event accuracy is not the main metric and should stay out of the headline.</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <section class="slide">
      <div>
        <span class="kicker">8. Claims</span>
        <h2>What you can say clearly, honestly and confidently</h2>
        <div class="truth-grid">
          <div class="card truth-card good">
            <h3>Valid claims</h3>
            <ul>
              <li>We evaluate on future weeks, not on random rows.</li>
              <li>For borelioza, the baseline captures weekly epidemic dynamics on holdout data.</li>
              <li>For environmental models, seasonality, land cover and relief materially influence model output.</li>
              <li>For KME, the prototype is useful for hotspot ranking and triage.</li>
              <li>The municipal score is a relative risk index, not a diagnosis.</li>
            </ul>
          </div>
          <div class="card truth-card bad">
            <h3>Claims to avoid</h3>
            <ul>
              <li>Do not claim calibrated personal disease probabilities.</li>
              <li>Do not present KME accuracy as the main success metric.</li>
              <li>Do not equate feature importance with biological causality.</li>
              <li>Do not say the predictive baseline is a purely environmental model.</li>
              <li>Do not imply the system replaces medical advice or surveillance.</li>
            </ul>
          </div>
        </div>
      </div>
      <div class="footer">
        Reusable asset folder: <code>docs/presentation/hackathon-research-report-assets/</code>.
        Main HTML deck: <code>docs/presentation/hackathon-research-report.html</code>.
      </div>
    </section>
  </main>
</body>
</html>
"""


def format_feature_label(feature_name: str) -> str:
    label = feature_name.replace("_pct", " %").replace("_m3_m3", " m3/m3")
    label = label.replace("_c", " °C").replace("_mm", " mm")
    label = label.replace("_", " ")
    label = label.replace(" ge ", " ≥ ")
    label = label.replace("  ", " ")
    return "\n".join(textwrap.wrap(label, width=23))


if __name__ == "__main__":
    raise SystemExit(main())
