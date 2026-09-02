#!/usr/bin/env python3
"""Build Slovenian graph exports and a standalone HTML report for okoljski_raziskovalni_model."""

from __future__ import annotations

import json
import os
from datetime import datetime
from html import escape
from pathlib import Path

MPL_CONFIG_DIR = Path(__file__).resolve().parents[1] / ".mplconfig"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
GROUPED_EVAL_DIR = PROCESSED_DIR / "model_grouped_evaluation"
LIVING_README_PATH = INTERIM_DIR / "Slovenia_local_data_normalized" / "README_LOCAL_DATA_NORMALIZATION.md"

GROUP_SCORE_PATH = GROUPED_EVAL_DIR / "environment_graph_ready_group_scores.csv"
GROUP_MANIFEST_PATH = GROUPED_EVAL_DIR / "environment_group_feature_manifest.csv"

ALL_GROUPS_PNG = GROUPED_EVAL_DIR / "environment_grouped_ablation_all_groups.png"
ALL_GROUPS_SVG = GROUPED_EVAL_DIR / "environment_grouped_ablation_all_groups.svg"
LOCAL_GROUPS_PNG = GROUPED_EVAL_DIR / "environment_grouped_ablation_local_groups.png"
LOCAL_GROUPS_SVG = GROUPED_EVAL_DIR / "environment_grouped_ablation_local_groups.svg"
COMMENTARY_PATH = GROUPED_EVAL_DIR / "ENVIRONMENT_GROUPED_GRAPH_COMMENTARY.md"
HTML_REPORT_PATH = GROUPED_EVAL_DIR / "okoljski_grafi_porocilo.html"
RUN_SUMMARY_PATH = GROUPED_EVAL_DIR / "environment_grouped_graphs_run_summary.json"

TARGET_ORDER = [
    "tickborne_current4w_per100k",
    "lyme_current4w_per100k",
    "kme_current8w_per100k",
]
TARGET_TITLES = {
    "tickborne_current4w_per100k": "Skupno breme klopnih bolezni: uporabnost okoljskih sklopov",
    "lyme_current4w_per100k": "Lymska borelioza: uporabnost okoljskih sklopov",
    "kme_current8w_per100k": "KME: uporabnost okoljskih sklopov",
}
TARGET_SHORT_LABELS = {
    "tickborne_current4w_per100k": "Skupno breme klopnih bolezni",
    "lyme_current4w_per100k": "Lymska borelioza",
    "kme_current8w_per100k": "KME",
}
GROUP_LABELS = {
    "copernicus_temperature": "Temperatura (Copernicus)",
    "copernicus_humidity": "Vlažnost (Copernicus)",
    "copernicus_precipitation": "Padavine (Copernicus)",
    "copernicus_soil": "Tla in talna vlaga (Copernicus)",
    "topography": "Topografija",
    "land_cover": "Raba tal",
    "population": "Poseljenost",
    "arso_temperature": "Temperatura (ARSO)",
    "arso_humidity": "Vlažnost (ARSO)",
    "arso_precipitation": "Padavine (ARSO)",
    "gozdis_temperature": "Temperatura (GOZDIS)",
    "gozdis_humidity": "Vlažnost (GOZDIS)",
    "gozdis_precipitation": "Padavine (GOZDIS)",
    "obrod_summary": "Obrod gozdnih vrst",
    "time_control_hidden": "Skriti letni fazni nadzor",
}
GROUP_CLASS_COLORS = {
    "core": "#295C6A",
    "local_optional": "#B06C2B",
}
GROUP_CLASS_LABELS = {
    "core": "Jedrni okoljski sklop",
    "local_optional": "Lokalni dodatni vir",
}


def load_scores() -> pd.DataFrame:
    df = pd.read_csv(GROUP_SCORE_PATH)
    df["group_label"] = df["group_name"].map(GROUP_LABELS).fillna(df["group_name"])
    return df


def load_group_manifest() -> pd.DataFrame:
    return pd.read_csv(GROUP_MANIFEST_PATH)


def load_hidden_group_labels(manifest_df: pd.DataFrame) -> list[str]:
    hidden_df = manifest_df[manifest_df["group_name"] == "time_control_hidden"].copy()
    if hidden_df.empty:
        return []
    return hidden_df["group_name"].map(GROUP_LABELS).fillna(hidden_df["group_name"]).drop_duplicates().tolist()


