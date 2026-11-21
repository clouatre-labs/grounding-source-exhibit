#!/usr/bin/env python3
"""Pre-seal assertion (seal v2.1, checklist item 3): verify that every F3
(forward cluster membership) ground-truth value is deterministically
present in each ANSWERABLE arm's frozen payload, and that okf-bundle is
NOT deterministically answerable on F3.

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


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    questions = json.loads(pathlib.Path(sys.argv[1]).read_text())
    snapshot = json.loads(SNAPSHOT.read_text())
    clusters = {c["id"]: c for c in snapshot["clusters"]}
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
          f"for every sampled cluster)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
