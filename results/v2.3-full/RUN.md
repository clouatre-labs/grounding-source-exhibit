# v2.3 Full Run Report (issue #36)

Sealed preregistration: [seal-v4.json](../../seal-v4.json) (schema 2.3.0), frozen before the first item ran. Payloads: production tree served after clouatre-labs/clouatre.ca PR #2414 (citation edge lines `- cites: <slug> ([Title](target))`), mirrored under [freeze/](freeze/), sha256-pinned in the seal and re-verified by the runner at each arm start (37 files; 63 per-question composition pins). Model `@cf/google/gemma-4-26b-a4b-it`, temperature 0, `max_completion_tokens` 4096, single deterministic attempt per item. Four arms x 63 sealed items (`ground-truth/full-v2.1.json`, byte-frozen; three gold-drift items adjusted identically for every arm via the seal `GOLD_DRIFT`: q-20261125-015 F3, q-20261125-062 F1, q-20261125-030 F2). Outputs: [raw/](raw/) (252 captures), [analysis-v4.json](analysis-v4.json), [run.log](run.log — gitignored).

Completeness: 252/252 captures, zero empty-after-retries, zero pin mismatches, no seal edits after run start.

## Headline (n=63, sealed scorer semantics unchanged)

| Arm | item_score | rate | Wilson 95% | F1 | F2 | F3 | F4 | Trunc | Abstentions (accuracy) | Mean prompt tok |
|---|---|---|---|---|---|---|---|---|---|---|
| kg-json | 61/63 | 0.968 | [0.891, 0.991] | 18/20 | 20/20 | 7/7 | 16/16 | 2 | 2 (0.0) | 19,325 |
| llms-txt | 55/63 | 0.873 | [0.769, 0.934] | 12/20 | 20/20 | 7/7 | 16/16 | 3 | 32 (1.0) | 4,321 |
| okf-index-relevant | 53/63 | 0.841 | [0.732, 0.911] | 19/20 | 20/20 | 1/7 | 13/16 | 3 | 4 (0.0) | 7,251 |
| okf-bundle | 50/63 | 0.794 | [0.678, 0.875] | 14/20 | 20/20 | 0/7 | 16/16 | 9 | 9 (0.0) | 17,339 |

Versus v2.2 (same arms, same scorer semantics): okf-bundle 31 -> 50 (+19), okf-index-relevant 22 -> 53 (+31), llms-txt 55 -> 55 (no regression), kg-json 61 -> 61.

## Pairwise inference (McNemar exact, Holm-Bonferroni across 6 pairs, alpha 0.05)

| Pair | discordant (a,b) | exact p | Holm p | Significant | Direction |
|---|---|---|---|---|---|
| kg-json vs okf-bundle | 11, 0 | 0.00098 | 0.0059 | yes | kg-json higher |
| kg-json vs okf-index-relevant | 10, 2 | 0.0386 | 0.193 | no | kg-json higher |
| llms-txt vs kg-json | 1, 7 | 0.0703 | 0.281 | no | kg-json higher |
| llms-txt vs okf-bundle | 11, 6 | 0.332 | 0.997 | no | llms-txt higher |
| llms-txt vs okf-index-relevant | 10, 8 | 0.815 | 1.0 | no | llms-txt higher |
| okf-bundle vs okf-index-relevant | 3, 6 | 0.508 | 1.0 | no | index-relevant higher |

After Holm, the only separated pair is kg-json > okf-bundle. The preregistered frontier claim holds: neither okf arm separates from llms-txt (Holm p 0.997 / 1.0), so the regenerated OKF surfaces reach statistical parity with llms.txt, and the two okf arms do not separate from each other.

## Per-fix verdicts

- **edgeStats (F2): FIXED.** okf-index-relevant 13/20 -> 20/20 (okf-bundle 20/20 -> 20/20; its v2.2 score was abstention-driven, now all extraction). Both okf arms extract the per-page counts exactly.
- **Directional cites (F1): FIXED.** okf-bundle 2/20 -> 14/20; okf-index-relevant 1/20 -> 19/20. The labeled directional edges (`cites:` / `cited-by:` with bare slugs) carry the answer; the composed arm extracts nearly perfectly, the full bundle loses ~6 items (extraction noise + 9 truncations).
- **Frontmatter membership: F4 FIXED, F3 NOT FIXED.** F4: okf-bundle 6/16 -> 16/16, okf-index-relevant 6/16 -> 13/16. F3 remains the residual failure: okf-bundle 0/7, okf-index-relevant 1/7 — the cluster indexes now list the gold membership exactly (deterministically answerable, sealed as such), but extraction/abstention behavior does not convert it. llms-txt and kg-json stay 7/7.

## Hypothesis verdict

Preregistered primary: "the okf composite improves over v2.2 under the sealed scorer without llms.txt regressing." **CONFIRMED.** Both okf composites rose sharply (31->50, 22->53), llms.txt is unchanged at 55/63, and the okf arms are no longer statistically separated from llms.txt. kg-json remains the ceiling (61/63); the F3 extraction failure is the one open defect.

## Notes and deviations

- Model id in the task prompt (`@cf/google/google/gemma-4-26b-a4b-it`) was wrong; the sealed and executed id is `@cf/google/gemma-4-26b-a4b-it` (verbatim from the v2.2 runner).
- GOLD_DRIFT covers three items (not only the pilot's one) because post #2412/#2413 joined the graph after v2.1 sealing; each drift value is agreed by live kg and live okf payloads identically; applied to every arm; question files untouched.
- Issue #32's `--fail-on-existing` was unimplemented; `run-bench-v4.sh` implements equivalent strictness (aborts before the loop on any pre-existing non-empty capture). No skips occurred.
- Zenodo deposit, blog edit, and clouatre.ca changes are explicitly out of scope for this run.
