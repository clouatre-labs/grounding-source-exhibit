# Findings: grounding-source-exhibit v2.1

## Headline

**The whole-bundle okf payload failed as a machine-grounding surface in this run: 31/63 item score (0.492, Wilson 95% [0.373, 0.612]), losing to both other arms (Holm p < 1e-5), with 23 of 63 runs truncating their context and only 37.5% extraction accuracy on the 16 items it was supposed to answer.** A curated llms.txt carried as much answerable signal as the full knowledge graph: 55/63 vs 61/63, not separated by the preregistered McNemar exact test with Holm correction (p = 0.070).

## Design Recap

Three arms, same 63 sealed questions, same model (@cf/google/gemma-4-26b-a4b-it, temperature 0, single attempt), only the grounding payload differs: frozen `llms.txt`, frozen `knowledge-graph.json`, frozen OKF v0.3 bundle (index plus every cluster and concept page). Four preregistered families with a sealed answerability map: F1 citation edges and F2 edgeStats counts (kg-json only), F3 forward cluster membership (kg-json and llms.txt), F4 cluster membership of a post (all arms). A correct abstention on an unanswerable item scores 1; conditional extraction and abstention accuracies are reported separately so the composite is never read as pure extraction. Sealed before any v2.1 run; pilot gate passed first (llms-txt 19/20, kg-json 20/20, okf-bundle 8/20). See [seal-v2.json](../seal-v2.json).

## Primary Endpoint

*Table 1: Item score per arm; correct answer or correct abstention scores 1 (n=63 each).*

| Arm | Score | Rate | Wilson 95% | Extraction acc. | Abstention acc. | Truncations |
| --- | --- | --- | --- | --- | --- | --- |
| kg-json | 61/63 | 0.968 | [0.891, 0.991] | 0.968 (63 items) | n/a (0 abstention items) | 2 |
| llms-txt | 55/63 | 0.873 | [0.769, 0.934] | 1.000 (23 items) | 0.800 (40 items) | 2 |
| okf-bundle | 31/63 | 0.492 | [0.373, 0.612] | 0.375 (16 items) | 0.532 (47 items) | 23 |

Pairwise McNemar exact tests with Holm-Bonferroni across the 3 pairs:

- llms-txt vs kg-json: discordant [1, 7], Holm p = 0.070 — **not significant**.
- llms-txt vs okf-bundle: discordant [25, 1], Holm p = 1.6e-6 — **okf-bundle worse**.
- kg-json vs okf-bundle: discordant [31, 1], Holm p = 4.6e-8 — **okf-bundle worse**.

## Secondary Endpoint

Paired permutation test on partial credit (10000 permutations, seed 20261123), as sealed: kg-json separates from both other arms on partial credit (kg-json minus llms-txt +0.574, p < 1e-4; kg-json minus okf-bundle +0.52, p < 1e-4); llms-txt and okf-bundle do **not** separate (llms-txt minus okf-bundle +0.057, p = 0.44) despite a 38-point item-score gap. The composite mixes extraction and abstention credit, so the pair reads as follows: llms-txt earns its item score mostly through correct abstentions (abstention accuracy 0.800) and perfect extraction on what it answers, while okf-bundle's partial credit comes from its few extraction attempts, and its item score collapses because it fails to abstain where the payload cannot answer.

## Exploratory: Per-Family Breakdown

*Table 2: Item-score counts per family per arm (exploratory per the seal).*

| Family | kg-json | llms-txt | okf-bundle | Grading note |
| --- | --- | --- | --- | --- |
| F1 citation edges (20) | 18/20 | 12/20 | 2/20 | extraction for kg-json; abstention-graded for the other two |
| F2 edgeStats counts (20) | 20/20 | 20/20 | 20/20 | extraction for kg-json; abstention-graded for the other two |
| F3 cluster membership (7) | 7/7 | 7/7 | 3/7 | extraction for kg-json and llms-txt; abstention-graded for okf-bundle |
| F4 post clusters (16) | 16/16 | 16/16 | 6/16 | extraction for all three arms |

