#!/usr/bin/env python3
"""Deterministic question generator for grounding-source-exhibit v2.

Samples four question families from the frozen knowledge-graph.json
snapshot, family-interleaved, without replacement per family:

- F1: citation edges from posts with >=1 outbound citation edge
      (ground truth: linked post slugs, edge list in snapshot document order)
- F2: edgeStats inbound/outbound link counts
- F3: node.concepts arrays (3-4 concept slugs)
- F4: cluster membership for a post (ground truth: the set of cluster
      identifiers whose clusters[].posts array contains the slug, in
      cluster document order; all 24 posts are eligible)

Every ground truth is validated against the snapshot before writing.

Usage:
    generate-questions-v2.py --snapshot freeze/knowledge-graph.json \
        --seed 20261121 --out questions.json [--blinded] [--validate]

    --blinded  writes ground-truth-blinded.json (id, family, prompt only)
               next to --out and prints the sha256 of the full questions file
    --validate re-checks an existing questions.json against the snapshot

Standard library only; uv-run compatible.
"""

import argparse
import hashlib
import json
import pathlib
import random
import sys

PROMPTS = {
    "F1": (
        'Which posts does the post "{title}" (slug {slug}) link to, '
        'according to the payload? Respond with JSON '
        '{{"answer": [<linked post slugs>]}}. If the payload does not '
        'determine the answer, respond with {{"answer": null}}.'
    ),
    "F2": (
        "How many inbound and outbound links does the post with slug "
        "{slug} have according to the payload? Respond with JSON "
        '{{"answer": {{"inbound": <int>, "outbound": <int>}}}}. If the '
        'payload does not determine the answer, respond with '
        '{{"answer": null}}.'
    ),
    "F3": (
        "Which posts belong to the cluster with id {slug} according to "
        'the payload? Respond with JSON '
        '{{"answer": [<post slugs>]}}. If the payload does not '
        'determine the answer, respond with {{"answer": null}}.'
    ),
    "F4": (
        "Which cluster(s) does the post with slug {slug} belong to, "
        "according to the payload? Respond with JSON "
        '{{"answer": [<cluster id or name>]}}. If the payload does not '
        'determine the answer, respond with {{"answer": null}}.'
    ),
}

# F3 is capped at 7: the sampling unit is the cluster; 2 of the 9 frozen
# clusters (governance-oversight, agent-infrastructure) are excluded
# because their okf cluster indexes list the FULL kg membership, which
# would make okf-bundle deterministically answerable on those items and
# contradict the seal answerability map. Enforced per-item by
# scripts/verify-f3-payloads.py. F3 v2.1: forward cluster membership
# (replaces the aborted v2.0 post->concepts family; see
# results/raw-v2-pilot-aborted/ABORT-PILOT.md).
F3_EXCLUDED_CLUSTERS = {"governance-oversight", "agent-infrastructure"}
PER_FAMILY = {"pilot": {"F1": 5, "F2": 5, "F3": 5, "F4": 5},
              "full": {"F1": 20, "F2": 20, "F3": 7, "F4": 16}}


def clusters_for_post(snapshot: dict, slug: str) -> list[str]:
    """Cluster ids whose clusters[].posts contains the slug, in snapshot
    cluster document order."""
    return [c["id"] for c in snapshot["clusters"]
            if slug in c.get("posts", [])]


