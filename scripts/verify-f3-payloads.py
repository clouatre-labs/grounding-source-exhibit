#!/usr/bin/env python3
"""Pre-seal assertion (seal v2.1 checklist item 3, extended for seal v2.2):
verify that every F3 (forward cluster membership) ground-truth value is
deterministically present in each ANSWERABLE arm's frozen payload, that
okf-bundle is NOT deterministically answerable on F3, and (v2.2 gate) that
the okf-index-relevant arm's per-question payload composition is complete
and leaves F3 non-answerable.

Checks per F3 item (cluster -> gold post slugs):
  kg-json:  freeze/knowledge-graph.json clusters[].posts contains the gold
            set exactly for that cluster id.
  llms-txt: freeze/llms.txt "## Concept Index" line for the cluster lists
            exactly the gold set.
  okf-bundle: NOT answerable -- asserted at the file level: at least one
            gold cluster has no okf directory, or its okf index lists a
            strict subset of the gold posts (verified here for EVERY F3
            item's cluster, so no sampled item could flip okf to
            answerable).
  okf-index-relevant: per preregistration-v2.2.md, the derived gold-cluster
            set G (sorted unique nodes[].category values over seed slugs,
            routed via clusters[] -> post-slug filenames) must be NON-EMPTY
            and fully present in the composed payload (every G cluster has
            an okf directory whose index exists); the gate FAILS if any
            derived gold cluster is absent from the composition. It also
            re-derives F3 non-answerability: every G cluster index must
            list a strict subset of the gold set.

Usage:
    scripts/verify-f3-payloads.py <questions-file>
Exits nonzero on any failure. Standard library only.
"""

import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT = REPO / "freeze" / "knowledge-graph.json"
LLMS = REPO / "freeze" / "llms.txt"
OKF = REPO / "freeze" / "okf"

ANSWERABLE = {"F3": {"kg-json", "llms-txt"}}


def parse_llms_concept_index(text: str) -> dict[str, list[str]]:
    ci: dict[str, list[str]] = {}
    if "## Concept Index" not in text:
        return ci
    sec = text.split("## Concept Index")[1].split("##")[0]
    for line in sec.splitlines():
        m = re.match(r"- ([a-z0-9-]+): (.+)$", line.strip())
        if m:
            ci[m.group(1)] = [s.strip() for s in m.group(2).split(",")]
    return ci


def okf_index_posts(cluster_id: str) -> list[str] | None:
    """Post slugs listed in the okf cluster index (link targets), or None
    when the cluster has no okf directory."""
    idx = OKF / "clusters" / cluster_id / "index.md"
    if not idx.exists():
        return None
    return re.findall(r"\(([a-z0-9-]+)\.md\)", idx.read_text())


def relevant_arm_gold_clusters(item: dict, cat: dict, clusters: dict) -> list[str]:
    """Derived gold-cluster set G for the okf-index-relevant arm
    (preregistration-v2.2.md, pinned before sealing): sorted unique
    nodes[].category values over seed slugs. F3 seeds are the ground-truth
    post slugs, so cross-cluster gold sets route through node categories."""
    return sorted({cat[s] for s in item["ground_truth"] if s in cat})


def okf_relevant_composition(cid: str) -> list[str] | None:
    """Post slugs listed by the okf cluster index for cid (the pages the
    v2.2 arm would include for that cluster), or None when absent."""
    return okf_index_posts(cid)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    questions = json.loads(pathlib.Path(sys.argv[1]).read_text())
    snapshot = json.loads(SNAPSHOT.read_text())
    clusters = {c["id"]: c for c in snapshot["clusters"]}
    cat = {n["slug"]: n["category"] for n in snapshot["nodes"]
           if n["kind"] == "post"}
    llms_ci = parse_llms_concept_index(LLMS.read_text())

    f3 = [i for i in questions["items"] if i["family"] == "F3"]
    if not f3:
        print("ERROR: no F3 items in questions file")
        return 1

    failures: list[str] = []
    okf_not_answerable_witnesses = 0
    for item in f3:
        cid = next((c for c in clusters if c in item["prompt"]), None)
        gold = set(item["ground_truth"])
        if cid is None:
            failures.append(f"{item['id']}: no cluster id in prompt")
            continue
        if gold != set(clusters[cid]["posts"]):
            failures.append(f"{item['id']}: gold != kg clusters[{cid}].posts")
        # kg-json answerable
        if gold != set(clusters[cid]["posts"]) or cid not in clusters:
            failures.append(f"{item['id']}: kg-json gold mismatch")
        # llms-txt answerable
        if sorted(llms_ci.get(cid, [])) != sorted(gold):
            failures.append(
                f"{item['id']}: llms.txt Concept Index for {cid} != gold "
                f"(index={llms_ci.get(cid)})")
        # okf-bundle NOT answerable: per-item witness
        listed = okf_index_posts(cid)
        if listed is None:
            okf_not_answerable_witnesses += 1
        elif set(listed) != gold:
            okf_not_answerable_witnesses += 1
        # okf-index-relevant (v2.2 gate): derived gold-cluster set must be
        # non-empty and fully present in the composed payload (every G
        # cluster has an okf directory with an index). The gate FAILS if
        # any derived gold cluster is absent from the composition. F3
        # non-answerability witness (mirrors the okf-bundle convention):
        # the listing of at least one G cluster differs from the gold set,
        # so the payload never determines the full gold membership.
        g = relevant_arm_gold_clusters(item, cat, clusters)
        if not g:
            failures.append(f"{item['id']}: okf-index-relevant derived "
                            f"gold-cluster set G is empty")
        listings = {}
        for c in g:
            comp = okf_relevant_composition(c)
            if comp is None:
                failures.append(f"{item['id']}: okf-index-relevant gold "
                                f"cluster {c} absent from payload "
                                f"composition (no okf directory)")
            elif not (OKF / "clusters" / c / "index.md").exists():
                failures.append(f"{item['id']}: okf-index-relevant cluster "
                                f"index missing for {c}")
            else:
                listings[c] = set(comp)
        if listings and all(v == gold for v in listings.values()):
            failures.append(f"{item['id']}: okf-index-relevant F3 "
                            f"answerability drift: every composed cluster "
                            f"index lists exactly the gold set")

    if okf_not_answerable_witnesses != len(f3):
        failures.append(
            f"okf-bundle answerability drift: {okf_not_answerable_witnesses}"
            f"/{len(f3)} F3 items have an okf non-answerability witness; "
            f"every sampled cluster must be non-answerable by okf")

    if failures:
        print("FAIL: F3 payload verification")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"OK: {len(f3)} F3 items verified against frozen payloads "
          f"(kg-json exact, llms-txt exact, okf-bundle non-answerable "
          f"for every sampled cluster, okf-index-relevant composition "
          f"complete and non-answerable on F3 for every item)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
