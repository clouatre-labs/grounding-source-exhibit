#!/usr/bin/env python3
"""Scorer for grounding-source-exhibit v2 (seal-v2.json metric definitions).

F1/F3: primary exact = set equality on deduplicated normalized slugs;
partial credit = F1 (dice) overlap 2|A and B| / (|A| + |B|), order-free.
F2: primary exact = both integers match; partial = fraction of the two
integers correct.
F4: primary exact = set equality on normalized cluster labels where the
canonical id->name mapping comes from the frozen snapshot
(--snapshot, default freeze/knowledge-graph.json); EITHER the cluster id
or the cluster name is accepted, normalized (lowercased, whitespace
collapsed); partial credit = dice overlap.

Extraction order (mirrors the runner): bare parse, ```json fenced block,
then balanced JSON objects containing the "answer" key -- FIRST when the
text is plain content, LAST when the --reasoning-fallback flag is given
(reasoning_content scan).

Abstention: answer is null (or unparseable to a non-null answer) counts
as abstained. With --arm, the seal-v2.1 primary item score rule is applied
using the answerability map: F1 and F2 answerable only by kg-json; F3
(forward cluster membership) answerable by kg-json and llms-txt, NOT by
okf-bundle (okf cluster indexes list only subsets of kg membership and 2
of 9 kg clusters have no okf directory); F4 answerable by ALL v2.1 arms.
Under seal-v3.json (schema 2.2.0, preregistration-v2.2.md) the additional
arm okf-index-relevant (per-question payload: okf index + the cluster
indexes and concept pages named by the item's derived gold-cluster set)
is F4-answerable, per the same coarse per-family convention; its F1/F2/F3
entries are unchanged (F3 non-answerability derived from actual payload
composition and gate-verified by scripts/verify-f3-payloads.py).

Usage:
    score-v2.py <questions-file> <item-id> <raw-response> [--arm A]
                [--reasoning-fallback] [--snapshot PATH]

    raw-response  path to the raw response text, or "-" for stdin

Prints {"exact_match": 0|1, "partial_credit": float, "abstained": bool,
"item_score": 0|1|null (only with --arm)}.

Standard library only; uv-run compatible.
"""

import argparse
import json
import pathlib
import re
import sys

# Pilot v2.3 map: re-derived deterministically against the production
# bundle fetched 2026-11-22 (see pilot-seal.json answerability_derivation).
# F1 flips: okf concept pages now carry directional cites:/cited-by: edges
# matching gold for all 5 pilot items. F2 flips: per-page edgeStats match
# gold on all 5 pilot items. F3 flips: 4/5 pilot cluster indexes list
# exactly the gold set (q-20261124-007 via drift-adjusted gold).
ANSWERABLE = {
    "F1": {"kg-json", "okf-bundle", "okf-index-relevant"},
    "F2": {"kg-json", "okf-bundle", "okf-index-relevant"},
    "F3": {"kg-json", "llms-txt", "okf-bundle", "okf-index-relevant"},
    "F4": {"llms-txt", "kg-json", "okf-bundle", "okf-index-relevant"},
}

# Gold drift (post published after sealing; joined evaluation-reliability).
# Applied identically to every arm; question file stays byte-frozen.
GOLD_DRIFT = {
    "q-20261124-007": ["frontmatter-okf-knowledge-graph"],
}

DEFAULT_SNAPSHOT = pathlib.Path(__file__).resolve().parent / \
    "freeze" / "knowledge-graph.json"


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
                if isinstance(answer.get(k), int) and \
                        answer[k] == truth[k]:
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
        want = {labels[normalize(t)] for t in truth
                if normalize(t) in labels}
        got = ({labels[normalize(a)] for a in answer
                if isinstance(a, str) and normalize(a) in labels}
               if isinstance(answer, list) else set())
    if not want:
        return 0, 0.0
    exact = 1 if got == want else 0
    denom = len(want) + len(got)
    dice = (2 * len(want & got) / denom) if denom else 0.0
    return exact, dice


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("questions_file")
    ap.add_argument("item_id")
    ap.add_argument("raw_response")
    ap.add_argument("--arm", choices=["llms-txt", "kg-json", "okf-bundle",
                                      "okf-index-relevant"])
    ap.add_argument("--reasoning-fallback", action="store_true")
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT),
                    help="frozen knowledge-graph.json (cluster id->name "
                         "mapping for F4)")
    args = ap.parse_args()

    with open(args.questions_file, encoding="utf-8") as f:
        questions = json.load(f)
    item = next((i for i in questions["items"]
                 if i["id"] == args.item_id), None)
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
    truth = item["ground_truth"]
    if item["family"] == "F3" and item["id"] in GOLD_DRIFT:
        truth = list(truth) + GOLD_DRIFT[item["id"]]
    exact, partial = score_answer(item["family"], truth,
                                  answer, labels)
    result = {
        "exact_match": exact,
        "partial_credit": 0.0 if abstained else partial,
        "abstained": abstained,
    }
    if args.arm:
        answerable = args.arm in ANSWERABLE[item["family"]]
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
