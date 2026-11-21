"""Figure 4: exploratory per-family item-score counts per arm.

Regenerate: uv run --with matplotlib python figures/fig4-family-breakdown.py
Reads only committed results/raw-v2/<arm>/run-*.json records grouped by the
family field. Per-family breakdowns are labeled exploratory in
seal-v2.json. For llms-txt and okf-bundle, F1/F2 (and F3 for okf-bundle)
items are unanswerable, so a count there reflects a correct abstention,
not an extraction; kg-json is answerable on every family.
"""

import json
import pathlib
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = pathlib.Path(__file__).resolve().parents[1] / "results" / "raw-v2"
ARMS = ["llms-txt", "kg-json", "okf-bundle"]
FAMILIES = ["F1", "F2", "F3", "F4"]
COLORS = {"llms-txt": "#7f7f7f", "kg-json": "#0072B2", "okf-bundle": "#D55E00"}
FAMILY_LABELS = {
    "F1": "F1 citation edges\n(kg-json only)",
    "F2": "F2 edgeStats counts\n(kg-json only)",
    "F3": "F3 cluster membership\n(kg-json + llms-txt)",
    "F4": "F4 post clusters\n(all arms)",
}


def load_counts():
    counts = {}
    for arm in ARMS:
        tally = defaultdict(lambda: [0, 0])
        for path in sorted((RAW / arm).glob("run-*.json")):
            rec = json.loads(path.read_text())
            tally[rec["family"]][0] += 1 if rec["item_score"] else 0
            tally[rec["family"]][1] += 1
        counts[arm] = tally
    return counts


def main():
    counts = load_counts()
    if not counts:
        print("no records under results/raw-v2/ yet; run the bench first "
              "(recipe/run-bench.sh)")
        return

    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=200)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    width = 0.24
    for i, family in enumerate(FAMILIES):
        for j, arm in enumerate(ARMS):
            k, n = counts[arm][family]
            x = i + (j - 1) * width
            ax.bar(x, k / n, width=width - 0.02, color=COLORS[arm], zorder=2)
            ax.annotate(f"{k}/{n}", (x, k / n), textcoords="offset points",
                        xytext=(0, 3), ha="center", fontsize=7)
    ax.set_xticks(range(len(FAMILIES)))
    ax.set_xticklabels([FAMILY_LABELS[f] for f in FAMILIES], fontsize=8)
    ax.set_ylabel("Item-score count per family", fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylim(0, 1.09)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_title("The okf bundle loses on every answerable family;\n"
                 "llms-txt trails kg-json only on unanswerable F1",
                 fontsize=10)
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=COLORS[a]) for a in ARMS],
              ARMS, fontsize=8, loc="upper center", ncol=3, frameon=False,
              bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout()
    out = pathlib.Path(__file__).resolve().parent / "fig4-family-breakdown.png"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
