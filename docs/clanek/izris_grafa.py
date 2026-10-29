"""Izriše graf rezultatov za članek; zaženi iz korena z .venv/bin/python docs/clanek/izris_grafa.py.

Vsebinski vir: model_v3/outputs/lockbox_2025/lyme_lockbox_metrics.csv
(enkratna ocena zamrznjenega modela na zaklenjenem letu 2025).
Izhoda: graf-rezultati-belo-ozadje.png in .pdf v tej mapi.
"""
import csv
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/kloppodklopjo-matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
METRICS = ROOT / "model_v3" / "outputs" / "lockbox_2025" / "lyme_lockbox_metrics.csv"

SYSTEMS = (
    ("catboost_poisson_s3_weather_offset", "CatBoost\n(izbrani model)"),
    ("model_s3_weather_offset_matched", "Poissonov GLM\n(primerjalni model)"),
    ("baseline_d_municipality_seasonal_history", "Zgodovinsko povprečje\n(občina × letni čas)"),
)


def sl(value, decimals=3):
    """Zapis števila po slovenskem pravilu: decimalna vejica."""
    return f"{value:.{decimals}f}".replace(".", ",")


def main():
    with METRICS.open(encoding="utf-8") as handle:
        rows = {r["candidate_id"]: r for r in csv.DictReader(handle)}

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "pdf.fonttype": 42})
    fig = plt.figure(figsize=(6.5, 2.6))
    ax = fig.add_axes((0.30, 0.205, 0.685, 0.755))

    for index, (candidate_id, _) in enumerate(SYSTEMS):
        y = len(SYSTEMS) - 1 - index
        value = float(rows[candidate_id]["mae"])
        ax.barh(y, value, height=0.42, facecolor="black", edgecolor="black",
                linewidth=0.8, zorder=3)
        ax.text(value + 0.022, y, sl(value), va="center", ha="left", fontsize=9)

    ax.set_yticks(range(len(SYSTEMS)))
    ax.set_yticklabels([label for _, label in SYSTEMS][::-1], linespacing=1.35)
    ax.set_ylim(-0.6, len(SYSTEMS) - 0.4)
    ax.set_xlim(0, 1.42)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0, 1.25])
    ax.set_xticklabels([sl(v, 2) for v in (0, 0.25, 0.5, 0.75, 1.0, 1.25)])
    ax.set_xlabel("MAE (primeri na občino na teden) — nižje je bolje", fontsize=9)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_linewidth(0.8)
        ax.spines[side].set_color("black")
    ax.tick_params(colors="black", labelsize=9, length=3, width=0.8)
    ax.tick_params(axis="y", length=0)

    destination = Path(__file__).resolve().parent
    for extension in ("png", "pdf"):
        fig.savefig(destination / f"graf-rezultati-belo-ozadje.{extension}",
                    dpi=600, transparent=False, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
