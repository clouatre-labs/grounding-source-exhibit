# Preregistration v2.1 (human-readable mirror of seal-v2.json)

This file mirrors the operative preregistration for reviewers who prefer prose. The machine-readable source of truth is [seal-v2.json](../seal-v2.json) (schema 2.1.0, sealed 2026-11-21, status `sealed-pending-pilot`, issue clouatre-labs/clouatre.ca#2388). In any disagreement, the seal wins.

## Provenance

- Supersedes seal v2.0.0 (tag `prereg-v2`), which was aborted 2026-11-21 when its pilot gate failed `f3_competitiveness`: the original F3 (post → concepts) was mis-preregistered as answerable by kg-json and okf-bundle, but the OKF bundle carries no post → concepts association, so both non-kg arms answered confidently wrong instead of abstaining.
- Supersedes v1 (aborted for a coverage ceiling: llms.txt lists reading chains verbatim, making the primary metric trivially solvable; see `results/raw-v1-aborted/RUN-ABORTED.md`).
- Sealed before any v2.1 item ran; the pilot gate passed first (llms-txt 19/20, kg-json 20/20, okf-bundle 8/20), then the full 63-item run executed.

## Model

`@cf/google/gemma-4-26b-a4b-it`, temperature 0, max completion 4096 tokens, finish reason logged, one deterministic attempt per item, single run.

## Arms (only the payload differs)

| Arm | Payload |
| --- | --- |
| `llms-txt` | frozen `freeze/llms.txt` alone |
| `kg-json` | full frozen `freeze/knowledge-graph.json` text |
| `okf-bundle` | full frozen OKF bundle: `freeze/okf/index.md` plus every cluster index and concept page (33 markdown files), sha256 pinned per file |

## Question families and sealed answerability

63 items across four families, sampled without replacement, families interleaved, deterministic PRNG (stdlib `random.Random`, pilot seed 20261124, full seed 20261125; blinded and plaintext question files committed with hashes in the seal).

- F1: citation edges — answerable by `kg-json` only.
- F2: edgeStats counts — answerable by `kg-json` only.
- F3: forward cluster membership (cluster → post slugs), redesigned after the v2.0 abort — answerable by `kg-json` and `llms-txt`, NOT by `okf-bundle`.
- F4: cluster membership of a post — answerable by all arms.

## Primary scoring rule

Answerable item + correct answer = 1; answerable item + false abstention = 0; unanswerable item + correct abstention = 1; any non-null attempt on an unanswerable item = 0. This makes failure to abstain measurable rather than hidden.

## Statistics

Primary endpoint: overall item-score rate per arm; pairwise McNemar exact tests (binomial two-sided on discordant pairs) with Holm-Bonferroni adjustment across the 3 arm pairs, alpha 0.05. Secondary: paired permutation test on partial credit (10,000 permutations, seed 20261123). Conditional extraction and abstention accuracies are reported as diagnostics. Power: MDD ~22-24pp aggregate at n=63.

## Pilot gate (blocking, n=20, held out)

- Floor: best arm ≥ 3/20.
- Saturation (scoped): okf-bundle ≤ 18/20 ONLY; llms-txt and kg-json are exempt (discrimination is read from the F3/F4 extraction spread).
- F3 competitiveness: ≥ 2 arms with ≥ 2/5 on F3 items.
- llms-txt F4 guard: llms-txt ≥ 2/5 on F4 items (extraction, not abstention).

## Preconditions before any run

`scripts/verify-f3-payloads.py <questions-file>` exits 0 for BOTH the pilot and full questions files (every F3 gold present in each answerable arm's frozen payload; okf-bundle non-answerable at the file level).

## v2.1 reporting fix

`analysis-v2.py` pilot tables print per-family columns using the SAME primary item_score rule as the composite (v2.0 had reported `exact_match` for some family columns, which did not reconcile with the item_score table).
