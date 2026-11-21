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
ANALYSIS = pathlib.Path(__file__).resolve().parents[1] / "results" / "analysis-v2.json"
ARMS = ["llms-txt", "kg-json", "okf-bundle"]
COLORS = {"llms-txt": "#7f7f7f", "kg-json": "#0072B2", "okf-bundle": "#D55E00"}
# Annotation positions; p-values are loaded from results/analysis-v2.json.
ANNOTATION_TEMPLATE = ("paired permutation (preregistered): kg-json vs "
                       "llms-txt {kg_llms}; kg-json vs okf-bundle {kg_okf};\n"
                       "llms-txt vs okf-bundle {llms_okf} (no separation)")


def perm_label(p):
    return "p<1e-4" if p < 1e-4 else f"p={p:.2f}"


def load_annotation():
    data = json.loads(ANALYSIS.read_text())
    comps = data["comparisons"]
    return ANNOTATION_TEMPLATE.format(
        kg_llms=perm_label(comps["llms-txt_vs_kg-json"]["paired_permutation_partial_credit"]["p_value"]),
        kg_okf=perm_label(comps["kg-json_vs_okf-bundle"]["paired_permutation_partial_credit"]["p_value"]),
        llms_okf=perm_label(comps["llms-txt_vs_okf-bundle"]["paired_permutation_partial_credit"]["p_value"]),
    )


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

    means = {arm: sum(v) / len(v) for arm, v in scores.items()}
    ax.set_xticks(range(len(arms)))
    ax.set_xticklabels([f"{a}\nmean {means[a]:.2f}" for a in arms],
                       fontsize=9)
    ax.set_ylabel("Partial credit\n(dice overlap / integer fraction)",
                  fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylim(-0.05, 1.07)
    ax.set_title("kg-json's answers carry the most credit; llms.txt earns\n"
                 "its item score through abstention, not richer answers",
                 fontsize=10, pad=8)
    ax.text(0.5, -0.24, load_annotation(), transform=ax.transAxes, ha="center",
            fontsize=7.5)
    fig.subplots_adjust(bottom=0.3)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out = pathlib.Path(__file__).resolve().parent / "fig2-partial-credit.png"
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
