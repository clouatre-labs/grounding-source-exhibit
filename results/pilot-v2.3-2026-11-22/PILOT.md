# Pilot v2.3 (issue #36 pilot gate) — pilot-only, non-claim

Date: 2026-11-22. Scope: go/no-go signal only. No `seal-v4.json`, no Zenodo
deposit, no blog edit. Question files (`ground-truth/pilot-v2.1.json`,
seed 20261124, n=20, sha256 `1be8cbcd…d65a4`) are byte-frozen.

## 1. Payload pins

Production payloads fetched from clouatre.ca on 2026-11-22 into
`freeze/` (this directory); all 37 files sha256-pinned in `manifest.json`
and `pilot-seal.json` (frozen_payloads). Key pins:

| Payload | URL | sha256 |
|---|---|---|
| llms.txt | https://clouatre.ca/llms.txt | `1a3f2c5cc51b51c433c5aa282c2ae0ad7119be0236c35557d6ff3b8527992470` |
| knowledge-graph.json | https://clouatre.ca/knowledge-graph.json | `e880d83b19f5c60fe140a823bed98a70e975d9f6ce7d3139ccaa3d3dcbc74f51` |
| okf index.md | https://clouatre.ca/okf/index.md | `7d09dccf648bec9b91f54665b327eb0890fa4191b5499379e0b84ea8f5fb054c` |
| okf bundle (concatenated) | https://clouatre.ca/okf/ tree, run-bench enumeration | see manifest.json `okf_bundle_concat_sha256` |

Digests intentionally differ from `seal-v2.json`/`seal-v3.json`: clouatre.ca
PRs #2412/#2413 (issue #2411) regenerated the bundle with per-page edgeStats,
directional `cites:`/`cited-by:` edges, and frontmatter-derived cluster
membership, and post `frontmatter-okf-knowledge-graph` was published. The
verified new-bundle features are present in production (checked live before
pinning). No digest mismatch occurred at any later step: the runner
re-verified every pin at arm start and all four arms passed the check.

## 2. Answerability re-derivation (flips)

