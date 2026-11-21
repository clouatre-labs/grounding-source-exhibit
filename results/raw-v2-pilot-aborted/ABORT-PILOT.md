# v2 Pilot ABORTED (2026-11-21)

Pilot gate verdict: `STOP, redesign, re-register` (analysis-v2.py, seal-v2.json preregistered gates).

## Raw tallies (20 items, 5/family, seed 20261121, @cf/google/gemma-4-26b-a4b-it, temperature 0)

| arm | item_score (item_score rule) | F1 | F2 | F3 | F4 |
|---|---|---|---|---|---|
| kg-json | 20/20 | 5/5 | 5/5 | 5/5 | 5/5 |
| llms-txt | 14/20 | 4/5 (abstention credit) | 5/5 (abstention credit) | 0/5 | 5/5 |
| okf-bundle | 7/20 | 0/5 (5 hallucinated attempts, unanswerable) | 5/5 (abstention credit) | 0/5 | 2/5 |

Family columns use the same `item_score` rule as the composite (answerable + correct
= 1; non-null attempt on an unanswerable item = 0; correct abstention = 1). The
composite sums reconcile per arm: llms-txt 4+5+0+5 = 14; okf-bundle 0+5+0+2 = 7.
The earlier chat report showed `exact_match` for F1/F2, which under-counted llms-txt
and over-counted okf-bundle F1; the scoring code itself was correct.

## Gate outcomes

- floor (best arm >= 3/20): PASS (kg-json 20/20)
- saturation (okf-bundle <= 18/20): PASS (7/20)
- f3_competitiveness (>= 2 arms >= 2/5): **FAIL** (only kg-json scored; llms-txt 0/5, okf-bundle 0/5)
- llms-txt_f4_guard: PASS (5/5)

## Root cause (verified against frozen payloads)

F3 (post -> concept slugs) was preregistered as answerable by kg-json AND okf-bundle,
but the okf bundle carries no post->concepts association: the frozen cluster pages
(e.g. `freeze/okf/clusters/governance-oversight/decision-frameworks-ai-delivery.md`)
contain no concept metadata; the association exists only in the kg JSON `concepts`
arrays. Both unanswerable-by-design arms answered F3 confidently wrong
(`abstained=false`), i.e. they hallucinated plausible-but-incorrect concept slugs
rather than abstaining. Scoring was spot-checked and is correct; the failure is a
preregistration error, not a harness bug.

## Consequence

Per seal-v2 `on_failure`: STOP, redesign, re-register. F3 is replaced by forward
cluster membership (cluster -> post slugs), answerable by kg-json and llms-txt
(llms.txt Concept Index matches kg `clusters[].posts` exactly; verified by script),
NOT by okf-bundle (okf cluster indexes list only subsets of kg membership and 2 of
9 kg clusters have no okf directory). Re-registered as seal schema 2.1.0, tag
`prereg-v2.1`.