def load_snapshot(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize(slug: str) -> str:
    return slug.lower().removesuffix(".json")


def posts(snapshot: dict) -> list[dict]:
    return [n for n in snapshot["nodes"] if n.get("kind") == "post"]


def outbound_edges(snapshot: dict) -> dict[str, list[str]]:
    """slug -> linked post slugs, in snapshot edge document order."""
    out: dict[str, list[str]] = {}
    for edge in snapshot["edges"]:
        if edge.get("type") != "citation":
            continue
        out.setdefault(edge["from"], []).append(edge["to"])
    return out


def sample_family(snapshot: dict, family: str, rng: random.Random,
                  n: int) -> list[dict]:
    posts_all = posts(snapshot)
    if family == "F1":
        out_edges = outbound_edges(snapshot)
        eligible = [p for p in posts_all
                    if len(out_edges.get(p["slug"], [])) >= 1]
    elif family == "F2":
        eligible = [p for p in posts_all
                    if isinstance(p.get("edgeStats"), dict)]
    elif family == "F4":
        # All posts are eligible; snapshot document order is the tiebreak
        # (posts() preserves document order).
        eligible = [p for p in posts_all
                    if clusters_for_post(snapshot, p["slug"])]
    else:  # F3
        # Sampling unit is the cluster; eligible = clusters with >=2 posts
        # not excluded by F3_EXCLUDED_CLUSTERS (okf-full-listing clusters).
        eligible = [c for c in snapshot["clusters"]
                    if len(c.get("posts", [])) >= 2
                    and c["id"] not in F3_EXCLUDED_CLUSTERS]
    if len(eligible) < n:
        raise SystemExit(
            f"ERROR: family {family} has {len(eligible)} eligible posts, "
            f"need {n}")
    chosen = rng.sample(eligible, n)
    items = []
    for target in chosen:
        if family == "F3":
            slug = target["id"]
            title = slug  # cluster id stands in; the prompt uses the id
        else:
            slug = target["slug"]
            title = target.get("title", slug)
        if family == "F1":
            truth = [normalize(s) for s in out_edges[slug]]
        elif family == "F2":
            truth = {"inbound": target["edgeStats"]["inbound"],
                     "outbound": target["edgeStats"]["outbound"]}
        elif family == "F4":
            truth = clusters_for_post(snapshot, slug)
        else:
            # F3: cluster post membership, in snapshot document order.
            truth = list(target["posts"])
        if family == "F2":
            ok = isinstance(truth["inbound"], int) and \
                isinstance(truth["outbound"], int)
        else:
            ok = isinstance(truth, list) and len(truth) >= 1 and \
                all(isinstance(s, str) and s for s in truth)
        if not ok:
            raise SystemExit(f"ERROR: empty/invalid ground truth for {slug}")
        items.append({
            "family": family,
            "slug": slug,
            "prompt": PROMPTS[family].format(title=title, slug=slug),
            "ground_truth": truth,
        })
    return items


def generate(snapshot: dict, seed: int, n_per_family: dict) -> dict:
    rng = random.Random(seed)
    by_family = {
        fam: sample_family(snapshot, fam, rng, n_per_family[fam])
        for fam in ("F1", "F2", "F3", "F4")
    }
    # Family-interleaved in the question file.
    items = []
    i = 0
    while any(by_family.values()):
        for fam in ("F1", "F2", "F3", "F4"):
            if by_family[fam]:
                item = by_family[fam].pop(0)
                i += 1
                items.append({
                    "id": f"q-{seed}-{i:03d}",
                    "family": item["family"],
                    "prompt": item["prompt"],
                    "ground_truth": item["ground_truth"],
                })
    return {
        "seed": seed,
        "snapshot_sha256": hashlib.sha256(
            pathlib.Path(SNAPSHOT_PATH).read_bytes()).hexdigest(),
        "items": items,
    }


def validate_questions(questions: dict, snapshot: dict) -> None:
    out_edges = outbound_edges(snapshot)
    by_slug = {p["slug"]: p for p in posts(snapshot)}
    clusters_by_id = {c["id"]: c for c in snapshot["clusters"]}
    for item in questions["items"]:
        prompt = item["prompt"]
        truth = item["ground_truth"]
        if item["family"] == "F3":
            cid = next((c for c in clusters_by_id if c in prompt), None)
            if cid is None:
                raise SystemExit(f"ERROR: no cluster id in prompt "
                                 f"{item['id']}")
            if cid in F3_EXCLUDED_CLUSTERS:
                raise SystemExit(f"ERROR: F3 sampled excluded cluster "
                                 f"{cid}")
            want = list(clusters_by_id[cid]["posts"])
            if truth != want or len(want) < 2:
                raise SystemExit(f"ERROR: F3 mismatch for cluster {cid}")
            continue
        slug = None
        for s in by_slug:
            if s in prompt:
                slug = s
                break
        if slug is None:
            raise SystemExit(f"ERROR: no slug found in prompt {item['id']}")
        p = by_slug[slug]
        truth = item["ground_truth"]
        if item["family"] == "F1":
            want = [normalize(s) for s in out_edges.get(slug, [])]
            if truth != want:
                raise SystemExit(f"ERROR: F1 mismatch for {slug}")
        elif item["family"] == "F2":
            want = {"inbound": p["edgeStats"]["inbound"],
                    "outbound": p["edgeStats"]["outbound"]}
            if truth != want:
                raise SystemExit(f"ERROR: F2 mismatch for {slug}")
        elif item["family"] == "F4":
            want = clusters_for_post(snapshot, slug)
            if truth != want or not want:
                raise SystemExit(f"ERROR: F4 mismatch for {slug}")
        else:
            want = [normalize(s) for s in out_edges.get(slug, [])]
            if truth != want:
                raise SystemExit(f"ERROR: F1 mismatch for {slug}")


SNAPSHOT_PATH = ""


def main() -> int:
    global SNAPSHOT_PATH
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["pilot", "full"], default="full")
    ap.add_argument("--blinded", action="store_true")
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args()

    snapshot = load_snapshot(args.snapshot)
    n = PER_FAMILY[args.mode]
    if args.validate:
        with open(args.out, encoding="utf-8") as f:
            questions = json.load(f)
        validate_questions(questions, snapshot)
        print("OK: all ground truths validate against the snapshot")
        return 0

    SNAPSHOT_PATH = args.snapshot
    questions = generate(snapshot, args.seed, n)
    validate_questions(questions, snapshot)
    out = pathlib.Path(args.out)
    out.write_text(json.dumps(questions, indent=2) + "\n")
    print(f"wrote {out} ({len(questions['items'])} items, "
          f"seed {args.seed})")

    if args.blinded:
        blinded = {
            "seed": questions["seed"],
            "snapshot_sha256": questions["snapshot_sha256"],
            "questions_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
            "items": [{"id": it["id"], "family": it["family"],
                       "prompt": it["prompt"]}
                      for it in questions["items"]],
        }
        blinded_path = out.with_name("ground-truth-blinded.json")
        blinded_path.write_text(json.dumps(blinded, indent=2) + "\n")
        print(f"wrote {blinded_path} (blinded)")
        print(f"questions.json sha256: {blinded['questions_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
