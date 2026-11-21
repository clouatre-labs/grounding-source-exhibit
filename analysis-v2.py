#!/usr/bin/env python3
"""Sealed analysis for grounding-source-exhibit v2 (seal-v2.json).

Reads results/raw-v2/<arm>/run-*.json plus the full-run questions file,
computes per-arm primary overall exact-match rates, pairwise McNemar
exact tests (binomial two-sided on discordant pairs) with Holm-Bonferroni
adjustment across the 3 arm pairs, secondary paired permutation tests on
partial credit (10000 permutations, seed 20261123), conditional
extraction and abstention accuracy diagnostics, and per-arm truncation
rates (finish_reason == "length"). Writes results/analysis-v2.json and
prints a markdown summary.

Standard library only; uv-run compatible.
"""

import argparse
import itertools
import json
import math
import pathlib
import random
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parent
RAW = REPO / "results" / "raw-v2"
OUT = REPO / "results" / "analysis-v2.json"
ARMS = ["llms-txt", "kg-json", "okf-bundle"]
PERM_SEED = 20261123
PERMS = 10000


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value: binomial(n, 0.5) tail at min(b,c),
    doubled (capped at 1)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, returned in input order."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adjusted = [0.0] * m
    running = 0.0
    prev = 0.0
    for rank, idx in enumerate(order):
        adj = min(1.0, (m - rank) * pvals[idx])
        running = max(prev, adj)
        prev = running
        adjusted[idx] = running
    return adjusted


def paired_permutation(xs, ys, seed: int = PERM_SEED, perms: int = PERMS):
    """Two-sided paired permutation test on partial-credit differences."""
    n = len(xs)
    if n == 0:
        return 1.0, 0.0
    diffs = [x - y for x, y in zip(xs, ys)]
    observed = abs(sum(diffs))
    rng = random.Random(seed)
    count = 0
    for _ in range(perms):
        total = 0
        for d in diffs:
            total += d if rng.random() < 0.5 else -d
        if abs(total) >= observed - 1e-12:
            count += 1
    return count / perms, sum(diffs) / n


def load_arm(arm: str, questions: dict):
    items = {i["id"]: i for i in questions["items"]}
    records = []
    for path in sorted((RAW / arm).glob("run-*.json")):
        rec = json.loads(path.read_text())
        item = items.get(rec.get("item_id"))
        if item is None:
            raise SystemExit(f"ERROR: unknown item_id {rec.get('item_id')} "
                             f"in {path}")
        records.append((item, rec))
    records.sort(key=lambda t: t[0]["id"])
    return records


def summarize_arm(arm: str, records):
    n = len(records)
    item_scores = [1 if r.get("item_score") is True or
                   r.get("item_score") == 1 else 0 for _, r in records]
    exact = [1 if r.get("exact_match") is True or
             r.get("exact_match") == 1 else 0 for _, r in records]
    partials = [float(r["partial_credit"]) for _, r in records
                if r.get("partial_credit") is not None]
    trunc = sum(1 for _, r in records if r.get("finish_reason") == "length")

    ans_idx = [k for k, (item, _) in enumerate(records)
               if arm in _answerable_for(item["family"])]
    unans_idx = [k for k in range(n) if k not in set(ans_idx)]

    def cond(idxs, scores):
        sub = [scores[k] for k in idxs]
        return {"n": len(sub),
                "accuracy": (sum(sub) / len(sub)) if sub else None}

    return {
        "n": n,
        "item_score_count": sum(item_scores),
        "item_score_rate": (sum(item_scores) / n) if n else None,
        "conditional_extraction": cond(ans_idx, item_scores),
        "conditional_abstention": cond(unans_idx, item_scores),
        "truncations": trunc,
        "truncation_rate": (trunc / n) if n else None,
        "_item_scores": item_scores,
        "_partials": partials,
    }


def _answerable_for(family: str) -> set:
    # Mirrors recipe/score-v2.py ANSWERABLE.
    return {"F1": {"kg-json"}, "F2": {"kg-json"},
            "F3": {"kg-json", "okf-bundle"},
            "F4": {"llms-txt", "kg-json", "okf-bundle"}}[family]


