"""Figure 1: preregistered item-score rate per arm with 95% Wilson intervals.

Regenerate: uv run --with matplotlib python figures/fig1-arm-comparison.py
Reads only committed results/raw-v2/<arm>/run-*.json records (item_score
bool). Item score = correct answer or correct abstention under the
preregistered answerability map (seal-v2.json). Primary endpoint: pairwise
McNemar exact test with Holm-Bonferroni across the 3 pairs.
"""

import json
import math
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = pathlib.Path(__file__).resolve().parents[1] / "results" / "raw-v2"
ARMS = ["llms-txt", "kg-json", "okf-bundle"]
COLORS = {"llms-txt": "#7f7f7f", "kg-json": "#0072B2", "okf-bundle": "#D55E00"}
# Holm-adjusted McNemar exact p-values from results/analysis-v2.json.
BRACKETS = [
    ("llms-txt", "kg-json", "Holm p=0.070 (ns)", 0.955),
    ("kg-json", "okf-bundle", "Holm p<1e-7", 1.075),
]


def load_counts():
    counts = {}
    for arm in ARMS:
        paths = sorted((RAW / arm).glob("run-*.json"))
        if not paths:
            continue
        records = [json.loads(p.read_text()) for p in paths]
        k = sum(1 for rec in records if rec["item_score"])
        counts[arm] = (k, len(records))
    return counts


def wilson_interval(k, n, z=1.959963985):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def main():
    counts = load_counts()
    if not counts:
        print("no records under results/raw-v2/ yet; run the bench first "
              "(recipe/run-bench.sh)")
        return
    arms = [a for a in ARMS if a in counts]

    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=200)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    xs = {arm: i for i, arm in enumerate(arms)}
    for arm in arms:
        k, n = counts[arm]
        p, lo, hi = wilson_interval(k, n)
        ax.bar(xs[arm], p, width=0.5, color=COLORS[arm], zorder=2)
        ax.errorbar(xs[arm], p, yerr=[[p - lo], [hi - p]], capsize=2,
                    elinewidth=0.8, color="#000000", zorder=3)
        ax.annotate(f"{p:.2f}", (xs[arm], hi), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=9)
    ax.set_xticks([xs[a] for a in arms])
    ax.set_xticklabels([f"{a}\n(n={counts[a][1]})" for a in arms], fontsize=9)
    ax.set_ylabel("Item score rate", fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])

    for left, right, label, y in BRACKETS:
        x0, x1 = xs[left], xs[right]
        ax.plot([x0, x0, x1, x1], [y - 0.012, y, y, y - 0.012],
                linewidth=0.8, color="#000000", clip_on=False)
        ax.text((x0 + x1) / 2, y + 0.008, label, ha="center", fontsize=8)

    ax.set_title("llms.txt matched the knowledge graph; the okf bundle\n"
                 "scored 0.49 on preregistered item score", fontsize=10)
    fig.tight_layout()
    out = pathlib.Path(__file__).resolve().parent / "fig1-arm-comparison.png"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
