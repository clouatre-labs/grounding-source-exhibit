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
- Deposit: Zenodo DOI 10.5281/zenodo.24424679 (single-zip artifact set) under concept DOI 10.5281/zenodo.24410380; superseded v2.1.x snapshots are listed on the Zenodo record.

## v2.2 Extension: OKF Index-Plus-Relevant-Pages Arm (preregistered, not yet run)

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

The full run completed after the gate pass (single sealed attempt per item; the invocation was interrupted twice by tool time limits and resumed via the runner's built-in captured-file skip, so no item ran twice).

| Arm | item_score | F1 | F2 | F3 | F4 | Trunc | Mean prompt tok |
|---|---|---|---|---|---|---|---|
| okf-index-relevant | 23/63 | 0/20 | 12/20 | 4/7 | 7/16 | 12 | 4,147 |
| okf-bundle | 31/63 | 2/20 | 20/20 | 3/7 | 6/16 | 23 | 10,081 |
| llms-txt | 55/63 | 12/20 | 20/20 | 7/7 | 16/16 | 2 | 4,201 |
| kg-json | 61/63 | 18/20 | 20/20 | 7/7 | 16/16 | 2 | 18,767 |

Reading: the payload-size hypothesis is confirmed but not decisive. At 41% of the bundle payload, the index-plus-relevant arm cuts truncations from 23 to 12 and edges the bundle on F4 extraction (7/16 vs 6/16) and F3 abstention (4/7 vs 3/7), but loses overall (23/63 vs 31/63), driven by F2 abstention failures (12/20 vs 20/20: the composed payload contains the prompt-source page, so the model attempts answers the edge counts would falsify) and F1 (0/20 vs 2/20; symmetric Related links are absent from the composed pages). llms-txt remains dominant at the same payload size (55/63, 2 truncations).

Producer recommendation for clouatre.ca: the per-question OKF slice did not rescue the OKF surface. The composite dropped to 23/63 versus the bundle's 31/63 because abstention discipline collapsed on the cleaner payload: on F2 the index-relevant arm scored 12/20 versus the bundle's 20/20 — the model attempted answers instead of abstaining on families the OKF content cannot determine (McNemar raw p = 0.077, Holm p = 0.141, so the direction is a wrong-direction signal, not a separated difference). Extraction barely moved: F4 7/16 versus 6/16. Truncations halved (12 versus 23) at 41% of the bundle token budget, confirming payload size was the truncation cause — but truncations were never the binding constraint on accuracy. `llms.txt` remains the grounding frontier at a nearly identical token budget: 55/63 at ~4,201 mean prompt tokens versus 23/63 at ~4,147. Remember this arm is the BEST-CASE slice: it routes by gold-cluster ground truth, strictly more favorable than any realistic retrieval, and it still lost to every competitor (Holm p < 1e-8 versus llms-txt and kg-json). Supported conclusions, and no more: (1) llms.txt is the primary model-grounding surface; (2) never serve the whole bundle; (3) per-question composition is the only defensible OKF delivery mode, but it does not close the gap; (4) the content-level fixes are per-page edgeStats (F2 unanswerability) and directional citation edges (F1 ambiguity). Pairwise statistics (McNemar raw and Holm-adjusted across the six arm pairs) are in `results/analysis-v2.json`; the okf-bundle_vs_okf-index-relevant comparison is not significant at 0.05 after Holm, so the composite drop is reported as a direction, not a separated effect.
