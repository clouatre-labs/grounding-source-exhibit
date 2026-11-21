"""Figure 3: conditional extraction and abstention accuracy per arm.

Regenerate: uv run --with matplotlib python figures/fig3-conditional-accuracy.py
Reads only committed results/raw-v2/<arm>/run-*.json records. The composite
item score mixes extraction (answerable items) and abstention credit
(correct abstention on unanswerable items scores 1), so the conditional
accuracies are what explain where each arm's composite lands. Accuracies
re-derive the numbers in results/analysis-v2.json.
"""

import json
import pathlib
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = pathlib.Path(__file__).resolve().parents[1] / "results" / "raw-v2"
ARMS = ["llms-txt", "kg-json", "okf-bundle"]
COLORS = {"llms-txt": "#7f7f7f", "kg-json": "#0072B2", "okf-bundle": "#D55E00"}
ANSWERABLE = {
    "llms-txt": {"F3", "F4"},
    "kg-json": {"F1", "F2", "F3", "F4"},
    "okf-bundle": {"F4"},
}


def load_tally():
    tally = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for arm in ARMS:
        for path in sorted((RAW / arm).glob("run-*.json")):
            rec = json.loads(path.read_text())
            cell = tally[arm][rec["family"]]
            cell[0] += 1 if rec["item_score"] else 0
            cell[1] += 1
    return tally


def main():
    tally = load_tally()
    if not tally:
        print("no records under results/raw-v2/ yet; run the bench first "
              "(recipe/run-bench.sh)")
        return

    extraction = {}
    abstention = {}
    for arm in ARMS:
        ex_k = sum(tally[arm][f][0] for f in ANSWERABLE[arm])
        ex_n = sum(tally[arm][f][1] for f in ANSWERABLE[arm])
        extraction[arm] = (ex_k, ex_n)
        ab_k = sum(tally[arm][f][0] for f in tally[arm] if f not in ANSWERABLE[arm])
        ab_n = sum(tally[arm][f][1] for f in tally[arm] if f not in ANSWERABLE[arm])
        if ab_n:
            abstention[arm] = (ab_k, ab_n)

    panels = [
        ("Extraction accuracy (answerable items)", extraction),
        ("Abstention accuracy (unanswerable items)", abstention),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.6), dpi=200, sharey=True)
    for ax, (title, data) in zip(axes, panels):
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        arms = [a for a in ARMS if a in data]
        for i, arm in enumerate(arms):
            k, n = data[arm]
            ax.bar(i, k / n, width=0.5, color=COLORS[arm], zorder=2)
            ax.annotate(f"{k}/{n}", (i, k / n), textcoords="offset points",
                        xytext=(0, 3), ha="center", fontsize=8)
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels([a for a in arms], fontsize=8, rotation=12)
        ax.set_title(title, fontsize=9)
        ax.set_ylim(0, 1.09)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.tick_params(axis="y", labelsize=8)
    axes[0].set_ylabel("Accuracy", fontsize=9)

    fig.suptitle("The okf bundle fails at both extracting and abstaining; "
                 "llms.txt extracts\nperfectly but mis-abstains on unanswerable F1",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    out = pathlib.Path(__file__).resolve().parent / "fig3-conditional-accuracy.png"
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
