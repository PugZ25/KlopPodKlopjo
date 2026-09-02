from __future__ import annotations

import os
from pathlib import Path

from pipeline_utils import PROJECT_ROOT, timestamp_utc, write_json


MPL_CONFIG_DIR = PROJECT_ROOT / "interim" / "matplotlib_config"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import pandas as pd


WORKSPACE_DIR = PROJECT_ROOT / "modeling - model_c_climate_effect"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
REPORTS_DIR = WORKSPACE_DIR / "reports"
CHARTS_DIR = OUTPUTS_DIR / "charts"

GRAPH_10Y = OUTPUTS_DIR / "model_c_graph_prevalence_10y.csv"
METRICS_CSV = OUTPUTS_DIR / "model_c_final_validation_metrics.csv"

MODEL_ORDER = [
    "lyme_prevalence",
    "kme_prevalence",
    "combined_prevalence",
]

MODEL_TITLES = {
    "lyme_prevalence": "Lyme Prevalence",
    "kme_prevalence": "KME Prevalence",
    "combined_prevalence": "Combined Tick-Borne Prevalence",
}

SCENARIO_LABELS = {
    "medium_emissions": "Medium-emissions scenario",
    "high_emissions": "High-emissions scenario",
}

COLORS = {
    "background": "#F5FAF6",
    "panel_fill": "#FBFDFB",
    "history": "#1F2933",
    "history_points": "#334E68",
    "medium_emissions": "#5BAE6A",
    "high_emissions": "#0B6E4F",
    "future_zone": "#DFF3E3",
    "future_zone_edge": "#A7D7AF",
    "scenario_band": "#A7D7AF",
    "grid": "#D7E8DB",
    "text": "#173024",
    "muted": "#5C7A68",
}


def ensure_dirs() -> None:
    for path in [CHARTS_DIR, REPORTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def prevalence_formatter(value: float, _: int) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    return f"{value:,.1f}"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    graph = pd.read_csv(GRAPH_10Y, encoding="utf-8-sig")
    metrics = pd.read_csv(METRICS_CSV, encoding="utf-8-sig")
    graph["year"] = pd.to_numeric(graph["year"], errors="coerce").astype(int)
    graph["prevalence_per_100k"] = pd.to_numeric(graph["prevalence_per_100k"], errors="coerce")
    return graph, metrics


def model_metric_lookup(metrics: pd.DataFrame) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for model_name, frame in metrics.groupby("model_name", sort=False):
        result[model_name] = {
            str(row.metric_name): float(row.metric_value)
            for row in frame.itertuples(index=False)
        }
    return result


def style_axis(ax: plt.Axes) -> None:
    ax.set_facecolor(COLORS["panel_fill"])
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.8, alpha=1.0)
    ax.grid(axis="x", visible=False)
    ax.tick_params(colors=COLORS["muted"], labelsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.yaxis.set_major_formatter(FuncFormatter(prevalence_formatter))


def plot_one_panel(
    *,
    ax: plt.Axes,
    frame: pd.DataFrame,
    model_name: str,
    metric_lookup: dict[str, dict[str, float]],
    show_legend: bool,
) -> None:
    style_axis(ax)

    history = frame[frame["series_role"] == "observed_history"].drop_duplicates(subset=["year"]).copy()
    medium = frame[
        (frame["series_role"] == "predicted_future") & (frame["scenario_family"] == "medium_emissions")
    ].copy()
    high = frame[
        (frame["series_role"] == "predicted_future") & (frame["scenario_family"] == "high_emissions")
    ].copy()

    ymin = float(frame["prevalence_per_100k"].min())
    ymax = float(frame["prevalence_per_100k"].max())
    pad = max((ymax - ymin) * 0.18, ymax * 0.08 if ymax else 1.0)

    ax.axvspan(2025.5, 2035.5, color=COLORS["future_zone"], alpha=1.0, zorder=0)
    ax.axvline(2025.5, color=COLORS["future_zone_edge"], linewidth=1.8, linestyle="--", zorder=1)

    if not medium.empty and not high.empty:
        corridor = medium[["year", "prevalence_per_100k"]].merge(
            high[["year", "prevalence_per_100k"]],
            on="year",
            suffixes=("_medium", "_high"),
            how="inner",
        )
        lower = corridor[["prevalence_per_100k_medium", "prevalence_per_100k_high"]].min(axis=1)
        upper = corridor[["prevalence_per_100k_medium", "prevalence_per_100k_high"]].max(axis=1)
        ax.fill_between(
            corridor["year"],
            lower,
            upper,
            color=COLORS["scenario_band"],
            alpha=0.32,
            zorder=2,
        )

    ax.plot(
        history["year"],
        history["prevalence_per_100k"],
        color=COLORS["history"],
        linewidth=2.8,
        zorder=4,
    )
    ax.scatter(
        history["year"],
        history["prevalence_per_100k"],
        color=COLORS["history_points"],
        edgecolor="white",
        linewidth=0.7,
        s=28,
        zorder=5,
    )

    ax.plot(
        medium["year"],
        medium["prevalence_per_100k"],
        color=COLORS["medium_emissions"],
        linewidth=2.8,
        zorder=6,
    )
    ax.plot(
        high["year"],
        high["prevalence_per_100k"],
        color=COLORS["high_emissions"],
        linewidth=2.8,
        zorder=7,
    )

    ax.set_xlim(2016, 2035)
    ax.set_ylim(max(0.0, ymin - pad * 0.20), ymax + pad)
    ax.set_title(MODEL_TITLES[model_name], fontsize=16, color=COLORS["text"], weight="bold", loc="left")
    ax.text(
        0.0,
        1.02,
        "Observed history transitions into climate-scenario prevalence projection",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10,
        color=COLORS["muted"],
    )
    ax.text(
        2026.05,
        ymax + pad * 0.62,
        "Projected climate-effect window",
        color=COLORS["high_emissions"],
        fontsize=10,
        weight="bold",
    )

    rmse = metric_lookup.get(model_name, {}).get("weighted_rmse")
    mape = metric_lookup.get(model_name, {}).get("weighted_mape_pct")
    if rmse is not None and mape is not None:
        ax.text(
            0.985,
            0.95,
            f"Holdout RMSE: {rmse:,.1f}\nHoldout MAPE: {mape:,.1f}%",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=9.5,
            color=COLORS["text"],
            bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor=COLORS["grid"]),
        )

    if show_legend:
        legend_handles = [
            Line2D([0], [0], color=COLORS["history"], lw=2.8, label="Observed prevalence"),
            Line2D([0], [0], color=COLORS["medium_emissions"], lw=2.8, label=SCENARIO_LABELS["medium_emissions"]),
            Line2D([0], [0], color=COLORS["high_emissions"], lw=2.8, label=SCENARIO_LABELS["high_emissions"]),
            Patch(facecolor=COLORS["future_zone"], edgecolor=COLORS["future_zone_edge"], label="Projection zone"),
        ]
        ax.legend(
            handles=legend_handles,
            ncol=2,
            loc="lower left",
            frameon=False,
            fontsize=10,
            labelcolor=COLORS["text"],
        )