The discriminative signal sits in F4 and F3: on items every arm can answer in principle, the okf bundle scores 6/16 and 3/7. All 23 truncated runs (23/63) occurred on F1/F2/F3, which are unanswerable for this arm; their empty output was scored as correct abstention (item_score = 1), so truncation inflated the abstention side of the composite rather than causing the F4 misses. Every F4 miss (10/16) is a complete, confident wrong answer (`finish_reason: stop`), consistent with delivery mismatch rather than budget exhaustion. The 23/63 truncation rate still evidences payload-size interaction with the 4096-token completion budget, but on the unanswerable families it accidentally rescued the score. On unanswerable families it answered confidently wrong (abstention accuracy 0.532; in the v2.0 pilot, 100% of its F3 failures were confident hallucinations, not abstentions), which is the failure mode a publisher should weight most heavily.

## Run History and Deviations

- **v1 abort** (pre-scoring): llms.txt listed reading chains verbatim, giving it a coverage ceiling; run halted by orchestrator decision, archived in `results/raw-v1-aborted/`, v1 seal deposited as DOI 10.5281/zenodo.24410381.
- **v2.0 pilot-gate STOP** (blocking gate, honored): F3 was mis-preregistered as post-to-concepts (answerable by no okf payload); both non-kg arms failed the F3 competitiveness gate by answering confidently wrong. Full run was NOT started.
- **v2.1 re-registration** (pre-run): F3 redesigned as forward cluster membership with the answerability map verified per-item by `scripts/verify-f3-payloads.py`; 2 okf-full-listing clusters excluded from sampling so okf-bundle stays deterministically unanswerable; pilot passed all four blocking gates before the full run.
- **2026-11-21 reporting repair** (post-run, #20): a jq type error in `run-bench.sh` stored `abstained: false` for all 73 true abstentions in `raw-v2` and `raw-v2-pilot-pass`. All 249 records were regenerated deterministically via `score-v2.py`; `item_score`, `exact_match`, and `partial_credit` re-verified unchanged, so no published number moved. The findings causal sentence on truncation attribution was rewritten; the Zenodo v2.1.3 snapshot predates this repair; v2.1.4 (DOI 10.5281/zenodo.24427220) supersedes it on the same concept record.
- No post-hoc scoring deviations from the v2.1 seal; the only post-run change is the reporting repair above. Per-family breakdowns are labeled exploratory in the seal and reported as such here.

## Threats to Validity

- Single model, single site, one deterministic attempt per item; run-to-run variance is unquantified by design (temperature 0), so rates carry item-sampling variance only (MDD ~22-24pp aggregate at n=63, per the seal).
- The composite endpoint mixes extraction and abstention credit; read conditional accuracies, not just headline rates.
- okf-bundle truncations reflect payload size interacting with the 4096-token completion budget, not ranking quality of the bundle's content; a larger budget or chunked retrieval could change its extraction accuracy (phase 2 candidate). Delivery-mode analysis and revival hypotheses: [docs/okf-postmortem.md](../docs/okf-postmortem.md).
- The v2.0 abort means the preregistered question set changed once; the v2.1 seal is the operative registration and was sealed before any v2.1 item ran.

## Artifacts

- Raw records: `results/raw-v2/{llms-txt,kg-json,okf-bundle}/run-001..063.json` (full raw responses, usage, finish reason, sealed scores).
- Statistics: `results/analysis-v2.json` (schema in [DATA_DICTIONARY.md](../DATA_DICTIONARY.md)).
- Questions: `ground-truth/blinded-*-v2.1.json` (pre-run, blinded) and `ground-truth/full-v2.1.json` (plaintext, committed with raw outputs per the seal blinding note).
- Deposit: Zenodo DOI 10.5281/zenodo.24424679 (single-zip artifact set, v2.1 run) under concept DOI 10.5281/zenodo.24410380; superseded v2.1.x snapshots are listed on the Zenodo record.

## v2.2 Extension: OKF Index-Plus-Relevant-Pages Arm (sealed, run complete)

- Deposit: Zenodo DOI 10.5281/zenodo.24441791 (single-zip artifact set, v2.2.0 four-arm run including the relocated pilot captures and the incident manifest) under concept DOI 10.5281/zenodo.24410380; the record description documents the capture incident, the remediation, and that interim pre-repair values were never deposited.

A fourth delivery-mode arm, `okf-index-relevant`, is preregistered under [seal-v3.json](../seal-v3.json) (schema 2.2.0; prose mirror in [preregistration-v2.2.md](../preregistration-v2.2.md)), sealed before any v2.2 item ran. It reuses the sealed v2.1 question sets, seeds, prompts, scoring rule, model, and 4096-token budget unchanged; the only difference is the payload: per question, the frozen OKF index plus only the cluster indexes and concept pages named by the item's derived gold-cluster set (mapping pinned BEFORE sealing: ground truth -> `nodes[].category` -> `clusters[]` -> post-slug filenames, `sort -u` enumerations), single completion. The intent is to test whether the okf surface's v2.1 failures (0.492 composite, 23/63 truncations, 0.375 F4 extraction) were caused by payload size rather than delivery mode.

Pre-run status and gates: `scripts/verify-f3-payloads.py` passes on BOTH question files with the extended gate (v2.1 conditions plus per-item okf-index-relevant composition completeness and F3 non-answerability witnesses), the composed payloads are byte-deterministic (per-question sha256 pins in the seal match repeated assemblies for sampled items across F1/F2/F3/F4), and `recipe/run-bench.sh` now parameterizes SEAL per arm (v2 arms keep seal-v2.json; `SEAL_FILE` overrides) without touching the v2 payload assembly. Sealed answerability delta: `okf-index-relevant` joins F4 only; F1 (symmetric Related links), F2 (no edge counts), and F3 (composed cluster indexes never list the full gold membership) remain non-answerable, so the arm's headline comparison against `okf-bundle` and `llms-txt` is scoped to F4 extraction accuracy, abstention accuracy on F1/F2/F3, and truncation count.

### Pilot result (n=20, gate PASSED) and scoped comparison

All seal-v3 preconditions verified before the run: `verify-f3-payloads.py` exit 0 on both question files, frozen-payload sha256 match for all 67 entries across both seals, all 63 per-question pins reproduced byte-identically, and both questions files match their seal `dataset` pins. The runner needed a dispatch fix (the per-question arm had no branch in the fixed-payload assembly case and aborted at startup); composition, seal, and freeze tree are unchanged.

Pilot gate, evaluated per `seal-v3.json` (all four blocking conditions met): floor best arm 20/20 (kg-json) >= 3/20; saturation okf-bundle 8/20 <= 18/20 and okf-index-relevant 8/20 <= 18/20; F3 competitiveness four arms >= 2/5 (llms-txt 5, kg-json 5, okf-bundle 2, okf-index-relevant 2); llms-txt F4 guard 5/5 >= 2/5.

| Arm | item_score | F1 | F2 | F3 | F4 | Trunc | Mean prompt tok |
|---|---|---|---|---|---|---|---|
| okf-index-relevant | 8/20 | 0/5 | 3/5 | 2/5 | 3/5 | 3 | 4,124 |
| okf-bundle | 8/20 | 0/5 | 4/5 | 2/5 | 2/5 | 4 | 10,078 |
| llms-txt | 19/20 | 4/5 | 5/5 | 5/5 | 5/5 | 3 | 4,198 |
| kg-json | 20/20 | 5/5 | 5/5 | 5/5 | 5/5 | 0 | n/a |

Reading: at 41% of the whole-bundle payload the index-plus-relevant-pages arm matches okf-bundle's total and beats it on the sealed delta metric (F4 extraction 3/5 vs 2/5) with one fewer truncation. Two caveats: three of its items ended `finish_reason=length` with no answer emitted, which scores as correct abstention on the unanswerable families, so part of the F2/F3 credit is truncation-driven (the clean extraction signal is F4); and llms-txt scores 19/20 at comparable payload size, so the plaintext frontier still dominates any OKF surface in the pilot.

Run-incident disclosure: a `count=0` smoke test triggered BSD `seq` descent and consumed single sealed attempts for pilot items 001 and 020 before the real invocation; both captures are kept as those items' only attempts (the item-020 file sits at its true slot `run-020.json`). An earlier invocation killed at a tool timeout may have discarded one unseen request for item 001; no second captured attempt exists for any item.

### Full run (n=63) and final scoped comparison

The full run completed after the gate pass (single sealed attempt per item). A capture-repair incident affected this arm and is fully remediated; the numbers below are recomputed from the verified raw captures.

Incident disclosure (namespace collision, v2.2): in PR #28 the 20-capture pilot pass wrote its captures into the full-run directory `results/raw-v2/okf-index-relevant/` as `run-001..020`, so the full run in PR #29 skipped slots 1-20 as already-captured. The items are interleaved 5x per family across slots 1-20, leaving five wrong-prompt slots per family in the mixed tree. Remediation: the 20 pilot captures were relocated to `results/raw-v2-pilot-pass/okf-index-relevant/`, and 20 first true attempts for items 1-20 were captured in a single invocation with per-item prompt pins verified 20/20 at run time; capture timestamps postdate the main run (slots 21-63). The repaired tree is ordinal-verified `run-001..063`; the loader aligns strictly by ordinal and fails loudly on any id mismatch (no id remapping).

| Arm | item_score | F1 | F2 | F3 | F4 | Trunc | Mean prompt tok |
|---|---|---|---|---|---|---|---|
| okf-index-relevant | 22/63 | 1/20 | 13/20 | 2/7 | 6/16 | 14 | 4,350 |
| okf-bundle | 31/63 | 2/20 | 20/20 | 3/7 | 6/16 | 23 | 10,081 |
| llms-txt | 55/63 | 12/20 | 20/20 | 7/7 | 16/16 | 2 | 4,201 |
| kg-json | 61/63 | 18/20 | 20/20 | 7/7 | 16/16 | 2 | 18,767 |

Reading: the payload-size hypothesis is confirmed but not decisive. At 43% of the bundle payload, the index-plus-relevant arm cuts truncations from 23 to 14, ties the bundle on F4 extraction (6/16 vs 6/16), and trails on F3 abstention (2/7 vs 3/7), but loses overall (22/63 vs 31/63), driven by F2 abstention failures (13/20 vs 20/20: the composed payload contains the prompt-source page, so the model attempts answers the edge counts would falsify) and F1 (1/20 vs 2/20; symmetric Related links are absent from the composed pages). llms-txt remains dominant at a comparable payload size (55/63, 2 truncations).

Producer recommendation for clouatre.ca: the per-question OKF slice did not rescue the OKF surface. The composite dropped to 22/63 versus the bundle's 31/63 because abstention discipline collapsed on the cleaner payload: on F2 the index-relevant arm scored 13/20 versus the bundle's 20/20 — the model attempted answers instead of abstaining on families the OKF content cannot determine (McNemar raw p = 0.012, Holm p = 0.023, so the composite drop is significant at 0.05 after Holm and runs in the wrong direction). Extraction tied: F4 6/16 versus 6/16. Truncations were cut (14 versus 23) at 43% of the bundle token budget, confirming payload size was the truncation cause — but truncations were never the binding constraint on accuracy. `llms.txt` remains the grounding frontier at a comparable token budget: 55/63 at ~4,201 mean prompt tokens versus 22/63 at ~4,350. Remember this arm is the BEST-CASE slice: it routes by gold-cluster ground truth, strictly more favorable than any realistic retrieval, and it still lost to every competitor (Holm p < 1e-7 versus llms-txt and kg-json). Supported conclusions, and no more: (1) llms.txt is the primary model-grounding surface; (2) never serve the whole bundle; (3) per-question composition is the only defensible OKF delivery mode, but it does not close the gap; (4) the content-level fixes are per-page edgeStats (F2 unanswerability) and directional citation edges (F1 ambiguity). Pairwise statistics (McNemar raw and Holm-adjusted across the six arm pairs) are in `results/analysis-v2.json`; the okf-bundle_vs_okf-index-relevant comparison is significant at 0.05 after Holm (bundle higher), so the composite drop is reported as a separated wrong-direction effect.

## v2.3 Extension: Regenerated OKF Bundle (sealed, run complete)

Preregistered under [seal-v4.json](../seal-v4.json) (schema 2.3.0), sealed before any v2.3 item ran against the production payloads served after clouatre-labs/clouatre.ca PR #2414 (citation edge lines `- cites: <slug> ([Title](target))`). The v2.2 producer fixes were implemented upstream: per-page `edgeStats` (F2), directional labeled `cites:`/`cited-by:` edges (F1), and frontmatter-derived cluster membership (F4). A pilot gate on the pre-#2414 bundle (2026-11-22, [results/pilot-v2.3-2026-11-22/](pilot-v2.3-2026-11-22/PILOT.md)) passed all four blocking conditions, and pins were re-derived against the post-#2414 tree per the issue's re-pin constraint. Sealed answerability delta versus v2.1: the okf arms join F1 (cites list == gold on all F1 items) and F2 (edgeStats == gold on all F2 items), and join F3 (cluster indexes now list the gold membership exactly; one item answerable only under drift-adjusted gold); F4 unchanged. Model, temperature, token budget, prompts, question sets, seeds, and scorer semantics are unchanged; three gold-drift items (q-20261125-015 F3, q-20261125-062 F1, q-20261125-030 F2) are adjusted identically for every arm via the seal `GOLD_DRIFT` (post `frontmatter-okf-knowledge-graph` joined the graph after v2.1 sealing); question files are byte-frozen. Full evidence: [results/v2.3-full/RUN.md](v2.3-full/RUN.md).

### Full run (n=63, single sealed attempt per item, 252/252 captures, zero empties)

| Arm | item_score | F1 | F2 | F3 | F4 | Trunc | Mean prompt tok |
|---|---|---|---|---|---|---|---|
| okf-index-relevant | 53/63 | 19/20 | 20/20 | 1/7 | 13/16 | 3 | 7,251 |
| okf-bundle | 50/63 | 14/20 | 20/20 | 0/7 | 16/16 | 9 | 17,339 |
| llms-txt | 55/63 | 12/20 | 20/20 | 7/7 | 16/16 | 3 | 4,321 |
| kg-json | 61/63 | 18/20 | 20/20 | 7/7 | 16/16 | 2 | 19,325 |

Reading: the preregistered hypothesis is confirmed. Both okf composites rose sharply (31 -> 50, 22 -> 53), llms.txt did not regress (55 -> 55), and after Holm-Bonferroni across the six pairs the only separated pair is kg-json > okf-bundle (Holm p = 0.0059); neither okf arm separates from llms-txt (Holm p = 0.997 / 1.0) nor from the other (p = 1.0). Per-fix verdicts: edgeStats (F2) fixed (composed arm 13/20 -> 20/20), directional cites (F1) fixed (composed arm 1/20 -> 19/20), frontmatter membership (F4) fixed (bundle 6/16 -> 16/16), while F3 extraction remains unsolved on the okf surface (0/7 and 1/7) even though the sealed payloads now contain the exact gold membership — the model does not convert index listings into correct membership answers, and llms-txt/kg-json stay 7/7. Truncations fell to 9 (bundle) and 3 (composed) from 23/14. Payload size remains a cost story: the composed arm reaches 53/63 at ~7,251 mean prompt tokens versus the bundle's ~17,339. Supported conclusions: (1) the content levers work — the OKF composite rose to statistical parity with llms.txt; (2) per-question composition remains the best OKF delivery mode and now also the cheapest competitive one at ~1.7x the llms.txt token budget; (3) the residual defect is F3 extraction on index-listing payloads, not payload content; (4) llms.txt and kg-json keep their positions (non-regression confirmed). Pairwise statistics are in `results/v2.3-full/analysis-v4.json`; deposit and blog updates are deferred to a separate, human-approved step.
