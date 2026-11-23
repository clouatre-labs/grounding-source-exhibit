#!/usr/bin/env python3
"""Scorer for grounding-source-exhibit v2.3 full run (seal-v4.json metric
definitions, issue #36).

F1/F3: primary exact = set equality on deduplicated normalized slugs;
partial credit = F1 (dice) overlap 2|A and B| / (|A| + |B|), order-free.
F2: primary exact = both integers match; partial = fraction of the two
integers correct.
F4: primary exact = set equality on normalized cluster labels where the
canonical id->name mapping comes from the frozen snapshot
(--snapshot, default results/v2.3-full/freeze/knowledge-graph.json);
EITHER the cluster id or the cluster name is accepted, normalized
(lowercased, whitespace collapsed); partial credit = dice overlap.

Extraction order (mirrors the runner): bare parse, ```json fenced block,
then balanced JSON objects containing the "answer" key -- FIRST when the
text is plain content, LAST when the --reasoning-fallback flag is given
(reasoning_content scan).

Abstention: answer is null (or unparseable to a non-null answer) counts
as abstained. With --arm, the seal primary item score rule is applied
using the seal answerability map: F1 and F2 answerable by kg-json,
okf-bundle, and okf-index-relevant; F3 answerable by all four arms; F4
answerable by all four arms.

ANSWERABLE and GOLD_DRIFT are loaded from the seal (--seal, default
seal-v4.json at the repo root). GOLD_DRIFT covers the three post-#2414
drift-affected items (q-20261125-015 F3 and q-20261125-062 F1: slug added
to gold; q-20261125-030 F2: gold dict replaced by the live-agreed
{inbound: 4, outbound: 8}); applied identically to every arm, question
file byte-frozen. normalize()/score_answer()/abstention/item_score logic
is byte-identical to recipe/score-v2.py (normalize strips ".json" ONLY;
no .md normalization).

Usage:
    score-v4.py [--seal SEAL] <questions-file> <item-id> <raw-response>
                [--arm A] [--reasoning-fallback] [--snapshot PATH]

    raw-response  path to the raw response text, or "-" for stdin

Prints {"exact_match": 0|1, "partial_credit": float, "abstained": bool,
"item_score": 0|1|null (only with --arm)}.

--selfcheck runs canned spot checks over the four scoring rules (F1/F3
set equality + dice, F2 integer match, F4 label mapping, abstention)
without a questions file and exits 0/1.

Standard library only; uv-run compatible.
"""

import argparse
import json
import pathlib
import re
import sys

DEFAULT_SEAL = pathlib.Path(__file__).resolve().parent.parent / "seal-v4.json"
DEFAULT_SNAPSHOT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "results"
    / "v2.3-full"
    / "freeze"
    / "knowledge-graph.json"
)


def load_seal(seal_path: str):
    with open(seal_path, encoding="utf-8") as f:
        seal = json.load(f)
    answerable = {fam: set(arms) for fam, arms in seal["answerability_map"].items()}
    gold_drift = seal.get("GOLD_DRIFT", {})
    return answerable, gold_drift


def apply_gold_drift(item_id: str, family: str, truth, gold_drift: dict):
    """Return the drift-adjusted truth for this item (or truth unchanged)."""
    drift = gold_drift.get(item_id)
    if drift is None:
        return truth
    if family == "F2":
        if "answer_set" in drift:
            return dict(drift["answer_set"])
        return truth
    if "answer_add" in drift:
        return list(truth) + list(drift["answer_add"])
    return truth


def normalize(slug: str) -> str:
    # Lowercased, .json suffix stripped, whitespace collapsed.
    return " ".join(slug.lower().removesuffix(".json").split())


def norm_set(slugs) -> set:
    return {normalize(s) for s in slugs if isinstance(s, str)}