def pilot_gate(pilot_questions: dict) -> int:
    """Evaluate the seal-v2 pilot gate from pilot run records.

    Gates (seal-v2.json pilot_gate):
      floor:               BLOCKING: best arm >= 3/20
      saturation (scoped): BLOCKING: okf-bundle <= 18/20 ONLY
                           (llms-txt and kg-json are EXEMPT from the
                           saturation cap; discrimination is read from
                           the F3/F4 extraction spread)
      f3_competitiveness:  BLOCKING: >= 2 arms with >= 2/5 on F3 items
      llms-txt_f4_guard:   BLOCKING: llms-txt >= 2/5 on F4 items
                           (extraction, not abstention)
    """
    n_pilot = len(pilot_questions["items"])
    per_arm = {}
    for arm in ARMS:
        records = load_arm(arm, pilot_questions)
        if not records:
            raise SystemExit(f"ERROR: no pilot records under "
                             f"results/raw-v2/{arm}/")
        scores = [1 if r.get("item_score") is True or
                  r.get("item_score") == 1 else 0 for _, r in records]
        f3 = [1 if s == 1 else 0 for (item, _), s in zip(records, scores)
              if item["family"] == "F3"]
        f4 = [1 if s == 1 else 0 for (item, _), s in zip(records, scores)
              if item["family"] == "F4"]
        per_arm[arm] = {
            "n": len(scores),
            "item_score": sum(scores),
            "f3_score": sum(f3),
            "f3_n": len(f3),
            "f4_score": sum(f4),
            "f4_n": len(f4),
        }

    best = max(v["item_score"] for v in per_arm.values())
    floor_ok = best >= 3
    # Scoped saturation: only okf-bundle is capped; llms-txt and kg-json
    # are exempt from the cap.
    sat_ok = per_arm["okf-bundle"]["item_score"] <= 18
    f3_competitive = sum(1 for v in per_arm.values()
                         if v["f3_n"] and v["f3_score"] >= 2) >= 2
    # NEW: llms-txt compliance guard on F4 (extraction, not abstention).
    f4_guard_ok = per_arm["llms-txt"]["f4_score"] >= 2
    ok = floor_ok and sat_ok and f3_competitive and f4_guard_ok

    print("# Pilot gate (seal-v2, scoped saturation)\n")
    for arm, v in per_arm.items():
        print(f"- {arm}: item_score={v['item_score']}/{v['n']}, "
              f"F3={v['f3_score']}/{v['f3_n']}, "
              f"F4={v['f4_score']}/{v['f4_n']}")
    print(f"\nfloor (best arm >= 3/{n_pilot}): "
          f"{'PASS' if floor_ok else 'FAIL'} (best={best})")
    print(f"saturation (okf-bundle <= 18/20 ONLY; llms-txt and "
          f"kg-json exempt): "
          f"{'PASS' if sat_ok else 'FAIL'} "
          f"(okf-bundle={per_arm['okf-bundle']['item_score']}, "
          f"llms-txt={per_arm['llms-txt']['item_score']} exempt, "
          f"kg-json={per_arm['kg-json']['item_score']} exempt)")
    print(f"f3_competitiveness (>= 2 arms with >= 2/5 on F3): "
          f"{'PASS' if f3_competitive else 'FAIL'}")
    print(f"llms-txt_f4_guard (llms-txt >= 2/5 on F4, extraction): "
          f"{'PASS' if f4_guard_ok else 'FAIL'} "
          f"(F4={per_arm['llms-txt']['f4_score']}/"
          f"{per_arm['llms-txt']['f4_n']})")
    verdict = "PROCEED" if ok else "STOP, redesign, re-register"
    print(f"\nverdict: {verdict}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--questions", required=True,
                    help="full-run questions.json (plaintext ground truth)")
    ap.add_argument("--pilot-questions",
                    help="optional pilot questions.json; when given, "
                         "evaluate the seal-v2 pilot gate from the pilot "
                         "run records under results/raw-v2/<arm>/")
    args = ap.parse_args()

    if args.pilot_questions:
        return pilot_gate(json.loads(
            pathlib.Path(args.pilot_questions).read_text()))
    questions = json.loads(pathlib.Path(args.questions).read_text())

    arms = {}
    for arm in ARMS:
        records = load_arm(arm, questions)
        if not records:
            print(f"no records under results/raw-v2/{arm}/ yet; "
                  "run the bench first (recipe/run-bench.sh)")
            return
        arms[arm] = summarize_arm(arm, records)

    summary = {}
    for arm, s in arms.items():
        summary[arm] = {k: v for k, v in s.items() if not k.startswith("_")}

    pairs = list(itertools.combinations(ARMS, 2))
    comparisons = {}
    raw_p_mcnemar = []
    for a, b in pairs:
        sa, sb = arms[a], arms[b]
        discordant_b = sum(1 for x, y in zip(sa["_item_scores"],
                                             sb["_item_scores"])
                           if x == 1 and y == 0)
        discordant_c = sum(1 for x, y in zip(sa["_item_scores"],
                                             sb["_item_scores"])
                           if x == 0 and y == 1)
        p_m = mcnemar_exact(discordant_b, discordant_c)
        p_perm, mean_diff = paired_permutation(sa["_partials"],
                                               sb["_partials"])
        comparisons[f"{a}_vs_{b}"] = {
            "mcnemar_exact": {
                "discordant": [discordant_b, discordant_c],
                "p_value": p_m,
            },
            "paired_permutation_partial_credit": {
                "permutations": PERMS,
                "seed": PERM_SEED,
                "mean_difference": mean_diff,
                "p_value": p_perm,
            },
        }
        raw_p_mcnemar.append(p_m)

    adjusted = holm(raw_p_mcnemar)
    for pair, adj in zip(comparisons, adjusted):
        comparisons[pair]["mcnemar_exact"]["p_value_holm"] = adj
        comparisons[pair]["mcnemar_exact"]["significant_at_0.05"] = \
            adj < 0.05

    result = {
        "schema_version": "2.0.0",
        "experiment": "grounding-source-exhibit-v2",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "statistics": {
            "primary": "overall exact match; pairwise McNemar exact test "
                       "with Holm-Bonferroni across 3 arm pairs, alpha 0.05",
            "secondary": "paired permutation test on partial credit "
                         "(10000 permutations, seed 20261123)",
            "exploratory": "per-family breakdowns",
        },
        "arms": summary,
        "comparisons": comparisons,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")

    print(f"# Analysis v2 summary ({result['analyzed_at']})\n")
    for arm, s in summary.items():
        print(f"## {arm}: n={s['n']}, "
              f"item_score={s['item_score_count']} "
              f"({s['item_score_rate']:.4f}), "
              f"truncations={s['truncations']}, "
              f"extraction_acc={s['conditional_extraction']['accuracy']}, "
              f"abstention_acc={s['conditional_abstention']['accuracy']}")
    print()
    for pair, c in comparisons.items():
        m = c["mcnemar_exact"]
        p = c["paired_permutation_partial_credit"]
        print(f"- {pair}: McNemar discordant={m['discordant']}, "
              f"p={m['p_value']:.4f}, Holm p={m['p_value_holm']:.4f}; "
              f"permutation p={p['p_value']:.4f}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
