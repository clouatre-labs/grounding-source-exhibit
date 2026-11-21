"""Figure 1: exact-match proportion per arm with 95% Wilson score intervals.

Regenerate: uv run --with matplotlib python figures/fig1-arm-comparison.py
Reads only committed results/raw/<arm>/run-*.json records (exact_match bool).
Exits gracefully if results/raw/ has no records yet.
"""

import json
import math
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = pathlib.Path(__file__).resolve().parents[1] / "results" / "raw"
ARMS = ["llms-txt", "kg-json", "okf-bundle"]
COLORS = {"llms-txt": "#7f7f7f", "kg-json": "#0072B2", "okf-bundle": "#D55E00"}


def load_counts():
    counts = {}
    for arm in ARMS:
        paths = sorted((RAW / arm).glob("run-*.json"))
        if not paths:
            continue
        records = [json.loads(p.read_text()) for p in paths]
        k = sum(1 for rec in records if rec["exact_match"])
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
        print("no records under results/raw/ yet; run the bench first "
              "(recipe/run-bench.sh)")
        return
    arms = [a for a in ARMS if a in counts]
    props, lows, highs, ns = [], [], [], []
    for arm in arms:
        k, n = counts[arm]
        p, lo, hi = wilson_interval(k, n)
        props.append(p)
        lows.append(p - lo)
        highs.append(hi - p)
        ns.append(n)

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    xs = range(len(arms))
    bars = ax.bar(xs, props, width=0.55,
                  color=[COLORS[a] for a in arms],
                  yerr=[lows, highs], capsize=4, error_kw={"linewidth": 1})
    for x, p, n in zip(xs, props, ns):
        ax.annotate(f"{p:.2f}\n(n={n})", (x, p), textcoords="offset points",
                    xytext=(0, 14), ha="center", fontsize=8)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(arms)
    ax.set_ylabel("Exact-match proportion")
    ax.set_ylim(0, 1.0)
    ax.set_title("Exact sequence match per arm (95% Wilson score intervals)")
    ax.legend(bars, arms, fontsize=8)
    fig.tight_layout()
    out = pathlib.Path(__file__).resolve().parent / "fig1-arm-comparison.png"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