def cluster_label_map(snapshot: dict) -> dict:
    """Canonical cluster id -> name (and name -> id) labels, from the
    frozen snapshot clusters[]. Accepts either form, normalized."""
    labels: dict[str, str] = {}
    for c in snapshot["clusters"]:
        cid, name = normalize(c["id"]), normalize(c["name"])
        labels[cid] = cid
        labels[name] = cid
    return labels


def _answer_from(obj):
    if not isinstance(obj, dict) or "answer" not in obj:
        return None, False
    return obj["answer"], True


def extract_answer(raw_response: str, reasoning_fallback: bool):
    """Return (answer, found). found=True only when a JSON object with an
    "answer" key parsed successfully."""
    text = raw_response.strip()
    if not text:
        return None, False
    try:
        ans, found = _answer_from(json.loads(text))
        if found:
            return ans, True
    except ValueError:
        pass
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            ans, found = _answer_from(json.loads(match.group(1)))
            if found:
                return ans, True
        except ValueError:
            pass
    # Balanced JSON objects containing the "answer" key; first (content)
    # or last (reasoning fallback).
    found_objs = []
    for start in range(len(text)):
        if text[start] != "{":
            continue
        for end in range(len(text), start, -1):
            if text[end - 1] != "}":
                continue
            try:
                parsed = json.loads(text[start:end])
            except ValueError:
                continue
            ans, found = _answer_from(parsed)
            if found:
                found_objs.append(ans)
                break
    if not found_objs:
        return None, False
    return (found_objs[-1] if reasoning_fallback else found_objs[0]), True


def score_answer(family: str, truth, answer, labels: dict | None = None):
    """Return (exact_match 0|1, partial_credit float)."""
    if family == "F2":
        if not isinstance(truth, dict):
            return 0, 0.0
        if isinstance(answer, dict):
            correct = 0
            for k in ("inbound", "outbound"):
                if isinstance(answer.get(k), int) and answer[k] == truth[k]:
                    correct += 1
            return (1 if correct == 2 else 0), correct / 2
        return 0, 0.0
    # F1 / F3: set equality on deduplicated normalized slugs.
    if family != "F4":
        if not isinstance(truth, list):
            return 0, 0.0
        want = norm_set(truth)
        got = norm_set(answer) if isinstance(answer, list) else set()
    else:
        # F4: truth is cluster ids; accept id or name via the canonical
        # id->name mapping from the frozen snapshot.
        if not isinstance(truth, list) or labels is None:
            return 0, 0.0
        want = {labels[normalize(t)] for t in truth if normalize(t) in labels}
        got = (
            {
                labels[normalize(a)]
                for a in answer
                if isinstance(a, str) and normalize(a) in labels
            }
            if isinstance(answer, list)
            else set()
        )
    if not want:
        return 0, 0.0
    exact = 1 if got == want else 0
    denom = len(want) + len(got)
    dice = (2 * len(want & got) / denom) if denom else 0.0
    return exact, dice


