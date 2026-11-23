#!/usr/bin/env python3
"""Analysis for grounding-source-exhibit v2.3 full run (issue #36,
seal-v4.json).

Reads the raw captures (results/v2.3-full/raw/<arm>/run-NNN.json for the
four arms), seal-v4.json, and ground-truth/full-v2.1.json; writes
results/v2.3-full/analysis-v4.json:

  per-arm   total (n), rate (mean item_score over non-null scores),
            wilson95 (Wilson score interval, descriptive), per_family,
            truncations (finish_reason == "length"), abstentions,
            abstention_accuracy (accuracy among graded abstentions)
  pairwise  McNemar exact test (binomial two-sided via math.comb) over the
            6 arm pairs on item_score discordance, Holm-Bonferroni
            adjusted across all 6 pairs (alpha 0.05, seed 20261123 for
            reproducibility bookkeeping)
  per_fix   verdicts for the three post-v2.1 content fixes --
            edgeStats_F2, directional_cites_F1,
            frontmatter_membership_F3_F4 -- with before (v2.1 run,
            results/raw-v2) and after (this run) per-arm family scores.

"Before" family scores come from results/raw-v2 (the v2.1 full run
captures, which already carry item_score under the seal-v2 answerability
map); "after" from results/v2.3-full/raw (seal-v4 map). The v2.1 baseline
arms are the fix targets: okf-bundle for edgeStats_F2 and
directional_cites_F1, llms-txt for frontmatter_membership_F3_F4 (the
published post joined every surface, so the drift item q-20261125-015 is
graded answerable in the "after" run only).

Usage: analysis-v4.py [--raw-before DIR] [--raw-after DIR] [--out PATH]

Standard library only; uv-run compatible.
"""

import argparse
import json
import math
import pathlib
import sys
from datetime import UTC, datetime

ARMS = ["llms-txt", "kg-json", "okf-bundle", "okf-index-relevant"]
FAMILIES = ["F1", "F2", "F3", "F4"]
Z95 = 1.959963984540054
SEED = 20261123
ALPHA = 0.05

# Fix target arms for the before/after per-fix verdicts.
FIX_TARGETS = {
    "edgeStats_F2": ("F2", ["okf-bundle", "okf-index-relevant"]),
    "directional_cites_F1": ("F1", ["okf-bundle", "okf-index-relevant"]),
    "frontmatter_membership_F3_F4": ("F3", ["llms-txt", "kg-json"]),
}


def load_arm(raw_dir: pathlib.Path, arm: str):
    """Return {item_id: run_dict} for one arm's captures."""
    runs = {}
    for path in sorted((raw_dir / arm).glob("run-*.json")):
        run = json.loads(path.read_text())
        runs[run["item_id"]] = run
    return runs


def wilson95(k: int, n: int):
    """Wilson score interval (descriptive)."""
    if n == 0:
        return None
    p = k / n
    denom = 1 + Z95 * Z95 / n
    center = p + Z95 * Z95 / (2 * n)
    spread = Z95 * math.sqrt(p * (1 - p) / n + Z95 * Z95 / (4 * n * n))
    return {
        "lo": (center - spread) / denom,
        "hi": (center + spread) / denom,
        "label": "descriptive",
    }


def mcnemar_exact(b: int, c: int):
    """Exact McNemar: 2 * P(X <= min(b,c)) under Binomial(b+c, 0.5),
    capped at 1."""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** (n - 1))
    return min(1.0, tail)


