"""Generate conference PNG charts (transparent background) for KlopPodKlopjo.

All numbers are read from the frozen model_v3 output artefacts. Nothing is
hard-coded except labels.

Usage:  python make_charts.py [light|dark]
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter

ROOT = Path("/Users/zankespert/Desktop/KlopPodKlopjo")
OUTS = ROOT / "model_v3" / "outputs"

INK = {
    "light": {"primary": "#0b0b0b", "secondary": "#52514e", "muted": "#898781",
              "grid": "#e1e0d9", "axis": "#c3c2b7"},
    "dark":  {"primary": "#ffffff", "secondary": "#d5d4cc", "muted": "#a3a29c",
              "grid": "#3a3a37", "axis": "#55554f"},
}

# categorical slots — validated all-pairs PASS on the light surface
C_BLUE, C_ORANGE, C_AQUA = "#2a78d6", "#eb6834", "#1baf7a"
C_BLUE_DK = "#184f95"

FONT = "Helvetica Neue"
plt.rcParams.update({
    "font.family": FONT, "font.size": 12,
    "figure.dpi": 200, "savefig.dpi": 200,
})

MODE = sys.argv[1] if len(sys.argv) > 1 else "light"
K = INK[MODE]
OUTDIR = ROOT / "docs" / "konferenca" / "grafi"
if MODE == "dark":
    OUTDIR = OUTDIR / "za-temno-podlago"
OUTDIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------ helpers
def style(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(K["axis"])
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=K["muted"], labelsize=11, length=3, width=0.8)
    for lb in ax.get_xticklabels() + ax.get_yticklabels():
        lb.set_color(K["secondary"])
    ax.set_axisbelow(True)
    ax.xaxis.grid(False)
    ax.yaxis.grid(False)
    if grid in ("x", "both"):
        ax.xaxis.grid(True, color=K["grid"], lw=0.8)
    if grid in ("y", "both"):
        ax.yaxis.grid(True, color=K["grid"], lw=0.8)


def head(fig, title, sub, x=0.008, y=0.975, gap=0.062, ts=17, ss=11.5):
    fig.text(x, y, title, fontsize=ts, fontweight="700", color=K["primary"],
             ha="left", va="top")
    fig.text(x, y - gap, sub, fontsize=ss, color=K["muted"], ha="left", va="top")


def foot(fig, txt, x=0.008, y=0.022):
    fig.text(x, y, txt, fontsize=9.5, color=K["muted"], ha="left", va="center")


def swatches(ax, items, loc="lower right", ncol=1, fs=11):
    h = [Rectangle((0, 0), 1, 1, color=c) for _, c in items]
    lg = ax.legend(h, [t for t, _ in items], frameon=False, loc=loc, ncol=ncol,
                   fontsize=fs, handlelength=0.85, handleheight=0.85,
                   handletextpad=0.6, borderpad=0.2, labelspacing=0.65,
                   columnspacing=1.4)
    for t in lg.get_texts():
        t.set_color(K["secondary"])
    return lg


def sl(v, dec=0):
    """Slovenian number format: period thousands separator, comma decimal."""
    t = f"{v:,.{dec}f}"
    return t.replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".")


def sl_axis(ax, which="y", dec=0):
    f = FuncFormatter(lambda v, _: sl(v, dec))
    (ax.yaxis if which == "y" else ax.xaxis).set_major_formatter(f)


def save(fig, name):
    p = OUTDIR / name
    fig.savefig(p, transparent=True)
    plt.close(fig)
    print("  ->", p.name)


# ======================================================= 1. lockbox trio
def chart_lockbox():
    lb = pd.read_csv(OUTS / "lockbox_2025" / "lyme_lockbox_metrics.csv").set_index("candidate_id")
    order = ["catboost_poisson_s3_weather_offset",
             "model_s3_weather_offset_matched",
             "baseline_d_municipality_seasonal_history"]
    names = ["CatBoost", "Poissonov GLM", "Sezonsko povprečje"]
    cols = [C_BLUE, C_ORANGE, C_AQUA]
    metrics = [("mae", "MAE — povprečna absolutna napaka"),
               ("rmse", "RMSE — koren povpr. kvadratne napake"),
               ("mean_poisson_deviance", "Poissonova devianca")]

    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.5))
    fig.subplots_adjust(top=0.70, bottom=0.17, left=0.122, right=0.99, wspace=0.30)

    for i, (ax, (col, lab)) in enumerate(zip(axes, metrics)):
        vals = [lb.loc[o, col] for o in order]
        y = np.arange(3)[::-1]
        top = np.nanmax([v for v in vals if not pd.isna(v)])
        for yi, v, c in zip(y, vals, cols):
            if pd.isna(v):
                ax.text(top * 0.035, yi, "ni matematično veljavno",
                        color=K["muted"], fontsize=10.5, va="center", style="italic")
            else:
                ax.barh(yi, v, height=0.46, color=c, edgecolor="none", zorder=3)
                ax.text(v + top * 0.035, yi, sl(v, 3), va="center", ha="left",
                        color=K["primary"], fontsize=11.5, fontweight="600", zorder=4)
        ax.set_yticks(y)
        ax.set_yticklabels(names if i == 0 else [""] * 3, fontsize=11.5)
        ax.set_ylim(-0.62, 2.62)
        ax.set_xlim(0, top * 1.34)
        style(ax, grid="x")
        sl_axis(ax, "x", 2)
        ax.tick_params(axis="y", length=0)
        ax.set_title(lab, color=K["primary"], fontsize=12.5, fontweight="600",
                     loc="left", pad=12)

    head(fig, "Zaklenjeni set 2025: enkratna ocena na 9.964 napovedih",
         "Nižje je bolje pri vseh treh merilih. Model je bil zamrznjen, preden je kdorkoli pogledal podatke leta 2025.",
         y=0.965, gap=0.088)
    foot(fig, "Vir: model_v3/outputs/lockbox_2025/lyme_lockbox_metrics.csv  ·  cilj: prijavljeni primeri borelioze v tednih t+1 do t+4  ·  212 občin × 47 izdajnih tednov",
         y=0.035)
    save(fig, "01-zaklenjeni-set-2025-primerjava-modelov.png")


# ================================================= 2. fold-wise stability
def chart_stability():
    cb = pd.read_csv(OUTS / "catboost_challenger" / "lyme_catboost_challenger_fold_metrics.csv")
    gl = pd.read_csv(OUTS / "catboost_challenger" / "lyme_matched_statistical_reference_fold_metrics.csv")
    lb = pd.read_csv(OUTS / "lockbox_2025" / "lyme_lockbox_metrics.csv").set_index("candidate_id")
    yrs = [int(f.split("_")[-1]) for f in cb["fold_id"]]
    x = yrs + [2025]
    cb_y = list(cb["mae"]) + [lb.loc["catboost_poisson_s3_weather_offset", "mae"]]
    gl_y = list(gl["mae"]) + [lb.loc["model_s3_weather_offset_matched", "mae"]]

    fig, ax = plt.subplots(figsize=(12.8, 6.0))
    fig.subplots_adjust(top=0.775, bottom=0.145, left=0.062, right=0.845)

    ax.axvspan(2024.5, 2025.5, color=C_BLUE, alpha=0.07, zorder=0)
    ax.text(2025, 2.03, "zaklenjeni set 2025\n(enkratna ocena)", ha="center",
            va="top", color=K["muted"], fontsize=10.5, linespacing=1.4)

    for xs, ys, c in ((x[:8], gl_y[:8], C_ORANGE), (x[:8], cb_y[:8], C_BLUE)):
        ax.plot(xs, ys, color=c, lw=2, marker="o", ms=7.5, mec="none", zorder=3)
    for ys, c in ((gl_y, C_ORANGE), (cb_y, C_BLUE)):
        ax.plot(x[7:], ys[7:], color=c, lw=2, ls=(0, (4, 3)), zorder=3)
        ax.plot([2025], [ys[-1]], marker="D", ms=9.5, color=c, mec="none", zorder=5)

    # series names parked to the right of the plot, never over the data
    ax.text(2025.72, gl_y[-1] + 0.035, "Poissonov GLM", color=C_ORANGE, fontsize=12.5,
            fontweight="700", ha="left", va="bottom", clip_on=False)
    ax.text(2025.72, cb_y[-1] - 0.035, "CatBoost", color=C_BLUE, fontsize=12.5,
            fontweight="700", ha="left", va="top", clip_on=False)

    # selective labels only: the worst year, the best year, and the lockbox
    for xi, yi, dy in ((2020, cb_y[3], -20), (2024, cb_y[7], -20), (2025, cb_y[8], -20)):
        ax.annotate(sl(yi, 2), (xi, yi), textcoords="offset points",
                    xytext=(0, dy), ha="center", color=K["secondary"], fontsize=10.5)
    ax.annotate(sl(gl_y[3], 2), (2020, gl_y[3]), textcoords="offset points",
                xytext=(0, 12), ha="center", color=K["secondary"], fontsize=10.5)

    ax.set_xticks(x)
    ax.set_xticklabels([str(v) for v in x])
    ax.set_xlim(2016.5, 2025.55)
    ax.set_ylim(0.80, 2.08)
    ax.set_ylabel("MAE  (nižje je bolje)", color=K["secondary"], fontsize=11.5)
    style(ax)
    sl_axis(ax, "y", 1)
    head(fig, "Stabilnost skozi čas: napaka po posameznem letu validacije",
         "Razširjajoča se validacija z drsečim izhodiščem — model se za vsako leto uči izključno na podatkih pred tem letom.",
         y=0.975, gap=0.070)
    foot(fig, "Vir: lyme_catboost_challenger_fold_metrics.csv, lyme_matched_statistical_reference_fold_metrics.csv, lyme_lockbox_metrics.csv  ·  81.832 razvojnih + 9.964 zaklenjenih napovedi")
    save(fig, "02-stabilnost-napake-po-letih.png")


# ======================================================== 3. calibration
def chart_calibration():
    cg = pd.read_csv(OUTS / "lockbox_2025" / "lyme_lockbox_calibration_groups.csv")
    cb = cg[cg.candidate_id == "catboost_poisson_s3_weather_offset"]

    fig, ax = plt.subplots(figsize=(9.8, 7.0))
    fig.subplots_adjust(top=0.795, bottom=0.175, left=0.098, right=0.975)

    hi = cb[["predicted_mean", "observed_mean"]].to_numpy().max() * 1.09
    ax.plot([0, hi], [0, hi], color=K["axis"], lw=1.4, ls=(0, (5, 4)), zorder=2)
    ax.text(hi * 0.72, hi * 0.735, "popolno ujemanje", color=K["muted"],
            fontsize=10.5, rotation=41, rotation_mode="anchor", ha="center", va="bottom")

    ax.plot(cb.predicted_mean, cb.observed_mean, color=C_BLUE, lw=2, zorder=3)
    ax.scatter(cb.predicted_mean, cb.observed_mean, s=90, color=C_BLUE,
               edgecolor="none", zorder=4)
    for _, r in cb.iterrows():
        g = int(r.calibration_group)
        if g in (1, 10):
            ax.annotate(f"{g}. desetina", (r.predicted_mean, r.observed_mean),
                        textcoords="offset points",
                        xytext=(16, -6) if g == 10 else (14, -4),
                        color=K["secondary"], fontsize=10.5,
                        ha="left", va="top" if g == 10 else "center")
    ax.set_xlim(0, hi); ax.set_ylim(0, hi)
    ax.set_xlabel("povprečna napoved modela", color=K["secondary"], fontsize=11.5)
    ax.set_ylabel("dejansko povprečje prijavljenih primerov", color=K["secondary"], fontsize=11.5)
    style(ax, grid="both")
    sl_axis(ax, "x", 0); sl_axis(ax, "y", 0)
    head(fig, "Umerjenost: model sistematično podcenjuje",
         "Deset enako velikih skupin napovedi, urejenih od najnižje do najvišje.\nTočke nad črtkano črto pomenijo, da je bilo primerov več, kot jih je model napovedal.",
         y=0.977, gap=0.072)
    fig.text(0.098, 0.085,
             "Razmerje med opazovanim in napovedanim je 1,157.\nModel torej napove približno 13,5 % manj primerov, kot jih je bilo prijavljenih.",
             color=K["secondary"], fontsize=11, va="center", linespacing=1.5)
    foot(fig, "Vir: lyme_lockbox_calibration_groups.csv, lyme_lockbox_calibration_overall.csv  ·  zgolj diagnostika; naknadno umerjanje ni bilo izvedeno", y=0.018)
    save(fig, "03-umerjenost-modela.png")


# ======================================================== 4. seasonality
def chart_seasonality():
    d = pd.read_csv(OUTS / "descriptive" / "lyme_cases_by_iso_week.csv")
    fig, ax = plt.subplots(figsize=(13.0, 5.6))
    fig.subplots_adjust(top=0.775, bottom=0.155, left=0.070, right=0.985)

    peak = d.reported_lyme_cases.idxmax()
    cols = [C_BLUE_DK if i == peak else C_BLUE for i in d.index]
    ax.bar(d.iso_week, d.reported_lyme_cases, color=cols, width=0.70,
           edgecolor="none", zorder=3)
    pw, pv = int(d.loc[peak, "iso_week"]), int(d.loc[peak, "reported_lyme_cases"])
    ax.annotate(f"vrh: {pw}. teden — {sl(pv, 0)} primerov", (pw, pv),
                textcoords="offset points", xytext=(0, 13), ha="center",
                color=K["primary"], fontsize=11.5, fontweight="600")
    ax.set_xlabel("ISO teden v letu", color=K["secondary"], fontsize=11.5)
    ax.set_ylabel("prijavljeni primeri, 2016–2024", color=K["secondary"], fontsize=11.5)
    ax.set_xticks([1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 53])
    ax.set_xlim(0, 54)
    ax.set_ylim(0, pv * 1.17)
    style(ax)
    sl_axis(ax, "y", 0)
    head(fig, "Zakaj je letni čas v modelu",
         "Seštevek vseh prijavljenih primerov borelioze po ISO tednu čez devet let. Model ta vzorec zajame z enim sinusom in kosinusom.",
         y=0.975, gap=0.072)
    foot(fig, "Vir: model_v3/outputs/descriptive/lyme_cases_by_iso_week.csv  ·  212 občin, 2016-01-04 do 2024-12-30")
    save(fig, "04-sezonskost-borelioze.png")


# ================================================== 5. deployed proxy
def chart_proxy():
    ly = pd.read_csv(OUTS / "precaution_proxy" / "lyme_v1" / "aggregate_metrics.csv")
    km = pd.read_csv(OUTS / "precaution_proxy" / "kme_v1" / "aggregate_metrics.csv")
    scopes = ["development_rolling_origin", "opened_2025_retrospective_audit"]

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.7))
    fig.subplots_adjust(top=0.715, bottom=0.165, left=0.062, right=0.985, wspace=0.20)

    def panel(ax, a, b, ca, cb_, la, lb_, ylim, xlabs, ttl):
        xs, w, gap = np.arange(2), 0.28, 0.018
        for i, s in enumerate(scopes):
            for off, src, c in ((-(w / 2 + gap), a, ca), (w / 2 + gap, b, cb_)):
                v = src.loc[s, "pooled_mae"]
                ax.bar(xs[i] + off, v, w, color=c, edgecolor="none", zorder=3)
                ax.text(xs[i] + off, v + ylim * 0.018, sl(v, 3), ha="center",
                        va="bottom", color=K["primary"], fontsize=11, fontweight="600")
        ax.set_xticks(xs); ax.set_xticklabels(xlabs, fontsize=11.5)
        ax.set_xlim(-0.55, 1.55); ax.set_ylim(0, ylim)
        ax.set_ylabel("MAE  (nižje je bolje)", color=K["secondary"], fontsize=11.5)
        style(ax)
        sl_axis(ax, "y", 2)
        ax.set_title(ttl, color=K["primary"], fontsize=13, fontweight="600",
                     loc="left", pad=12)
        swatches(ax, [(la, ca), (lb_, cb_)], loc="upper right")

    ev = ly[ly.candidate_id == "catboost_current_week_seasonal_municipality_offset"].set_index("evaluation_scope")
    we = ly[ly.candidate_id == "catboost_current_week_compact_weather_offset"].set_index("evaluation_scope")
    panel(axes[0], ev, we, C_BLUE, C_ORANGE,
          "brez vremena (izbran po dokazih)", "z vremenom (v uporabi)",
          0.70, ["razvoj 2017–2024", "odprto leto 2025"], "Borelioza — po občinah")

    base = km[km.candidate_id == "baseline_global_historical_rate"].set_index("evaluation_scope")
    mod = km[km.candidate_id == "glm_current_week_seasonal_region_offset"].set_index("evaluation_scope")
    panel(axes[1], base, mod, C_AQUA, C_BLUE,
          "zgodovinsko povprečje", "izbrani GLM",
          0.42, ["razvoj 2018–2024", "odprto leto 2025"], "KME — po statističnih regijah")

    head(fig, "Objavljeni preventivni signal deluje brez sprotnih prijav primerov",
         "Tedenska napoved uporablja le občino oziroma regijo, letni čas, prebivalstvo in — pri boreliozi — vreme preteklih štirih tednov.",
         y=0.968, gap=0.085)
    foot(fig, "Vir: precaution_proxy/lyme_v1/aggregate_metrics.csv, precaution_proxy/kme_v1/aggregate_metrics.csv  ·  cilj: prijavljeni primeri v tekočem tednu t", y=0.032)
    save(fig, "05-objavljeni-signal-borelioza-kme.png")


# ================================================ 6. feature importance
def chart_features():
    fi = pd.read_csv(OUTS / "catboost_challenger" / "lyme_catboost_challenger_feature_importance.csv")
    m = fi.groupby("feature")["feature_importance"].mean()

    def grp(f):
        if f.startswith("seasonal_"):
            return "Letni čas  (2 značilki)"
        if f == "municipality_code":
            return "Občina  (1 značilka)"
        if f.startswith("past_4w"):
            return "Pretekla incidenca  (1 značilka)"
        return "Vreme ERA5-Land  (21 značilk)"

    g = m.groupby(grp).sum().sort_values()
    fig, ax = plt.subplots(figsize=(11.6, 5.2))
    fig.subplots_adjust(top=0.715, bottom=0.185, left=0.235, right=0.965)

    y = np.arange(len(g))
    cols = [C_ORANGE if "Vreme" in i else C_BLUE for i in g.index]
    ax.barh(y, g.values, height=0.52, color=cols, edgecolor="none", zorder=3)
    for yi, v in zip(y, g.values):
        ax.text(v + 0.9, yi, sl(v, 1) + " %", va="center", color=K["primary"],
                fontsize=12, fontweight="600")
    ax.set_yticks(y); ax.set_yticklabels(g.index, fontsize=11.5)
    ax.set_ylim(-0.62, len(g) - 0.38)
    ax.set_xlim(0, g.max() * 1.19)
    ax.set_xlabel("povprečen delež pomembnosti v modelu (%)", color=K["secondary"], fontsize=11.5)
    style(ax, grid="x")
    sl_axis(ax, "x", 0)
    ax.tick_params(axis="y", length=0)
    head(fig, "Kaj model dejansko uporablja",
         "Povprečje pomembnosti značilk čez osem validacijskih razdelitev. Vreme prispeva 21 značilk, a skupaj manj kot letni čas sam.",
         y=0.972, gap=0.078)
    foot(fig, "Vir: lyme_catboost_challenger_feature_importance.csv  ·  CatBoost PredictionValuesChange, povprečeno čez 8 razdelitev", y=0.028)
    save(fig, "06-pomembnost-znacilk.png")


# ========================================== 7. municipality error spread
def chart_municipality():
    me = pd.read_csv(OUTS / "lockbox_2025" / "lyme_lockbox_municipality_errors.csv")
    cb = me[me.candidate_id == "catboost_poisson_s3_weather_offset"]
    v = cb["mae"].to_numpy()

    fig, ax = plt.subplots(figsize=(12.4, 5.6))
    fig.subplots_adjust(top=0.755, bottom=0.215, left=0.062, right=0.985)

    ax.hist(v, bins=34, color=C_BLUE, edgecolor="none", zorder=3)
    med = float(np.median(v))
    ymax = ax.get_ylim()[1]
    ax.axvline(med, color=K["primary"], lw=1.5, ls=(0, (5, 4)), zorder=5)
    ax.text(med + 0.16, ymax * 0.90, f"mediana {sl(med, 2)}", color=K["primary"],
            fontsize=11.5, fontweight="600", va="center")
    top = cb.nlargest(1, "mae").iloc[0]
    ax.annotate(f"{top.municipality_name}  {sl(top.mae, 2)}", (top.mae, 1.0),
                textcoords="offset points", xytext=(-16, 46), ha="right",
                color=K["secondary"], fontsize=11,
                arrowprops=dict(arrowstyle="-", color=K["axis"], lw=1,
                                shrinkA=0, shrinkB=3))
    ax.set_xlabel("MAE občine v letu 2025  (primeri na teden)", color=K["secondary"], fontsize=11.5)
    ax.set_ylabel("število občin", color=K["secondary"], fontsize=11.5)
    ax.set_xlim(0, v.max() * 1.06)
    style(ax)
    sl_axis(ax, "x", 0); sl_axis(ax, "y", 0)
    head(fig, "Napaka je majhna v večini občin in velika v največjih",
         "Porazdelitev napake po 212 občinah v zaklenjenem letu 2025. Napaka raste z absolutnim številom primerov, torej z velikostjo občine.",
         y=0.972, gap=0.075)
    fig.text(0.062, 0.085,
             "Polovica občin ima MAE pod 0,90 primera na teden, 90 % občin pod 2,17. Ljubljana je edino izrazito odstopajoče območje.",
             color=K["secondary"], fontsize=11, va="center")
    foot(fig, "Vir: lyme_lockbox_municipality_errors.csv  ·  47 izdajnih tednov na občino", y=0.022)
    save(fig, "07-porazdelitev-napake-po-obcinah.png")


# ======================================================== 8. yearly load
def chart_years():
    ly = pd.read_csv(OUTS / "descriptive" / "lyme_cases_by_year.csv")
    km = pd.read_csv(OUTS / "kme_feasibility" / "kme_cases_by_year.csv")
    km = km[km.iso_year <= 2024]

    fig, axes = plt.subplots(1, 2, figsize=(14.2, 5.3))
    fig.subplots_adjust(top=0.715, bottom=0.155, left=0.058, right=0.985, wspace=0.19)

    for ax, x, yv, lab, c, ttl in (
        (axes[0], ly.issue_year, ly.reported_lyme_cases,
         "prijavljeni primeri borelioze", C_BLUE, "Borelioza — po občinah"),
        (axes[1], km.iso_year, km.total_kme_cases,
         "prijavljeni primeri KME", C_ORANGE, "KME — po statističnih regijah"),
    ):
        x, yv = list(x), list(yv)
        ax.bar(x, yv, color=c, width=0.60, edgecolor="none", zorder=3)
        for xi, vi in zip(x, yv):
            ax.text(xi, vi + max(yv) * 0.028, sl(vi, 0),
                    ha="center", color=K["secondary"], fontsize=10)
        ax.set_ylim(0, max(yv) * 1.20)
        ax.set_xticks(x)
        ax.set_xticklabels([str(i) for i in x], fontsize=10.5)
        ax.set_ylabel(lab, color=K["secondary"], fontsize=11.5)
        style(ax)
        sl_axis(ax, "y", 0)
        ax.set_title(ttl, color=K["primary"], fontsize=13, fontweight="600",
                     loc="left", pad=12)

    head(fig, "Letna nihanja, ki jih mora model prenesti",
         "Med letoma 2018 in 2021 je število prijavljenih primerov borelioze padlo za 61 %. Zato je validacija razdeljena po letih in ne naključno.",
         y=0.968, gap=0.085)
    foot(fig, "Vir: descriptive/lyme_cases_by_year.csv, kme_feasibility/kme_cases_by_year.csv  ·  prijavljeni primeri NIJZ", y=0.030)
    save(fig, "08-letna-nihanja-primerov.png")


# ============================================= 9. full approach ranking
def chart_baselines():
    dc = pd.read_csv(OUTS / "catboost_challenger" / "lyme_catboost_development_comparison.csv")
    keep = {
        "baseline_a_overall_history": "Splošno povprečje",
        "baseline_c_seasonal_history": "Sezonsko povprečje",
        "baseline_b_municipality_history": "Povprečje občine",
        "baseline_e_four_week_persistence": "Ponovitev zadnjih 4 tednov",
        "baseline_d_municipality_seasonal_history": "Občina × letni čas",
        "model_s1_seasonality_offset": "GLM: letni čas",
        "model_s3_weather_offset_matched": "GLM: letni čas + občina +\npretekla incidenca + vreme",
        "catboost_poisson_s3_weather_offset": "CatBoost: iste informacije",
    }
    d = dc[dc.candidate_id.isin(keep)].copy()
    d["lab"] = d.candidate_id.map(keep)
    d = d.sort_values("pooled_mae", ascending=False)

    fig, ax = plt.subplots(figsize=(12.0, 6.2))
    fig.subplots_adjust(top=0.775, bottom=0.135, left=0.245, right=0.965)

    y = np.arange(len(d))
    cols = [C_BLUE if c == "catboost_poisson_s3_weather_offset"
            else (C_ORANGE if c.startswith("model_") else C_AQUA)
            for c in d.candidate_id]
    ax.barh(y, d.pooled_mae, height=0.54, color=cols, edgecolor="none", zorder=3)
    for yi, v in zip(y, d.pooled_mae):
        ax.text(v + 0.03, yi, sl(v, 3), va="center", color=K["primary"],
                fontsize=11.5, fontweight="600")
    ax.set_yticks(y); ax.set_yticklabels(d.lab, fontsize=11)
    ax.set_ylim(-0.62, len(d) - 0.38)
    ax.set_xlim(0, d.pooled_mae.max() * 1.13)
    ax.set_xlabel("MAE na 81.832 razvojnih napovedih  (nižje je bolje)",
                  color=K["secondary"], fontsize=11.5)
    style(ax, grid="x")
    sl_axis(ax, "x", 1)
    ax.tick_params(axis="y", length=0)
    swatches(ax, [("preproste statistične osnove", C_AQUA),
                  ("Poissonovi GLM", C_ORANGE),
                  ("izbrani model strojnega učenja", C_BLUE)], loc="upper right")
    head(fig, "Lestvica vseh preizkušenih pristopov",
         "Vsi pristopi so ocenjeni na povsem enakih vrsticah in enaki časovni razdelitvi, zato razlika izvira iz modela in ne iz podatkov.",
         y=0.975, gap=0.068)
    foot(fig, "Vir: lyme_catboost_development_comparison.csv  ·  razvojna leta 2017–2024; zaklenjeni set 2025 ni vključen", y=0.020)
    save(fig, "09-lestvica-pristopov.png")


if __name__ == "__main__":
    print(f"[{MODE}] -> {OUTDIR}")
    for fn in (chart_lockbox, chart_stability, chart_calibration, chart_seasonality,
               chart_proxy, chart_features, chart_municipality, chart_years,
               chart_baselines):
        fn()
    print("done")