def _selfcheck(gold_drift: dict) -> int:
    """Canned spot checks over the four scoring rules; no questions file."""
    ok = True

    def check(name, got, want):
        nonlocal ok
        if got != want:
            print(
                f"SELFCHECK FAIL: {name}: got {got!r}, want {want!r}", file=sys.stderr
            )
            ok = False

    labels = {"eval-cluster": "eval-cluster", "evaluation reliability": "eval-cluster"}
    # F1/F3: set equality + dice; normalize strips .json only.
    e, p = score_answer("F1", ["a.json"], ["a", "a"], labels)
    check("F1 exact", e, 1)
    check("F1 dice dedup", p, 1.0)
    e, p = score_answer("F3", ["a", "b"], ["b", "a"], labels)
    check("F3 exact order-free", (e, p), (1, 1.0))
    e, p = score_answer("F1", ["a", "b"], ["a", "c"], labels)
    check("F1 partial", (e, round(p, 4)), (0, 0.5))
    # F2: both integers match; partial = fraction correct.
    e, p = score_answer(
        "F2", {"inbound": 4, "outbound": 8}, {"inbound": 4, "outbound": 7}, labels
    )
    check("F2 half", (e, p), (0, 0.5))
    # F4: id or name accepted via the snapshot label map.
    e, p = score_answer("F4", ["eval-cluster"], ["Evaluation Reliability"], labels)
    check("F4 name accepted", (e, p), (1, 1.0))
    # Abstention: null answer abstains; unparseable abstains.
    check("null abstains", extract_answer('{"answer": null}', False), (None, True))
    check("garbage abstains", extract_answer("no json here", False), (None, False))
    # Reasoning fallback: LAST balanced answer object wins.
    two = '{"answer": ["x"]} tail {"answer": ["y"]}'
    check("content first", extract_answer(two, False), (["x"], True))
    check("fallback last", extract_answer(two, True), (["y"], True))
    # GOLD_DRIFT wiring (from the seal): F1/F3 slug add, F2 dict replace.
    d062 = gold_drift.get("q-20261125-062", {})
    check(
        "drift F1 add",
        apply_gold_drift("q-20261125-062", "F1", ["a"], gold_drift),
        ["a"] + d062.get("answer_add", []),
    )
    d030 = gold_drift.get("q-20261125-030", {})
    check(
        "drift F2 set",
        apply_gold_drift(
            "q-20261125-030", "F2", {"inbound": 3, "outbound": 7}, gold_drift
        ),
        d030.get("answer_set", {"inbound": 3, "outbound": 7}),
    )
    if ok:
        print("selfcheck OK")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--seal",
        default=str(DEFAULT_SEAL),
        help="seal-v4.json (answerability map + gold drift)",
    )
    ap.add_argument("questions_file", nargs="?")
    ap.add_argument("item_id", nargs="?")
    ap.add_argument("raw_response", nargs="?")
    ap.add_argument(
        "--arm", choices=["llms-txt", "kg-json", "okf-bundle", "okf-index-relevant"]
    )
    ap.add_argument("--reasoning-fallback", action="store_true")
    ap.add_argument(
        "--snapshot",
        default=str(DEFAULT_SNAPSHOT),
        help="frozen knowledge-graph.json (cluster id->name mapping for F4)",
    )
    ap.add_argument(
        "--selfcheck",
        action="store_true",
        help="canned spot checks over the four scoring rules",
    )
    args = ap.parse_args()

    answerable_map, gold_drift = load_seal(args.seal)
    if args.selfcheck:
        return _selfcheck(gold_drift)
    if not (args.questions_file and args.item_id and args.raw_response):
        ap.error(
            "questions_file, item_id, raw_response are required unless --selfcheck"
        )

    with open(args.questions_file, encoding="utf-8") as f:
        questions = json.load(f)
    item = next((i for i in questions["items"] if i["id"] == args.item_id), None)
    if item is None:
        print(f"ERROR: item {args.item_id} not found", file=sys.stderr)
        return 2
    if args.raw_response == "-":
        raw = sys.stdin.read()
    else:
        with open(args.raw_response, encoding="utf-8") as f:
            raw = f.read()

    answer, found = extract_answer(raw, args.reasoning_fallback)
    abstained = (answer is None) or not found
    labels = None
    if item["family"] == "F4":
        with open(args.snapshot, encoding="utf-8") as f:
            labels = cluster_label_map(json.load(f))
    truth = apply_gold_drift(
        item["id"], item["family"], item["ground_truth"], gold_drift
    )
    exact, partial = score_answer(item["family"], truth, answer, labels)
    result = {
        "exact_match": exact,
        "partial_credit": 0.0 if abstained else partial,
        "abstained": abstained,
    }
    if args.arm:
        answerable = args.arm in answerable_map[item["family"]]
        if answerable:
            # answerable + correct = 1; false abstention = 0
            result["item_score"] = exact
        else:
            # correct abstention = 1; any non-null attempt = 0
            result["item_score"] = 1 if abstained else 0
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
