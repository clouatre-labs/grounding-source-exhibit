#!/usr/bin/env python3
"""Scorer for the grounding-source exhibit.

Exact port of resolveChainSequence from clouatre-labs/clouatre.ca
experiments/src/bench-do.ts (pinned commit 74105922), plus a partial-credit
prefix metric.

Usage:
    score.py <kg-file> <chain-id> <raw-response-text>

    kg-file            path to the fetched knowledge-graph.json document
    chain-id           readingChains entry id (ground truth key)
    raw-response-text  path to the run's raw_response file, or "-" for stdin

Prints {"exact_match": 0|1, "partial_credit": float|null}.

Standard library only; uv-run compatible.
"""

import json
import sys


def resolve_chain_sequence(kg_text: str, chain: str) -> list[str] | None:
    """Exact port of resolveChainSequence (bench-do.ts:262-285).

    Returns the expected slug sequence for `chain`, or null when the
    document, readingChains array, entry, or sequence is missing/malformed.
    """
    try:
        parsed = json.loads(kg_text)
    except ValueError:
        return None
    chains = parsed.get("readingChains") if isinstance(parsed, dict) else None
    if not isinstance(chains, list):
        return None
    for entry in chains:
        if not isinstance(entry, dict):
            continue
        if entry.get("id") != chain:
            continue
        sequence = entry.get("sequence")
        if not isinstance(sequence, list):
            return None
        if all(isinstance(slug, str) for slug in sequence):
            return sequence
        return None
    return None


def extract_sequence(raw_response: str) -> list[str] | None:
    """Extract a {"sequence": [...]} array of strings from the model output.

    Scans for the first JSON object whose "sequence" field is an array of
    strings (the model may wrap the JSON in prose or code fences).
    """
    text = raw_response.strip()
    if not text:
        return None
    # Direct parse first.
    try:
        parsed = json.loads(text)
        seq = parsed.get("sequence") if isinstance(parsed, dict) else None
        if isinstance(seq, list) and all(isinstance(s, str) for s in seq):
            return seq
    except ValueError:
        pass
    # Scan for embedded JSON objects starting at each '{'.
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
            seq = parsed.get("sequence") if isinstance(parsed, dict) else None
            if isinstance(seq, list) and all(isinstance(s, str) for s in seq):
                return seq
    return None


def score(kg_file: str, chain_id: str, raw_response_text: str) -> dict:
    with open(kg_file, encoding="utf-8") as f:
        kg_text = f.read()
    expected = resolve_chain_sequence(kg_text, chain_id)
    if expected is None:
        return {"exact_match": 0, "partial_credit": None}
    predicted = extract_sequence(raw_response_text)
    if predicted is None:
        return {"exact_match": 0, "partial_credit": None}
    matches = 0
    for got, want in zip(predicted, expected):
        if got == want:
            matches += 1
        else:
            break
    partial = matches / len(expected) if expected else None
    exact = 1 if predicted == expected else 0
    return {"exact_match": exact, "partial_credit": partial}


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    kg_file, chain_id, raw_arg = sys.argv[1], sys.argv[2], sys.argv[3]
    if raw_arg == "-":
        raw = sys.stdin.read()
    else:
        with open(raw_arg, encoding="utf-8") as f:
            raw = f.read()
    print(json.dumps(score(kg_file, chain_id, raw)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
