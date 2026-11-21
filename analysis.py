#!/usr/bin/env python3
"""Sealed analysis for the grounding-source exhibit.

Reads results/raw/<arm>/run-*.json for the three arms, computes per-arm
exact-match rates with Wilson 95% CIs, pairwise two-proportion score tests
on exact match (pooled SE), and pairwise Welch t tests on partial credit
(lgamma-based incomplete beta t survival function, mirroring
figures/fig2-partial-credit.py). Writes results/analysis.json and prints
a markdown summary.

Standard library only; uv-run compatible.
"""

import itertools
import json
import math
import pathlib
from datetime import datetime, timezone

RAW = pathlib.Path(__file__).resolve().parent / "results" / "raw"
OUT = pathlib.Path(__file__).resolve().parent / "results" / "analysis.json"
ARMS = ["llms-txt", "kg-json", "okf-bundle"]


def wilson_ci(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def two_proportion_score_test(x1: int, n1: int, x2: int, n2: int):
    n = n1 + n2
    if n1 == 0 or n2 == 0 or n == 0:
        return (0.0, 1.0)
    p1, p2 = x1 / n1, x2 / n2
    p_pool = (x1 + x2) / n
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return (0.0, 1.0)
    z = (p1 - p2) / se
    p = 2 * _norm_sf_half(z)
    return (z, p)


def _norm_sf_half(z: float) -> float:
    """Standard normal survival function (upper tail)."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def betainc(a: float, b: float, x: float) -> float:
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


def _betacf(a: float, b: float, x: float, itmax: int = 300, eps: float = 3e-14) -> float:
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
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def t_sf_two_sided(t: float, df: float) -> float:
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    return betainc(df / 2.0, 0.5, x)


def welch_t(xs, ys):
    nx, ny = len(xs), len(ys)
    if nx < 2 or ny < 2:
        return (0.0, float("nan"), 1.0, 0.0)
    mx, my = sum(xs) / nx, sum(ys) / ny
    vx = sum((v - mx) ** 2 for v in xs) / (nx - 1)
    vy = sum((v - my) ** 2 for v in ys) / (ny - 1)
    se2 = vx / nx + vy / ny
    if se2 == 0:
        return (0.0, float("nan"), 1.0, 0.0)
    t = (mx - my) / math.sqrt(se2)
    df = se2 * se2 / ((vx / nx) ** 2 / (nx - 1) + (vy / ny) ** 2 / (ny - 1))
    p = t_sf_two_sided(abs(t), df)
    return (t, df, p, mx - my)


def load_arm(arm: str):
    paths = sorted((RAW / arm).glob("run-*.json"))
    exact = partial = 0
    partials = []
    for path in paths:
        record = json.loads(path.read_text())
        if record.get("exact_match") is True:
            exact += 1
        pc = record.get("partial_credit")
        if pc is not None:
            partial += 1
            partials.append(float(pc))
    return {"n": len(paths), "exact": exact, "partials": partials,
            "partial_n": partial}


def main():
    arms = {}
    for arm in ARMS:
        arms[arm] = load_arm(arm)
        if arms[arm]["n"] == 0:
            print(f"no records under results/raw/{arm}/ yet; "
                  "run the bench first (recipe/run-bench.sh)")
            return

    summary = {}
    for arm, d in arms.items():
        n = d["n"]
        rate = d["exact"] / n
        lo, hi = wilson_ci(d["exact"], n)
        pmean = (sum(d["partials"]) / d["partial_n"]) if d["partial_n"] else None
        summary[arm] = {
            "n": n,
            "exact_match_count": d["exact"],
            "exact_match_rate": rate,
            "wilson_ci_95": [lo, hi],
            "partial_credit_n": d["partial_n"],
            "partial_credit_mean": pmean,
        }

    comparisons = {}
    for a, b in itertools.combinations(ARMS, 2):
        da, db = arms[a], arms[b]
        z, pz = two_proportion_score_test(
            da["exact"], da["n"], db["exact"], db["n"])
        t, df, pt, diff = welch_t(da["partials"], db["partials"])
        comparisons[f"{a}_vs_{b}"] = {
            "exact_match": {"statistic": z, "p_value": pz},
            "partial_credit": {
                "statistic": t, "df": df, "p_value": pt,
                "mean_difference": diff,
            },
        }

    result = {
        "schema_version": "1.0.0",
        "experiment": "grounding-source-exhibit",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "statistics": {
            "primary": "two-proportion score test on pairwise exact-match deltas",
            "secondary": "Welch t on partial credit",
            "reporting": "raw p-values only, no multiplicity adjustment",
        },
        "arms": summary,
        "comparisons": comparisons,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")

    print(f"# Analysis summary ({result['analyzed_at']})\n")
    for arm, s in summary.items():
        lo, hi = s["wilson_ci_95"]
        pmean = ("n/a" if s["partial_credit_mean"] is None
                 else f"{s['partial_credit_mean']:.4f}")
        print(f"## {arm}: n={s['n']}, exact={s['exact_match_count']} "
              f"({s['exact_match_rate']:.4f}, Wilson 95% CI "
              f"[{lo:.4f}, {hi:.4f}]), partial-credit mean={pmean} "
              f"(m={s['partial_credit_n']})")
    print()
    for pair, c in comparisons.items():
        e, p = c["exact_match"], c["partial_credit"]
        print(f"- {pair}: exact-match z={e['statistic']:.4f}, "
              f"p={e['p_value']:.4f}; Welch t={p['statistic']:.4f}, "
              f"df={p['df']:.1f}, p={p['p_value']:.4f}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