def holm(pvals):
    """Holm-Bonferroni adjusted p-values, order-preserving."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, pvals[i] * (m - rank)))
        adj[i] = running
    return adj


def arm_summary(runs):
    n = len(runs)
    scored = [r for r in runs.values() if r.get("item_score") is not None]
    k = sum(1 for r in scored if r["item_score"])
    per_family = {}
    for fam in FAMILIES:
        fr = [r for r in runs.values() if r["family"] == fam]
        fs = [r for r in fr if r.get("item_score") is not None]
        fk = sum(1 for r in fs if r["item_score"])
        per_family[fam] = {
            "n": len(fr),
            "scored": len(fs),
            "correct": fk,
            "rate": (fk / len(fs)) if fs else None,
        }
    abstained = [r for r in runs.values() if r.get("abstained")]
    graded_abst = [r for r in abstained if r.get("item_score") is not None]
    ab_correct = sum(1 for r in graded_abst if r["item_score"])
    truncations = sum(1 for r in runs.values() if r.get("finish_reason") == "length")
    return {
        "n": n,
        "item_score_count": k,
        "item_score_rate": (k / len(scored)) if scored else None,
        "wilson95": wilson95(k, len(scored)),
        "per_family": per_family,
        "truncations": truncations,
        "abstentions": len(abstained),
        "abstention_accuracy": (ab_correct / len(graded_abst)) if graded_abst else None,
    }


def family_score(runs, fam):
    """Mean item_score over graded runs in one family (None if ungraded)."""
    fs = [
        r
        for r in runs.values()
        if r["family"] == fam and r.get("item_score") is not None
    ]
    if not fs:
        return None
    return sum(1 for r in fs if r["item_score"]) / len(fs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--raw-before",
        default="results/raw-v2",
        help="v2.1 baseline captures (before per-fix scores)",
    )
    ap.add_argument(
        "--raw-after", default="results/v2.3-full/raw", help="v2.3 full run captures"
    )
    ap.add_argument("--seal", default="seal-v4.json")
    ap.add_argument("--out", default="results/v2.3-full/analysis-v4.json")
    args = ap.parse_args()

    root = pathlib.Path(".")
    before_dir, after_dir = root / args.raw_before, root / args.raw_after
    before = {arm: load_arm(before_dir, arm) for arm in ARMS}
    after = {arm: load_arm(after_dir, arm) for arm in ARMS}

    for arm in ARMS:
        if not after[arm]:
            print(
                f"ERROR: no captures for arm '{arm}' under {after_dir}", file=sys.stderr
            )
            return 2

    out = {
        "schema_version": "2.3.0",
        "experiment": "grounding-source-exhibit-v2.3-full",
        "analyzed_at": datetime.now(UTC).isoformat(),
        "seal": json.loads(pathlib.Path(args.seal).read_text()).get(
            "schema", "unknown"
        ),
        "statistics": {
            "primary": "overall item_score; pairwise McNemar exact test "
            "with Holm-Bonferroni across 6 arm pairs, "
            f"alpha {ALPHA}",
            "wilson": "Wilson 95% score intervals per arm (descriptive "
            "only, not hypothesis tests)",
            "permutation_seed": SEED,
        },
        "arms": {arm: arm_summary(after[arm]) for arm in ARMS},
        "comparisons": {},
        "per_fix": {},
    }

    # Pairwise McNemar exact + Holm over the 6 pairs, on item_score
    # discordance (ungraded runs excluded from both sides' vectors).
    pairs = [
        (ARMS[i], ARMS[j]) for i in range(len(ARMS)) for j in range(i + 1, len(ARMS))
    ]
    raw_p = []
    for a, b in pairs:
        ids = sorted(set(after[a]) & set(after[b]))
        va = {i: after[a][i]["item_score"] for i in ids}
        vb = {i: after[b][i]["item_score"] for i in ids}
        paired = [i for i in ids if va[i] is not None and vb[i] is not None]
        nd = sum(1 for i in paired if va[i] and not vb[i])
        nl = sum(1 for i in paired if vb[i] and not va[i])
        p = mcnemar_exact(nd, nl)
        raw_p.append(p if p is not None else 1.0)
        out["comparisons"][f"{a}_vs_{b}"] = {
            "n_paired": len(paired),
            "discordant": [nd, nl],
            "mcnemar_exact_p": p,
        }
    adj = holm(raw_p)
    for (a, b), p_adj, p_raw in zip(pairs, adj, raw_p):
        key = f"{a}_vs_{b}"
        out["comparisons"][key]["p_value_holm"] = p_adj
        out["comparisons"][key]["significant_at_0.05"] = p_adj < ALPHA
        out["comparisons"][key]["direction"] = (
            f"{a} higher"
            if out["comparisons"][key]["discordant"][0]
            > out["comparisons"][key]["discordant"][1]
            else f"{b} higher"
            if out["comparisons"][key]["discordant"][1]
            > out["comparisons"][key]["discordant"][0]
            else "tie"
        )

    # Per-fix verdicts: before (v2.1) vs after (v2.3) family scores on
    # the fix-target arms.
    for fix, (fam, arms) in FIX_TARGETS.items():
        entry = {"family": fam, "arms": {}}
        deltas = []
        for arm in arms:
            b_score = family_score(before[arm], fam)
            a_score = family_score(after[arm], fam)
            if b_score is not None and a_score is not None:
                deltas.append(a_score - b_score)
            entry["arms"][arm] = {"before": b_score, "after": a_score}
        if not deltas:
            entry["verdict"] = "indeterminate"
        elif all(d > 0 for d in deltas):
            entry["verdict"] = "improved"
        elif all(d < 0 for d in deltas):
            entry["verdict"] = "regressed"
        else:
            entry["verdict"] = "unchanged"
        out["per_fix"][fix] = entry

    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