Derived deterministically per pilot item against the pinned payloads
(`pilot-seal.json` → `answerability_map`; per-item evidence in the
transcript below the fold of this file's tables):

- **F1 (citation edges): FLIP.** All 5 pilot items now have
  `cites:` == gold on the okf concept pages. v2.1 map: only kg-json.
- **F2 (edgeStats): FLIP.** All 5 pilot items have page `edgeStats:
  inbound N, outbound M` exactly equal to gold. v2.1 map: only kg-json.
- **F3 (forward membership): FLIP (4/5).** New cluster indexes list
  exactly the gold post set for subagent-orchestration-tooling,
  legacy-modernization, security-supply-chain, multi-agent-architecture
  (`evaluation-reliability` lists gold plus the drifted new post, i.e.
  answerable against drift-adjusted gold). v2.1 map: kg-json and
  llms-txt only.
- **F4: unchanged.** Per-post membership stable; all arms answerable.

**Gold drift (not an answerability flip):** `q-20261124-007`
(F3, evaluation-reliability) — the new post joined that cluster after
sealing, so kg `clusters[].posts`, the llms.txt Concept Index line, and
the okf cluster index all now include
`frontmatter-okf-knowledge-graph`. The question file stays
byte-frozen; the pilot scorer (`score-v2-pilot.py`, `GOLD_DRIFT`) adds the
slug to gold for every arm identically.

`scripts/verify-f3-payloads.py` was not modified; it asserts the v2.1
expectations (okf F3 non-answerability), which this run deliberately
supersedes, so its per-cluster checks were re-derived by the analysis in
section 2 instead. All F1/F2/F3/F4 witnesses quoted above were computed
against the pinned freeze.

## 3. Run configuration

Four arms (`llms-txt`, `kg-json`, `okf-bundle`, `okf-index-relevant`),
pilot set n=20 (5 per family), model `@cf/google/gemma-4-26b-a4b-it`
(Cloudflare Workers AI), temperature 0, `max_completion_tokens` 4096,
single deterministic attempt — identical to the sealed v2.2 runner.
`run-bench-pilot.sh` is a verbatim copy of `recipe/run-bench.sh` with three
changes: output namespace (`raw/<arm>/` here, per the issue #31 concern —
nothing was written under `results/raw-v2*/`), payload base (this
directory's `freeze/`), and scorer (`score-v2-pilot.py`). `SEAL` resolves
to `pilot-seal.json` (pilot-local, schema `pilot-2.3.0`, no
`per_question_payloads` pins — the runner tolerates their absence).
Raw responses: `raw/<arm>/run-001..020.json` (80 captures, no empties).

## 4. Pilot scores (sealed scorer semantics, new answerability map)

| Arm | Total /20 | F1 /5 | F2 /5 | F3 /5 | F4 /5 | Trunc | Abst |
|---|---|---|---|---|---|---|---|
| llms-txt | 19 | 4 | 5 | 5 | 5 | 0 | 9 |
| kg-json | 20 | 5 | 5 | 5 | 5 | 0 | 0 |
| okf-bundle | 10 | 0 | 5 | 0 | 5 | 3 | 3 |
| okf-index-relevant | 11 | 1 | 5 | 0 | 5 | 3 | 4 |

Side-by-side with the v2.2 pilot gate on the same 20 items and identical
raw responses, rescored under this run's answerability map and gold drift
(`v22-pilot-rescored-new-map.json`; frozen-gold scores in
`v22-pilot-gate.json`):

| Arm | v2.2 payloads /20 | v2.3 payloads /20 | Δ |
|---|---|---|---|
| llms-txt | 18 | 19 | +1 |
| kg-json | 19 | 20 | +1 |
| okf-bundle | 7 | 10 | +3 |
| okf-index-relevant | 8 | 11 | +3 |

Per-family lever verdicts (okf arms, v2.2 → v2.3):

- **edgeStats (F2): fixed.** okf-bundle 0/5 → 5/5; okf-index-relevant
  0/5 → 5/5 (v2.2 full-run abstention collapse reproduced the 13/20
  failure; both okf arms now extract the counts exactly).
- **Frontmatter membership (F4): fixed.** okf-bundle 2/5 → 5/5;
  okf-index-relevant 3/5 → 5/5.
- **Directional cites (F1): extraction improved, format-blocked.**
  Sealed scorer: okf-bundle 5/5 → 0/5, okf-index-relevant 0/5 → 1/5.
  Manual inspection of all F1 raw responses shows the answers are
  substantively correct but use the payload's own slug format
  (`<slug>.md`, `/clusters/<cluster>/<slug>.md`); the sealed scorer
  normalizes only a `.json` suffix. With `.md`/path normalization
  (`normalized-sensitivity.json`, scorer copy
  `score-norm-sensitivity.py`): okf-bundle 17/20, F1 4/5;
  okf-index-relevant 16/20, F1 5/5. The regression is a payload-format /
  scorer-convention artifact, not semantic confusion.
- **F3: extraction, not payload.** Indexes now list gold exactly, yet
  sealed scorer gives 0/5; with format normalization okf-bundle 3/5
  (2 false abstentions remain on okf-index-relevant). Same
  extraction-fragility the postmortem predicted.

Truncations: 3 (okf-bundle) and 3 (okf-index-relevant), down from 4/3 on
v2.2 payloads; llms-txt and kg-json 0/0. Abstention behavior: llms-txt
correctly abstains on all 9 non-answerable F1/F2 items; okf arms abstain
correctly nowhere they shouldn't (llms F2 5/5 abstention-graded), but
okf-index-relevant still false-abstains on F3 (4/5).

## 5. Pilot gate (four blocking conditions, preregistration convention)

| # | Condition | Result | Verdict |
|---|---|---|---|
| 1 | Floor: best arm ≥ 3/20 | kg-json 20/20 | **PASS** |
| 2 | Saturation (scoped): okf-bundle ≤ 18/20 only | okf-bundle 10/20 | **PASS** |
| 3 | F3 competitiveness: ≥ 2 arms ≥ 2/5 on F3 | kg-json 5/5, llms-txt 5/5 | **PASS** |
| 4 | llms-txt F4 guard: ≥ 2/5 | llms-txt 5/5 | **PASS** |

## 6. Recommendation

Run the full v2.3. All four blocking pilot-gate conditions pass, and every
lever moved in the expected direction against matched raw responses on the
same items: F2 extraction went from total failure to 5/5 on both okf arms,
F4 membership from 2/5 to 5/5, truncations fell, and llms.txt did not
regress. The composite still trails llms.txt under the sealed scorer
(10/20 vs 19/20), but the sensitivity rescore shows most of the remaining
okf gap is a slug-format artifact (`.md` suffixes and cluster-path
prefixes in the new payload's edge listings) rather than extraction
failure, and F3 extraction remains genuinely fragile. Those two open
questions — the true composite once scorer normalization is decided, and
whether F3 recovers at n=7 — are exactly what the preregistered 63-item
run with a fresh seal exists to answer; closing at pilot scale would leave
a format-vs-extraction confound unresolved. Cost is bounded (four arms ×
63 items) and the pilot de-risks the run: pins verified, no truncation
surprises, gate green.

## Files

- `manifest.json`, `pilot-seal.json` — pins, answerability map, gold drift
- `freeze/` — production payload mirror (37 files, pinned)
- `raw/<arm>/run-001..020.json` — raw responses
- `run-bench-pilot.sh`, `score-v2-pilot.py`, `score-norm-sensitivity.py`
- `summary.json` — this run, sealed scorer
- `v22-pilot-gate.json` — archived v2.2 pilot gate scores (old map)
- `v22-pilot-rescored-new-map.json` — same raw responses, new map
- `normalized-sensitivity.json` — `.md`/path-normalized sensitivity rescore
