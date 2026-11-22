# Preregistration v2.2 (human-readable mirror of seal-v3.json)

This file mirrors the operative preregistration for reviewers who prefer prose. The machine-readable source of truth is [seal-v3.json](../seal-v3.json) (schema 2.2.0, sealed before any v2.2 item ran, issue clouatre-labs/clouatre.ca#2388). In any disagreement, the seal wins.

## Provenance

- Extends seal v2.1 (seal-v2.json, schema 2.1.0, sealed 2026-11-21): the v2.1 full run is complete and reported in [results/findings.md](../results/findings.md). The whole-bundle `okf-bundle` arm lost to both other arms (31/63, Holm p < 1e-5) with 23/63 truncations, motivating a medium-tier OKF delivery-mode arm that carries only the index plus the pages relevant to each question.
- Additive extension: the three v2.1 arms, question sets, seeds, prompts, scoring rule, model, and 4096-token completion budget are unchanged and remain governed by seal-v2.json. v2 artifacts and the frozen `freeze/` tree are byte-identical.

## Model

`@cf/google/gemma-4-26b-a4b-it`, temperature 0, max completion 4096 tokens, finish reason logged, one deterministic attempt per item, single run. Identical to v2.1.

## Question sets

The same sealed v2.1 question sets are reused unchanged: pilot `ground-truth/pilot-v2.1.json` (seed 20261124, n=20, held out, sha256 1be8cbcd7f80b28a4ce7a44801782010551460e7d3e1eb934a54dc3f343d65a4) and full `ground-truth/full-v2.1.json` (seed 20261125, n=63, sha256 10638a1a8dfec0a87f3efa851e18d6c63dd87fd7173c31966c89711a0abeea12). Because the per-question payload composition is derived from ground truth (below), the new arm consumes the plaintext question files; both were already unblinded with the completed v2.1 run, so no blinding purpose remains.

## New arm (only addition): `okf-index-relevant`

One arm is added under this seal; the v2.1 arms keep verifying against seal-v2.json (SEAL is parameterized in `recipe/run-bench.sh`, default per arm; `SEAL_FILE` env overrides).

### Per-question payload rule (pinned BEFORE sealing)

For each question item, the grounding payload is `freeze/okf/index.md` plus, for every cluster in the question's derived gold-cluster set G, that cluster's `freeze/okf/clusters/<cluster>/index.md` plus the concept pages that index links (post-slug filenames), enumerated with `sort -u` semantics (sorted, deduplicated). G is derived deterministically from the frozen snapshot `freeze/knowledge-graph.json` via `nodes[].category -> clusters[] -> post-slug filenames` (concept pages are post slugs, NOT `nodes[].concepts` slugs):

- F1 (citation edges): seed slugs = the prompt's source post slug PLUS every ground-truth (gold linked) post slug.
- F2 (edgeStats counts): seed slugs = the prompt's source post slug.
- F3 (forward cluster membership): seed slugs = every ground-truth post slug. This routes cross-cluster gold sets through node categories: a gold set spanning several kg clusters (for example `multi-agent-architecture`, `cost-roi`, `governance-oversight`) yields the union of those clusters' pages. Prompt-named clusters without an okf directory (`legacy-modernization`, `subagent-orchestration-tooling` — no `nodes[].category` maps to them) contribute nothing directly; their gold posts route through the categories the okf tree actually carries.
- F4 (cluster membership): seed slugs = the union of `clusters[].posts` over every ground-truth cluster id.

G = sorted unique `nodes[seed].category` values over the seed slugs (all 24 post categories are among the 7 okf-backed cluster ids, so G is never empty and every derived cluster has an okf directory — asserted per item by the extended verification gate). Assembly order: `index.md`, then per cluster in sorted order its `index.md` then its linked concept pages in sorted order. The composition is byte-deterministic; per-question composed-payload sha256 pins are frozen in `seal-v3.json` `per_question_payloads` for all 63 full-run items.

### Sealed answerability for `okf-index-relevant`

Derived from the actual payload composition and verified per item by the extended `scripts/verify-f3-payloads.py` gate:

- F1: NOT answerable. The queried post's page (always present: the prompt slug's category is in G) carries a symmetric "Related" link list that cannot distinguish outbound citation edges from inbound, and gold targets may fall outside G.
- F2: NOT answerable. OKF pages carry no inbound/outbound edge counts.
- F3: NOT answerable. For every sampled F3 gold set, the corresponding cluster index lists a strict subset of the kg membership (gate-verified per item), so the payload never determines the full gold set.
- F4: answerable (same coarse per-family convention as seal-v2.json, where F4 is answerable by every arm). Cluster indexes in G list the post slugs of every okf-backed gold cluster; membership in the two okf-absent clusters is no less derivable than it was for the v2.1 `okf-bundle` arm, which carries strictly more pages.

Answerability map (v2.2 delta only): F4 answerable by `llms-txt`, `kg-json`, `okf-bundle`, and `okf-index-relevant`; F1/F2/F3 unchanged.

## Primary scoring rule

Unchanged from v2.1: answerable item + correct answer = 1; answerable item + false abstention = 0; unanswerable item + correct abstention = 1; any non-null attempt on an unanswerable item = 0. Applied with the v2.2 answerability map via `recipe/score-v2.py`.

## Pilot gate (blocking, n=20, held out) and statistics

Identical thresholds and statistics to seal-v2.json, evaluated over the four arm pairs including `okf-index-relevant` (Holm-Bonferroni across 6 pairs, alpha 0.05; pilot floor best arm >= 3/20; F3 competitiveness >= 2 arms with >= 2/5; llms-txt F4 guard unchanged). The headline comparison is scoped: `okf-index-relevant` extraction accuracy, abstention accuracy, and truncation count versus `okf-bundle` (same okf surface, smaller payload) and `llms-txt` (the non-kg frontier).

## Preconditions before any run

1. `scripts/verify-f3-payloads.py <questions-file>` exits 0 for BOTH the pilot and full questions files: every v2.1 condition (kg-json exact, llms-txt exact, okf-bundle non-answerable per sampled cluster) PLUS the new-arm gate (every F3 item's derived gold-cluster set present in the composed payload; strict-subset non-answerability witness per item).
2. `recipe/run-bench.sh` aborts loudly on any frozen_payloads sha256 mismatch at run start (seal-v2.json for v2 arms, seal-v3.json for `okf-index-relevant`).
3. Every composed payload sha256 matches its `per_question_payloads` pin (determinism check; the assembly is byte-stable across repeated runs).
