"""Figure 3: paired per-question exact-match deltas between arms.

Regenerate: uv run --with matplotlib python figures/fig3-per-question-deltas.py
Reads only committed results/raw-v2/<arm>/run-*.json records (item_score bool),
pairing runs by question index (question_index field or run-<arm>-NNN.json
suffix). Shows stacked proportions of questions improved / tied / worsened
for kg-json vs llms-txt and okf-bundle vs llms-txt. Exits gracefully if
results/raw-v2/ has no records yet.
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


def load_exact(arm):
    by_question = {}
    for path in sorted((RAW / arm).glob("run-*.json")):
        rec = json.loads(path.read_text())
        idx = rec.get("question_index")
        if idx is None:
            match = IDX_RE.search(path.name)
            if not match:
                continue
            idx = int(match.group(1))
        by_question[int(idx)] = bool(rec["item_score"])
    return by_question


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
    base = load_exact(BASE_ARM)
    if not base:
        print(f"no records under results/raw-v2/{BASE_ARM}/ yet")
        return

    labels, improved, tied, worsened = [], [], [], []
    for arm in COMPARISONS:
        treat = load_exact(arm)
        pair = sorted(set(treat) & set(base))
        if not pair:
            print(f"no shared questions between {BASE_ARM} and {arm}")
            continue
        i, t, w = delta_counts(treat, base)
        total = i + t + w
        labels.append(f"{arm} vs {BASE_ARM}")
        improved.append(i / total)
        tied.append(t / total)
        worsened.append(w / total)

    if not labels:
        return

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    ys = range(len(labels))
    left = [0.0] * len(labels)
    segments = [
        ("improved", improved, "#009E73"),
        ("tied", tied, "#7f7f7f"),
        ("worsened", worsened, "#D55E00"),
    ]
    for name, vals, color in segments:
        ax.barh(ys, vals, left=left, height=0.55, color=color, label=name)
        for y, (v, l) in enumerate(zip(vals, left)):
            if v > 0:
                ax.annotate(f"{v:.2f}", (l + v / 2.0, y), ha="center",
                            va="center", fontsize=8, color="#ffffff")
        left = [l + v for l, v in zip(left, vals)]
    ax.set_yticks(list(ys))
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("Proportion of paired questions")
    ax.set_title("Paired per-question exact-match deltas")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    out = pathlib.Path(__file__).resolve().parent / "fig3-per-question-deltas.png"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
