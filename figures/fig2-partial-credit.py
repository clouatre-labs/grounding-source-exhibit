"""Figure 2: partial-credit distributions per arm with preregistered tests.

Regenerate: uv run --with matplotlib python figures/fig2-partial-credit.py
Reads only committed results/raw-v2/<arm>/run-*.json records (partial_credit
float in [0, 1]; nulls excluded). Partial credit is the preregistered
secondary metric: dice overlap on set-valued families (F1, F3, F4) and the
fraction of correct integers on F2. Annotated p-values are the sealed
paired permutation test (10000 permutations, seed 20261123) from
results/analysis-v2.json.
"""

import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = pathlib.Path(__file__).resolve().parents[1] / "results" / "raw-v2"
ARMS = ["llms-txt", "kg-json", "okf-bundle"]
COLORS = {"llms-txt": "#7f7f7f", "kg-json": "#0072B2", "okf-bundle": "#D55E00"}
# Sealed paired permutation results (results/analysis-v2.json).
ANNOTATION = ("paired permutation (preregistered): kg-json vs llms-txt "
              "p<1e-4; kg-json vs okf-bundle p<1e-4;\nllms-txt vs "
              "okf-bundle p=0.44 (no separation)")


def load_scores():
    scores = {}
    for arm in ARMS:
        paths = sorted((RAW / arm).glob("run-*.json"))
        if not paths:
            continue
        vals = [json.loads(p.read_text())["partial_credit"] for p in paths]
        vals = [v for v in vals if v is not None]
        if vals:
            scores[arm] = vals
    return scores


def main():
    scores = load_scores()
    if not scores:
        print("no records under results/raw-v2/ yet; run the bench first "
              "(recipe/run-bench.sh)")
        return
    arms = [a for a in ARMS if a in scores]

    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=200)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for i, arm in enumerate(arms):
        vals = scores[arm]
        ax.boxplot([vals], positions=[i], widths=0.4, showcaps=True,
                   showfliers=False, medianprops={"color": "#000000",
                                                  "linewidth": 1})
        jitter = [((i * 7919 + j * 104729) % 1000 - 500) / 500.0 * 0.12
                  for j in range(len(vals))]
        ax.scatter([i + dj for dj in jitter], vals, s=6, alpha=0.5,
                   color=COLORS[arm], edgecolors="none", zorder=3)
        mean = sum(vals) / len(vals)
        ax.scatter([i], [mean], marker="D", s=22, color="#000000", zorder=4)
        ax.annotate(f"mean {mean:.2f}", (i, mean), textcoords="offset points",
                    xytext=(12, 4), fontsize=8)

    ax.set_xticks(range(len(arms)))
    ax.set_xticklabels(arms, fontsize=9)
    ax.set_ylabel("Partial credit\n(dice overlap / integer fraction)",
                  fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("Partial credit separates kg-json from both other arms",
                 fontsize=10)
    ax.text(0.5, -0.24, ANNOTATION, transform=ax.transAxes, ha="center",
            fontsize=7.5)
    fig.subplots_adjust(bottom=0.3)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out = pathlib.Path(__file__).resolve().parent / "fig2-partial-credit.png"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