def style_axis(ax: plt.Axes, title: str) -> None:
    ax.axvline(0, color="#46555B", linewidth=1.1, linestyle="--", alpha=0.8)
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left")
    ax.set_xlabel(
        "Povprečni učinek na RMSE glede na referenčni okoljski model (pozitivno = večja uporabnost)",
        fontsize=10,
    )
    ax.grid(axis="x", color="#D5DFE5", linestyle="-", linewidth=0.8, alpha=0.85)
    ax.set_facecolor("#F8F4EC")
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#83919A")
    ax.tick_params(axis="y", length=0)


def set_x_margin(ax: plt.Axes, values: list[float], right_extra: float) -> None:
    max_abs = max(abs(min(values)), abs(max(values))) if values else 1.0
    left = -max_abs * 1.2
    right = max_abs * (1.0 + right_extra)
    if left == right:
        left -= 0.1
        right += 0.1
    ax.set_xlim(left, right)


def add_bar_annotations(ax: plt.Axes, subset: pd.DataFrame) -> None:
    values = subset["mean_rmse_effect_vs_reference"].tolist()
    max_abs = max(abs(min(values)), abs(max(values))) if values else 1.0
    offset = max_abs * 0.03 if max_abs > 0 else 0.02

    for idx, row in subset.reset_index(drop=True).iterrows():
        value = float(row["mean_rmse_effect_vs_reference"])
        label = (
            f"pokr. {row['mean_group_validation_coverage_pct']:.1f}% | "
            f"koristna leta {row['helpful_folds_pct']:.0f}%"
        )
        x = value + offset if value >= 0 else value - offset
        ha = "left" if value >= 0 else "right"
        ax.text(x, idx, label, va="center", ha=ha, fontsize=8.5, color="#2C3439")


