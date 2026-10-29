"""Izriše shemo za članek; zaženi iz korena z .venv/bin/python docs/clanek/izris_sheme.py.

Vsebinski viri: model_v3/config/precaution_snapshot.json in model_manifest.json
v model_v3/outputs/precaution_proxy/{lyme_v1,kme_v1}/.
Izhoda: shema-delovanja-modela-preprosta.png in .pdf v tej mapi.
"""
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/kloppodklopjo-matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "pdf.fonttype": 42})
    fig = plt.figure(figsize=(6.5, 3.8))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set(xlim=(0, 16), ylim=(0, 9.35))
    ax.axis("off")

    def box(x, y, w, h, text):
        ax.add_patch(Rectangle((x, y), w, h, fill=False,
                               edgecolor="black", linewidth=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                linespacing=1.35)

    def arrow(points):
        for start, end in zip(points[:-2], points[1:-1]):
            ax.plot([start[0], end[0]], [start[1], end[1]],
                    color="black", linewidth=0.8)
        ax.annotate("", xy=points[-1], xytext=points[-2],
                    arrowprops={"arrowstyle": "->", "lw": 0.8,
                                "color": "black", "shrinkA": 0, "shrinkB": 0})

    ax.text(8, 8.1, "Modela se učita iz preteklih prijav bolezni\n"
            "ob upoštevanju števila prebivalcev.",
            ha="center", va="center", linespacing=1.4)
    for x, label in ((2.6, "VHODNI PODATKI"), (8, "IZRAČUN"),
                     (13.4, "PRIKAZ NA ZEMLJEVIDU")):
        ax.text(x, 6.85, label, ha="center", va="center", fontsize=8)
    box(0.3, 4.5, 4.6, 1.8,
        "Občina in letni čas\nVreme zadnjih 4\nzaključenih tednov")
    box(6.2, 4.5, 3.6, 1.8, "Model\nborelioze")
    box(11.1, 4.5, 4.6, 1.8, "Tedenski signal\nza občino")
    box(0.3, 1.6, 4.6, 1.8, "Regija in letni čas")
    box(6.2, 1.6, 3.6, 1.8, "Model\nKME")
    box(11.1, 1.6, 4.6, 1.8, "Tedenski signal\nza regijo")
    for y in (5.4, 2.5):
        arrow([(4.9, y), (6.2, y)])
        arrow([(9.8, y), (11.1, y)])
    ax.text(8, 0.65, "Signal za tekoči teden: nizko / srednje / visoko.\n"
            "Relativna ocena za previdnost, ne osebna verjetnost okužbe.",
            ha="center", va="center", fontsize=9, linespacing=1.4)
    destination = Path(__file__).resolve().parent
    for extension in ("png", "pdf"):
        fig.savefig(destination / f"shema-delovanja-modela-preprosta.{extension}",
                    dpi=600, transparent=True)
        fig.savefig(destination / f"shema-delovanja-modela-belo-ozadje.{extension}",
                    dpi=600, transparent=False, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
