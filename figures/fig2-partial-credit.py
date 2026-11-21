"""Figure 2: partial-credit distributions per arm (strip over box plot).

Regenerate: uv run --with matplotlib python figures/fig2-partial-credit.py
Reads only committed results/raw/<arm>/run-*.json records (partial_credit
float in [0, 1]; nulls excluded). Annotates Welch t and a p-value computed
from an lgamma-based incomplete beta t-distribution survival function
(self-contained, no scipy). Exits gracefully if results/raw/ has no records.
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


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b) via continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(-lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - betainc(b, a, 1.0 - x)


def _betacf(a, b, x, itmax=300, eps=3e-14):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        num = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + num * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + num / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        num = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + num * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + num / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def t_sf_two_sided(t, df):
    """Two-sided p for Student t under H0 via incomplete beta."""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    return betainc(df / 2.0, 0.5, x)


def welch_t(xs, ys):
    nx, ny = len(xs), len(ys)
    mx, my = sum(xs) / nx, sum(ys) / ny
    vx = sum((v - mx) ** 2 for v in xs) / (nx - 1)
    vy = sum((v - my) ** 2 for v in ys) / (ny - 1)
    se2 = vx / nx + vy / ny
    t = (mx - my) / math.sqrt(se2)
    df = se2 * se2 / ((vx / nx) ** 2 / (nx - 1) + (vy / ny) ** 2 / (ny - 1))
    return t, df


def main():
    scores = load_scores()
    if not scores:
        print("no records under results/raw/ yet; run the bench first "
              "(recipe/run-bench.sh)")
        return
    arms = [a for a in ARMS if a in scores]

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    annotations = []
    for i, arm in enumerate(arms):
        vals = scores[arm]
        ax.boxplot([vals], positions=[i], widths=0.45,
                   showcaps=True, showfliers=False,
                   medianprops={"color": "#000000", "linewidth": 1})
        jitter = [((i * 7919 + j * 104729) % 1000 - 500) / 500.0 * 0.16
                  for j in range(len(vals))]
        ax.scatter([i + dj for dj in jitter], vals, s=10, alpha=0.5,
                   color=COLORS[arm], edgecolors="none")
        mean = sum(vals) / len(vals)
        ax.scatter([i], [mean], marker="D", s=30, color="#000000", zorder=5)
        ax.annotate(f"mean {mean:.2f}", (i, mean), textcoords="offset points",
                    xytext=(14, 4), fontsize=8)
        annotations.append(f"{arm}: n={len(vals)}")

    if len(arms) >= 2:
        t, df = welch_t(scores[arms[0]], scores[arms[1]])
        p = t_sf_two_sided(abs(t), df)
        ax.set_title(f"Welch t on partial credit ({arms[0]} vs {arms[1]}): "
                     f"t={t:.3f}, df={df:.1f}, p={p:.4f}")
    else:
        ax.set_title("Partial credit per arm")
    ax.set_xticks(range(len(arms)))
    ax.set_xticklabels(arms)
    ax.set_ylabel("Partial credit (prefix fraction)")
    ax.set_ylim(-0.03, 1.03)
    ax.legend(annotations, fontsize=8)
    fig.tight_layout()
    out = pathlib.Path(__file__).resolve().parent / "fig2-partial-credit.png"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