def build_all_groups_figure(df: pd.DataFrame) -> None:
    max_groups = max(df[df["target_name"] == target_name].shape[0] for target_name in TARGET_ORDER)
    fig_height = max(11.6, 2.8 + len(TARGET_ORDER) * max_groups * 0.38)
    fig, axes = plt.subplots(nrows=len(TARGET_ORDER), ncols=1, figsize=(14.6, fig_height), constrained_layout=True)
    fig.patch.set_facecolor("#ECE4D5")

    if len(TARGET_ORDER) == 1:
        axes = [axes]

    for ax, target_name in zip(axes, TARGET_ORDER):
        subset = df[df["target_name"] == target_name].copy().sort_values("mean_rmse_effect_vs_reference")
        values = subset["mean_rmse_effect_vs_reference"].tolist()
        colors = [GROUP_CLASS_COLORS.get(value, "#6B7A84") for value in subset["group_class"]]
        ax.barh(subset["group_label"], subset["mean_rmse_effect_vs_reference"], color=colors, edgecolor="#2C3439", linewidth=0.5)
        style_axis(ax, TARGET_TITLES[target_name])
        set_x_margin(ax, values, right_extra=0.95)
        add_bar_annotations(ax, subset.reset_index(drop=True))

    legend_items = [
        Patch(facecolor=GROUP_CLASS_COLORS["core"], edgecolor="#243038", label="Jedrni okoljski sklop"),
        Patch(facecolor=GROUP_CLASS_COLORS["local_optional"], edgecolor="#243038", label="Lokalni dodatni vir"),
    ]
    fig.legend(handles=legend_items, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.01))
    fig.suptitle(
        "Prispevek okoljskih dejavnikov in virov\nPozitivni stolpci pomenijo večjo uporabnost sklopa v razvojni validaciji",
        fontsize=16.5,
        fontweight="bold",
        x=0.05,
        y=1.03,
        ha="left",
    )

    fig.savefig(ALL_GROUPS_PNG, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(ALL_GROUPS_SVG, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def build_local_groups_figure(df: pd.DataFrame) -> None:
    local_df = df[df["group_class"] == "local_optional"].copy()
    max_groups = max(local_df[local_df["target_name"] == target_name].shape[0] for target_name in TARGET_ORDER)
    fig_height = max(8.7, 2.8 + len(TARGET_ORDER) * max_groups * 0.46)
    fig, axes = plt.subplots(nrows=len(TARGET_ORDER), ncols=1, figsize=(13, fig_height), constrained_layout=True)
    fig.patch.set_facecolor("#F3EBDD")

    if len(TARGET_ORDER) == 1:
        axes = [axes]

    for ax, target_name in zip(axes, TARGET_ORDER):
        subset = local_df[local_df["target_name"] == target_name].copy().sort_values("mean_rmse_effect_vs_reference")
        values = subset["mean_rmse_effect_vs_reference"].tolist()
        colors = [GROUP_CLASS_COLORS.get(value, "#6B7A84") for value in subset["group_class"]]
        ax.barh(subset["group_label"], subset["mean_rmse_effect_vs_reference"], color=colors, edgecolor="#2C3439", linewidth=0.5)
        style_axis(ax, f"{TARGET_SHORT_LABELS[target_name]}: samo lokalni viri")
        set_x_margin(ax, values, right_extra=2.1)

        max_abs = max(abs(subset["mean_rmse_effect_vs_reference"].min()), abs(subset["mean_rmse_effect_vs_reference"].max()))
        bubble_x = max_abs * 0.88 if max_abs > 0 else 0.05
        ax.scatter(
            [bubble_x] * len(subset),
            range(len(subset)),
            s=subset["mean_group_validation_coverage_pct"] * 8 + 30,
            color="#D7A03C",
            edgecolors="#243038",
            linewidths=0.6,
            alpha=0.75,
            zorder=3,
        )
        for idx, row in subset.reset_index(drop=True).iterrows():
            ax.text(
                bubble_x + max_abs * 0.05,
                idx,
                f"{row['mean_group_validation_coverage_pct']:.1f}% pokr. | {row['helpful_folds_pct']:.0f}% koristna leta",
                va="center",
                ha="left",
                fontsize=8.5,
                color="#243038",
            )

    legend_items = [
        Patch(facecolor=GROUP_CLASS_COLORS["local_optional"], edgecolor="#243038", label="Lokalni vir"),
        Line2D([0], [0], marker="o", color="w", label="Velikost kroga = validacijska pokritost", markerfacecolor="#D7A03C", markeredgecolor="#243038", markersize=10),
    ]
    fig.legend(handles=legend_items, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle(
        "Prispevek lokalnih virov podatkov\nPozitivni stolpci pomenijo, da lokalni vir izboljša referenčni okoljski model",
        fontsize=15.8,
        fontweight="bold",
        x=0.05,
        y=1.04,
        ha="left",
    )

    fig.savefig(LOCAL_GROUPS_PNG, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(LOCAL_GROUPS_SVG, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def build_commentary(df: pd.DataFrame, manifest_df: pd.DataFrame) -> str:
    hidden_labels = load_hidden_group_labels(manifest_df)
    lines = [
        "# Razlaga okoljskih grafov",
        "",
        "Ta zapis razlaga grafe okoljske primerjave za `okoljski_raziskovalni_model`.",
        "",
        "## Kako brati grafe",
        "",
        "- pozitivni stolpci so ugodni",
        "- jedrni sklopi so ocenjeni tako, da jih iz referenčnega okoljskega modela odstranimo",
        "- lokalni sklopi so ocenjeni tako, da jih referenčnemu okoljskemu modelu dodamo",
        "- pokritost je pomembna, ker lahko lokalni vir pomaga le na delu panela",
        "- delež koristnih let pokaže, kako stabilen je signal med razvojnimi leti",
        "",
    ]

    if hidden_labels:
        lines.extend(
            [
                "## Skriti sezonski nadzor",
                "",
                f"- uporabljeni skriti nadzorni sklopi: {', '.join(f'`{label}`' for label in hidden_labels)}",
                "- ta nadzor absorbira široko letno časovno fazo, zato izmerjeni sklopi bolje odražajo okoljski signal in ne le koledarskega položaja",
                "",
            ]
        )

    for target_name in TARGET_ORDER:
        subset = df[df["target_name"] == target_name].copy().sort_values("target_group_rank")
        top_overall = subset.iloc[0]
        core_subset = subset[subset["group_class"] == "core"].copy()
        local_subset = subset[subset["group_class"] == "local_optional"].copy()
        positive_local_subset = local_subset[local_subset["mean_rmse_effect_vs_reference"] > 0].copy()
        top_local = local_subset.iloc[0] if not local_subset.empty else None
        top_two = subset.head(2)
        negative_core_subset = core_subset[core_subset["mean_rmse_effect_vs_reference"] < 0].copy()
        lines.extend(
            [
                f"## {TARGET_SHORT_LABELS[target_name]}",
                "",
                f"- najmočnejši sklop: `{top_overall['group_label']}` z učinkom RMSE `{top_overall['mean_rmse_effect_vs_reference']:.6f}`",
                f"- drugo mesto: `{top_two.iloc[1]['group_label']}` z učinkom RMSE `{top_two.iloc[1]['mean_rmse_effect_vs_reference']:.6f}`",
            ]
        )

        if local_subset.empty:
            lines.append("- v tej izvedbi ni bilo ocenjenih lokalnih sklopov za ta cilj")
        elif positive_local_subset.empty:
            lines.append("- noben lokalni vir za ta cilj ni v povprečju izboljšal referenčnega okoljskega modela")
        else:
            best_positive_local = positive_local_subset.sort_values(
                "mean_rmse_effect_vs_reference", ascending=False
            ).iloc[0]
            lines.append(
                f"- najboljši pozitivni lokalni vir: `{best_positive_local['group_label']}` "
                f"(učinek `{best_positive_local['mean_rmse_effect_vs_reference']:.6f}`, "
                f"pokritost `{best_positive_local['mean_group_validation_coverage_pct']:.4f}%`, "
                f"koristna leta `{best_positive_local['helpful_folds_pct']:.1f}%`)"
            )
        if top_local is not None:
            lines.append(
                f"- najvišje uvrščeni lokalni vir: `{top_local['group_label']}` "
                f"(učinek `{top_local['mean_rmse_effect_vs_reference']:.6f}`, "
                f"pokritost `{top_local['mean_group_validation_coverage_pct']:.4f}%`, "
                f"koristna leta `{top_local['helpful_folds_pct']:.1f}%`)"
            )

        lines.extend(
            [
                "",
                "Razlaga:",
                "",
                f"- sklop `{top_overall['group_label']}` nosi največ dodatne razlagalne vrednosti za ta cilj",
                f"- sklop `{top_two.iloc[1]['group_label']}` pomaga oceniti, ali je signal skoncentriran v enem bloku ali razporejen med več družin dejavnikov",
            ]
        )
        if top_local is not None:
            lines.append(
                f"- lokalni vir `{top_local['group_label']}` je treba vedno brati skupaj s pokritostjo in deležem koristnih let"
            )

        if not negative_core_subset.empty:
            negative_core_labels = ", ".join(f"`{label}`" for label in negative_core_subset["group_label"].tolist())
            lines.extend(
                [
                    "",
                    "Pozor:",
                    "",
                    f"- negativni rezultati jedrnih sklopov {negative_core_labels} bolj verjetno pomenijo redundanco ali prekrivanje z močnejšimi bloki kot pa biološko nepomembnost",
                    "",
                ]
            )

    lines.extend(
        [
            "## Datoteke",
            "",
            f"- `{ALL_GROUPS_PNG.name}` in `{ALL_GROUPS_SVG.name}` prikazujeta vse okoljske sklope",
            f"- `{LOCAL_GROUPS_PNG.name}` in `{LOCAL_GROUPS_SVG.name}` prikazujeta samo lokalne vire",
            f"- `{HTML_REPORT_PATH.name}` je samostojen HTML izvoz za predstavitve",
        ]
    )
    return "\n".join(lines)


def effect_badge_class(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def format_effect(value: float) -> str:
    return f"{value:+.4f}"


def format_pct(value: float) -> str:
    return f"{value:.1f}%"


def best_local_summary(subset: pd.DataFrame) -> tuple[str, str]:
    local_subset = subset[subset["group_class"] == "local_optional"].copy()
    if local_subset.empty:
        return "Ni lokalnega sklopa", "V tej izvedbi za ta cilj ni ločeno ocenjenega lokalnega dodatnega vira."

    positive_local_subset = local_subset[local_subset["mean_rmse_effect_vs_reference"] > 0].copy()
    if positive_local_subset.empty:
        top_local = local_subset.sort_values("target_group_rank").iloc[0]
        return (
            str(top_local["group_label"]),
            (
                "Najvišje uvrščeni lokalni vir ni bil pozitiven. "
                f"Učinek {format_effect(float(top_local['mean_rmse_effect_vs_reference']))}, "
                f"pokritost {format_pct(float(top_local['mean_group_validation_coverage_pct']))}."
            ),
        )

    top_local = positive_local_subset.sort_values("mean_rmse_effect_vs_reference", ascending=False).iloc[0]
    return (
        str(top_local["group_label"]),
        (
            f"Najboljši pozitivni lokalni vir z učinkom {format_effect(float(top_local['mean_rmse_effect_vs_reference']))}, "
            f"pokritostjo {format_pct(float(top_local['mean_group_validation_coverage_pct']))} "
            f"in deležem koristnih let {format_pct(float(top_local['helpful_folds_pct']))}."
        ),
    )


def render_summary_cards(df: pd.DataFrame) -> str:
    cards: list[str] = []
    for target_name in TARGET_ORDER:
        subset = df[df["target_name"] == target_name].copy().sort_values("target_group_rank")
        top_row = subset.iloc[0]
        runner_up = subset.iloc[1]
        local_title, local_summary = best_local_summary(subset)
        badge_class = effect_badge_class(float(top_row["mean_rmse_effect_vs_reference"]))
        cards.append(
            f"""
            <article class="summary-card">
              <div class="card-topline">{escape(TARGET_SHORT_LABELS[target_name])}</div>
              <h3>{escape(str(top_row["group_label"]))}</h3>
              <div class="metric-row">
                <span class="badge {badge_class}">{escape(format_effect(float(top_row["mean_rmse_effect_vs_reference"])))}</span>
                <span class="meta-chip">koristna leta {escape(format_pct(float(top_row["helpful_folds_pct"])))}</span>
                <span class="meta-chip">pokritost {escape(format_pct(float(top_row["mean_group_validation_coverage_pct"])))}</span>
              </div>
              <p class="lead">Najmočnejši sklop za ta cilj v razvojni validaciji.</p>
              <p><strong>2. mesto:</strong> {escape(str(runner_up["group_label"]))} ({escape(format_effect(float(runner_up["mean_rmse_effect_vs_reference"])))})</p>
              <p><strong>Lokalni vrh:</strong> {escape(local_title)}</p>
              <p class="supporting-copy">{escape(local_summary)}</p>
            </article>
            """
        )
    return "\n".join(cards)


def render_signal_table(df: pd.DataFrame) -> str:
    rows: list[str] = []
    for target_name in TARGET_ORDER:
        subset = df[df["target_name"] == target_name].copy().sort_values("target_group_rank").head(5)
        for _, row in subset.iterrows():
            badge_class = effect_badge_class(float(row["mean_rmse_effect_vs_reference"]))
            rows.append(
                f"""
                <tr>
                  <td>{escape(TARGET_SHORT_LABELS[target_name])}</td>
                  <td>{int(row["target_group_rank"])}</td>
                  <td>{escape(str(row["group_label"]))}</td>
                  <td>{escape(GROUP_CLASS_LABELS.get(str(row["group_class"]), str(row["group_class"])))}</td>
                  <td><span class="table-badge {badge_class}">{escape(format_effect(float(row["mean_rmse_effect_vs_reference"])))}</span></td>
                  <td>{escape(format_pct(float(row["helpful_folds_pct"])))}</td>
                  <td>{escape(format_pct(float(row["mean_group_validation_coverage_pct"])))}</td>
                </tr>
                """
            )
    return "\n".join(rows)


def render_analysis_sections(df: pd.DataFrame) -> str:
    sections: list[str] = []
    for target_name in TARGET_ORDER:
        subset = df[df["target_name"] == target_name].copy().sort_values("target_group_rank")
        top_row = subset.iloc[0]
        runner_up = subset.iloc[1]
        local_title, local_summary = best_local_summary(subset)
        negative_cores = subset[
            (subset["group_class"] == "core") & (subset["mean_rmse_effect_vs_reference"] < 0)
        ]["group_label"].tolist()
        caution_text = (
            "Negativni jedrni sklopi v tem cilju bolj verjetno kažejo na redundanco ali prekrivanje med dejavniki kot pa na dejansko nepomembnost mehanizma."
            if negative_cores
            else "V ospredju so predvsem pozitivni in stabilni jedrni signali."
        )
        sections.append(
            f"""
            <article class="analysis-card">
              <div class="analysis-kicker">{escape(TARGET_SHORT_LABELS[target_name])}</div>
              <h3>{escape(str(top_row["group_label"]))}</h3>
              <p>Najmočnejši sklop ima učinek <strong>{escape(format_effect(float(top_row["mean_rmse_effect_vs_reference"])))}</strong> in pomeni, da je njegov prispevek za ta cilj bolj uporaben od preostalih ocenjenih sklopov.</p>
              <p>Drugo mesto zaseda <strong>{escape(str(runner_up["group_label"]))}</strong>, kar pomaga razumeti, ali je signal skoncentriran ali razdeljen med več okoljskih blokov.</p>
              <p><strong>Lokalni vir:</strong> {escape(local_title)}. {escape(local_summary)}</p>
              <p class="analysis-note">{escape(caution_text)}</p>
            </article>
            """
        )
    return "\n".join(sections)


def read_svg_markup(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    cleaned = [line for line in lines if not line.startswith("<?xml") and not line.startswith("<!DOCTYPE")]
    return "\n".join(cleaned)


def write_html_report(df: pd.DataFrame, manifest_df: pd.DataFrame) -> None:
    hidden_labels = load_hidden_group_labels(manifest_df)
    all_svg_markup = read_svg_markup(ALL_GROUPS_SVG)
    local_svg_markup = read_svg_markup(LOCAL_GROUPS_SVG)
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    hidden_text = ", ".join(hidden_labels) if hidden_labels else "Skriti sezonski nadzor ni zaznan v manifestu."
    total_groups = int(df["group_name"].nunique())
    core_groups = int(df[df["group_class"] == "core"]["group_name"].nunique())
    local_groups = int(df[df["group_class"] == "local_optional"]["group_name"].nunique())

    html_text = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Okoljski grafi | okoljski_raziskovalni_model</title>
  <style>
    :root {{
      --bg: #f6f0e4; --bg2: #eadfc9; --panel: rgba(255,252,246,.84); --ink: #1f2b2d; --muted: #5c686b;
      --line: rgba(60,79,84,.14); --teal: #295C6A; --ochre: #B06C2B; --good: #2f6c58; --bad: #9e4d37; --mid: #7e7159;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: var(--ink); font-family: "Palatino Linotype", Georgia, serif;
      background: radial-gradient(circle at top right, rgba(176,108,43,.18), transparent 28%),
                  radial-gradient(circle at left top, rgba(41,92,106,.14), transparent 30%),
                  linear-gradient(180deg, var(--bg) 0%, var(--bg2) 55%, #faf6ee 100%); }}
    .page {{ max-width: 1440px; margin: 0 auto; padding: 40px 24px 72px; }}
    .hero, .panel, .summary-card, .analysis-card {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 26px; box-shadow: 0 18px 44px rgba(52,50,42,.12);
      backdrop-filter: blur(10px);
    }}
    .hero {{ padding: 34px; margin-bottom: 22px; position: relative; overflow: hidden; }}
    .hero::after {{ content: ""; position: absolute; right: -70px; top: -90px; width: 240px; height: 240px; border-radius: 50%;
      background: radial-gradient(circle, rgba(176,108,43,.26), rgba(176,108,43,.02) 72%); }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: .18em; color: var(--teal); font-size: .84rem; font-weight: 700; margin-bottom: 10px; }}
    h1 {{ margin: 0; max-width: 920px; font-size: clamp(2.1rem, 3vw, 3.5rem); line-height: .98; }}
    .hero p, .panel p, .analysis-card p {{ color: var(--muted); line-height: 1.62; }}
    .hero-meta, .card-grid, .analysis-grid {{ display: grid; gap: 16px; }}
    .hero-meta {{ grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); margin-top: 24px; }}
    .card-grid, .analysis-grid {{ grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
    .meta-box {{ padding: 16px 18px; border-radius: 18px; border: 1px solid var(--line); background: rgba(255,255,255,.42); }}
    .meta-label {{ display: block; text-transform: uppercase; letter-spacing: .12em; color: var(--muted); font-size: .8rem; margin-bottom: 6px; }}
    .meta-value {{ font-size: 1.28rem; font-weight: 700; }}
    .section {{ display: grid; gap: 22px; margin-top: 22px; }}
    .summary-card, .analysis-card, .panel {{ padding: 22px; }}
    .card-topline, .analysis-kicker {{ text-transform: uppercase; letter-spacing: .12em; color: var(--ochre); font-size: .78rem; font-weight: 700; }}
    .summary-card h3, .analysis-card h3 {{ margin: 10px 0 12px; font-size: 1.5rem; line-height: 1.08; }}
    .metric-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
    .badge, .meta-chip, .table-badge {{ display: inline-flex; align-items: center; padding: 6px 10px; border-radius: 999px; font-size: .86rem; font-weight: 700; }}
    .meta-chip {{ background: rgba(41,92,106,.08); color: var(--teal); }}
    .positive {{ background: rgba(47,108,88,.12); color: var(--good); }}
    .negative {{ background: rgba(158,77,55,.12); color: var(--bad); }}
    .neutral {{ background: rgba(126,113,89,.14); color: var(--mid); }}
    .panel h2 {{ margin: 0; font-size: 1.72rem; }}
    .panel-header {{ margin-bottom: 16px; }}
    .chart-shell {{ overflow-x: auto; border-radius: 22px; background: linear-gradient(180deg, rgba(255,255,255,.62), rgba(246,240,228,.82)); border: 1px solid rgba(56,70,72,.09); padding: 16px; }}
    .chart-shell svg {{ width: 100%; height: auto; display: block; }}
    .two-col {{ display: grid; grid-template-columns: 1.08fr .92fr; gap: 22px; }}
    .notes-list {{ margin: 0; padding-left: 18px; color: var(--muted); line-height: 1.7; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .95rem; }}
    th, td {{ text-align: left; padding: 12px 10px; border-bottom: 1px solid rgba(70,84,87,.12); vertical-align: top; }}
    th {{ text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-size: .8rem; }}
    .analysis-note {{ border-top: 1px solid rgba(56,70,72,.12); padding-top: 12px; }}
    @media (max-width: 1024px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 720px) {{ .page {{ padding: 24px 14px 52px; }} .hero, .panel, .summary-card, .analysis-card {{ padding: 18px; }} }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">okoljski_raziskovalni_model</div>
      <h1>Okoljski pregled dejavnikov za KME in boreliozo</h1>
      <p>Ta HTML izvoz povzema, kateri okoljski sklopi in lokalni viri podatkov največ prispevajo k razlagi trenutnega bremena KME, lymske borelioze in skupnega bremena klopnih bolezni. Grafi spodaj uporabljajo isto reproducibilno pipeline stopnjo kot shranjeni PNG in SVG izhodi.</p>
      <div class="hero-meta">
        <div class="meta-box"><span class="meta-label">Cilji</span><span class="meta-value">{len(TARGET_ORDER)}</span></div>
        <div class="meta-box"><span class="meta-label">Ocenjeni sklopi</span><span class="meta-value">{total_groups}</span></div>
        <div class="meta-box"><span class="meta-label">Jedrni sklopi</span><span class="meta-value">{core_groups}</span></div>
        <div class="meta-box"><span class="meta-label">Lokalni viri</span><span class="meta-value">{local_groups}</span></div>
        <div class="meta-box"><span class="meta-label">Razvojna leta</span><span class="meta-value">2021-2024</span></div>
        <div class="meta-box"><span class="meta-label">Izvoz ustvarjen</span><span class="meta-value">{escape(generated_at)}</span></div>
      </div>
    </section>

    <section class="section">
      <div class="card-grid">
        {render_summary_cards(df)}
      </div>
    </section>

    <section class="section">
      <section class="panel">
        <div class="panel-header">
          <h2>Vsi ocenjeni okoljski sklopi</h2>
          <p>Jedrni sklopi so ocenjeni z odstranitvijo iz referenčnega modela. Lokalni sklopi so ocenjeni kot dodatek k referenčnemu okoljskemu jedru. Pozitivne vrednosti pomenijo večjo uporabnost.</p>
        </div>
        <div class="chart-shell">{all_svg_markup}</div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2>Lokalni viri podatkov</h2>
          <p>Ta pogled izpostavi samo lokalne vire. Velikost kroga prikazuje validacijsko pokritost, zato je mogoče hitro ločiti močan signal od delnega ali zelo omejenega vira.</p>
        </div>
        <div class="chart-shell">{local_svg_markup}</div>
      </section>
    </section>

    <section class="section two-col">
      <section class="panel">
        <div class="panel-header">
          <h2>Kako brati graf</h2>
          <p>Ta povzetek pomaga pri razlagi grafov na predstavitvi brez potrebe po odpiranju dodatnih metodoloških datotek.</p>
        </div>
        <ul class="notes-list">
          <li>Pozitivna vrednost pomeni, da je sklop za model koristen.</li>
          <li>Pri jedrnih sklopih pozitiven rezultat pomeni, da odstranitev sklopa modelu škodi.</li>
          <li>Pri lokalnih sklopih pozitiven rezultat pomeni, da dodatek vira model izboljša.</li>
          <li>Pokritost pove, na kolikšnem delu panela je vir sploh prisoten.</li>
          <li>Delež koristnih let kaže stabilnost med razvojnimi validacijskimi leti.</li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2>Skriti sezonski nadzor</h2>
          <p>Sezonski nadzor ostaja prisoten v ozadju, da ocenjeni sklopi ne bi le ponavljali koledarskega cikla bolezni.</p>
        </div>
        <p><strong>Uporabljeni nadzorni sklop:</strong> {escape(hidden_text)}</p>
        <p>To pomeni, da je del širokega sezonskega ritma že zajet v modelu, zato grafi bolj pošteno izpostavijo dejanske okoljske prispevke, kot so raba tal, padavine ali vlažnost.</p>
      </section>
    </section>

    <section class="section">
      <section class="panel">
        <div class="panel-header">
          <h2>Najmočnejši signali po cilju</h2>
          <p>Spodnja tabela prikazuje prvih pet sklopov za vsak cilj glede na razvojno primerjavo z referenčnim okoljskim modelom.</p>
        </div>
        <div class="chart-shell">
          <table>
            <thead>
              <tr>
                <th>Cilj</th><th>Rang</th><th>Sklop</th><th>Razred</th><th>Učinek RMSE</th><th>Koristna leta</th><th>Pokritost</th>
              </tr>
            </thead>
            <tbody>{render_signal_table(df)}</tbody>
          </table>
        </div>
      </section>
    </section>

    <section class="section">
      <section class="panel">
        <div class="panel-header">
          <h2>Kratka razlaga po ciljih</h2>
          <p>Besedilni povzetek je pripravljen tako, da ga lahko neposredno uporabiš v predstavitvi ali razpravi.</p>
        </div>
        <div class="analysis-grid">{render_analysis_sections(df)}</div>
      </section>
    </section>
  </main>
</body>
</html>
"""
    HTML_REPORT_PATH.write_text(html_text, encoding="utf-8")


def update_living_readme(df: pd.DataFrame) -> None:
    if not LIVING_README_PATH.exists():
        return

    sections = [
        "",
        "## Environmental Graph Stage",
        "",
        "okoljski_raziskovalni_model now has graph outputs for presentation and interpretation.",
        "",
        "New script:",
        "",
        "- `scripts/build_environment_graphs.py`",
        "",
        "New graph outputs in `data/processed/model_grouped_evaluation/`:",
        "",
        f"- `{ALL_GROUPS_PNG.name}`",
        f"- `{ALL_GROUPS_SVG.name}`",
        f"- `{LOCAL_GROUPS_PNG.name}`",
        f"- `{LOCAL_GROUPS_SVG.name}`",
        f"- `{COMMENTARY_PATH.name}`",
        f"- `{HTML_REPORT_PATH.name}`",
    ]

    for target_name in TARGET_ORDER:
        best_row = df[df["target_name"] == target_name].sort_values("target_group_rank").iloc[0]
        sections.extend(
            [
                "",
                f"- Graph headline for `{target_name}`: `{best_row['group_label']}` ranked first",
                f"  - mean RMSE effect: `{best_row['mean_rmse_effect_vs_reference']:.6f}`",
                f"  - helpful-fold rate: `{best_row['helpful_folds_pct']:.1f}`%",
                f"  - mean coverage: `{best_row['mean_group_validation_coverage_pct']:.4f}`%",
            ]
        )

    existing = LIVING_README_PATH.read_text(encoding="utf-8")
    marker = "\n## Environmental Graph Stage\n"
    if marker in existing:
        existing = existing.split(marker)[0].rstrip()
    updated = existing.rstrip() + "\n" + "\n".join(sections) + "\n"
    LIVING_README_PATH.write_text(updated, encoding="utf-8")


def main() -> None:
    df = load_scores()
    manifest_df = load_group_manifest()

    build_all_groups_figure(df)
    build_local_groups_figure(df)

    commentary_text = build_commentary(df, manifest_df)
    COMMENTARY_PATH.write_text(commentary_text, encoding="utf-8")
    write_html_report(df, manifest_df)
    update_living_readme(df)

    run_summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": str(Path(__file__).resolve()),
        "input_group_scores": str(GROUP_SCORE_PATH.resolve()),
        "input_group_manifest": str(GROUP_MANIFEST_PATH.resolve()),
        "output_files": [
            ALL_GROUPS_PNG.name,
            ALL_GROUPS_SVG.name,
            LOCAL_GROUPS_PNG.name,
            LOCAL_GROUPS_SVG.name,
            COMMENTARY_PATH.name,
            HTML_REPORT_PATH.name,
            RUN_SUMMARY_PATH.name,
        ],
    }
    RUN_SUMMARY_PATH.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    print("Environmental graphs written to:")
    print(ALL_GROUPS_PNG)
    print(ALL_GROUPS_SVG)
    print(LOCAL_GROUPS_PNG)
    print(LOCAL_GROUPS_SVG)
    print(COMMENTARY_PATH)
    print(HTML_REPORT_PATH)
    print(RUN_SUMMARY_PATH)


if __name__ == "__main__":
    main()
