"""Figure 3: paired per-item item-score deltas between arms.

Regenerate: uv run --with matplotlib python figures/fig3-per-question-deltas.py
Reads only committed results/raw-v2/<arm>/run-*.json records (item_score
bool), pairing runs by the run-NNN.json suffix. Shows stacked proportions
of items improved / tied / worsened for kg-json vs llms-txt and
okf-bundle vs llms-txt. Exits gracefully if results/raw-v2/ has no
records yet.
"""

import json
import pathlib
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = pathlib.Path(__file__).resolve().parents[1] / "results" / "raw-v2"
BASE_ARM = "llms-txt"
COMPARISONS = ["kg-json", "okf-bundle"]
IDX_RE = re.compile(r"run-(\d+)\.json$")


def load_item_score(arm):
    by_item = {}
    for path in sorted((RAW / arm).glob("run-*.json")):
        rec = json.loads(path.read_text())
        idx = rec.get("question_index")
        if idx is None:
            match = IDX_RE.search(path.name)
            if not match:
                continue
            idx = int(match.group(1))
        by_item[int(idx)] = bool(rec["item_score"])
    return by_item


def delta_counts(treatment, base):
    improved = tied = worsened = 0
    for q in sorted(set(treatment) & set(base)):
        t_val, b_val = treatment[q], base[q]
        if t_val and not b_val:
            improved += 1
        elif b_val and not t_val:
            worsened += 1
        else:
            tied += 1
    return improved, tied, worsened


def main():
    if not list(RAW.glob("*/run-*.json")):
        print("no records under results/raw-v2/ yet; run the bench first "
              "(recipe/run-bench.sh)")
        return
    base = load_item_score(BASE_ARM)
    if not base:
        print(f"no records under results/raw-v2/{BASE_ARM}/ yet")
        return

    labels, counts = [], []
    for arm in COMPARISONS:
        treat = load_item_score(arm)
        pair = sorted(set(treat) & set(base))
        if not pair:
            print(f"no shared items between {BASE_ARM} and {arm}")
            continue
        labels.append(f"{arm} vs {BASE_ARM}")
        counts.append(delta_counts(treat, base))

    if not labels:
        return

    fig, ax = plt.subplots(figsize=(7.0, 3.2), dpi=200)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ys = range(len(labels))
    left = [0.0] * len(labels)
    segments = [
        ("improved", 1, "#009E73"),
        ("tied", 2, "#7f7f7f"),
        ("worsened", 3, "#D55E00"),
    ]
    for name, idx, color in segments:
        vals = [c[idx - 1] / sum(c) for c in counts]
        ax.barh(ys, vals, left=left, height=0.5, color=color, label=name)
        for y, (v, l, c) in enumerate(zip(vals, left, counts)):
            n = c[idx - 1]
            if v > 0.03:
                ax.annotate(f"{n}", (l + v / 2.0, y), ha="center",
                            va="center", fontsize=8, color="#ffffff")
            elif n > 0:
                ax.annotate(f"{n}", (l + v / 2.0, y), ha="center",
                            va="center", fontsize=8, color="#000000",
                            xytext=(0, 14 if y == 0 else -14),
                            textcoords="offset points")
        left = [l + v for l, v in zip(left, vals)]
    ax.set_yticks(list(ys))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.55, len(labels) - 0.45)
    ax.set_xlabel("Proportion of paired items (counts labeled)",
                  fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.set_title("Paired item-score deltas: okf-bundle drops 25 items\n"
                 "llms-txt answers; kg-json gains 7 and drops 1", fontsize=10)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.38),
              ncol=3, frameon=False)
    fig.subplots_adjust(bottom=0.32)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    out = pathlib.Path(__file__).resolve().parent / "fig3-per-question-deltas.png"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