def save_dashboard(graph: pd.DataFrame, metrics: pd.DataFrame) -> list[str]:
    metric_lookup = model_metric_lookup(metrics)
    fig, axes = plt.subplots(3, 1, figsize=(15.5, 16.8))
    fig.patch.set_facecolor(COLORS["background"])
    fig.subplots_adjust(top=0.89, bottom=0.06, left=0.08, right=0.985, hspace=0.32)

    for idx, model_name in enumerate(MODEL_ORDER):
        frame = graph[graph["model_name"] == model_name].copy()
        plot_one_panel(
            ax=axes[idx],
            frame=frame,
            model_name=model_name,
            metric_lookup=metric_lookup,
            show_legend=(idx == 0),
        )
        axes[idx].set_xlabel("Year", fontsize=11, color=COLORS["text"])
        axes[idx].set_ylabel("Prevalence per 100k", fontsize=11, color=COLORS["text"])

    fig.suptitle(
        "Slovenia Tick-Borne Disease Climate-Effect Outlook",
        fontsize=24,
        color=COLORS["text"],
        weight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.942,
        "Historical prevalence through 2025 with medium- and high-emissions scenario projections through 2035",
        ha="center",
        fontsize=12,
        color=COLORS["muted"],
    )

    outputs = []
    for suffix in ["png", "svg"]:
        path = CHARTS_DIR / f"model_c_prevalence_dashboard_10y.{suffix}"
        fig.savefig(path, dpi=240 if suffix == "png" else None, facecolor=fig.get_facecolor(), bbox_inches="tight")
        outputs.append(str(path))
    plt.close(fig)
    return outputs


def save_individual_charts(graph: pd.DataFrame, metrics: pd.DataFrame) -> list[str]:
    metric_lookup = model_metric_lookup(metrics)
    outputs: list[str] = []

    for model_name in MODEL_ORDER:
        frame = graph[graph["model_name"] == model_name].copy()
        fig, ax = plt.subplots(figsize=(14.5, 8.5), constrained_layout=True)
        fig.patch.set_facecolor(COLORS["background"])
        plot_one_panel(
            ax=ax,
            frame=frame,
            model_name=model_name,
            metric_lookup=metric_lookup,
            show_legend=True,
        )
        ax.set_xlabel("Year", fontsize=12, color=COLORS["text"])
        ax.set_ylabel("Prevalence per 100k", fontsize=12, color=COLORS["text"])

        for suffix in ["png", "svg"]:
            path = CHARTS_DIR / f"{model_name}_10y_presentation.{suffix}"
            fig.savefig(path, dpi=240 if suffix == "png" else None, facecolor=fig.get_facecolor(), bbox_inches="tight")
            outputs.append(str(path))
        plt.close(fig)

    return outputs


def write_chart_report(saved_paths: list[str]) -> None:
    lines = [
        "# Model C Presentation Graphs",
        "",
        f"- generated at: `{timestamp_utc()}`",
        "- visual style: green-forward forecast highlights with pale future shading",
        "- chart coverage: observed history 2016-2025 plus projected 2026-2035 scenario paths",
        "",
        "## Saved Files",
        "",
    ]
    for path in saved_paths:
        lines.append(f"- `{path}`")

    (REPORTS_DIR / "model_c_presentation_graphs_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ensure_dirs()
    graph, metrics = load_inputs()
    saved_paths = []
    saved_paths.extend(save_dashboard(graph, metrics))
    saved_paths.extend(save_individual_charts(graph, metrics))

    write_json(
        CHARTS_DIR / "model_c_presentation_graphs_manifest.json",
        {
            "generated_at": timestamp_utc(),
            "source_graph_csv": str(GRAPH_10Y),
            "source_metrics_csv": str(METRICS_CSV),
            "saved_paths": saved_paths,
        },
    )
    write_chart_report(saved_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
