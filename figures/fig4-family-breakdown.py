"""Figure 4: per-family breakdown, extraction and abstention kept separate.

Regenerate: uv run --with matplotlib python figures/fig4-family-breakdown.py
Reads only committed results/raw-v2/<arm>/run-*.json records grouped by the
family field. Per-family breakdowns are labeled exploratory in
seal-v2.json. Answerable arms appear only in the extraction panel; on
unanswerable families an item scores 1 only for a correct abstention, so
those arms appear only in the abstention panel. A bar therefore always
means exactly one thing.
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
# Families each arm can answer (seal-v2.json answerability map).
ANSWERABLE = {
    "llms-txt": {"F3", "F4"},
    "kg-json": {"F1", "F2", "F3", "F4"},
    "okf-bundle": {"F4"},
}
FAMILY_LABELS = {
    "F1": "F1\ncitation edges",
    "F2": "F2\nedgeStats counts",
    "F3": "F3\ncluster membership",
    "F4": "F4\npost clusters",
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


def draw_panel(ax, title, groups, width=0.24):
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    labels = list(groups)
    all_arms = sorted({arm for arms in groups.values() for arm in arms},
                      key=ARMS.index)
    for gi, family in enumerate(labels):
        arms = groups[family]
        offsets = {arm: (j - (len(arms) - 1) / 2) * width
                   for j, arm in enumerate(arms)}
        last_y = None
        for j, arm in enumerate(arms):
            k, n = groups[family][arm]
            ax.bar(gi + offsets[arm], k / n, width=width - 0.02,
                   color=COLORS[arm], zorder=2)
            # Bump the label up only when it would collide with the
            # neighbor's label at the same bar height.
            bump = 14 if last_y is not None and k / n == last_y else 4
            ax.annotate(f"{k}/{n}", (gi + offsets[arm], k / n),
                        textcoords="offset points",
                        xytext=(0, bump), ha="center", fontsize=7.5,
                        color="#000000")
            last_y = k / n
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([FAMILY_LABELS[f] for f in labels], fontsize=7.5)
    ax.set_ylim(0, 1.16)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.tick_params(axis="y", labelsize=7.5)
    ax.set_title(title, fontsize=9, pad=14)


def main():
    tally = load_tally()
    if not tally:
        print("no records under results/raw-v2/ yet; run the bench first "
              "(recipe/run-bench.sh)")
        return

    families = ["F1", "F2", "F3", "F4"]
    extraction = {f: {arm: tally[arm][f] for arm in ARMS
                      if f in ANSWERABLE[arm]} for f in families}
    abstention = {f: {arm: tally[arm][f] for arm in ARMS
                      if f not in ANSWERABLE[arm]} for f in families}

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.4), dpi=200)
    draw_panel(axes[0], "Extraction (answerable arms only)", extraction)
    draw_panel(axes[1], "Abstention (unanswerable arms only)", abstention)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[a]) for a in ARMS]
    fig.legend(handles, ARMS, fontsize=8, loc="upper center", ncol=3,
               frameon=False, bbox_to_anchor=(0.5, 0.94))
    fig.suptitle("okf-bundle collapses on the only family all arms can "
                 "answer (F4: 6/16)\nand on abstention, where llms-txt "
                 "misses only F1", fontsize=10, y=1.02)
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    out = pathlib.Path(__file__).resolve().parent / "fig4-family-breakdown.png"
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
