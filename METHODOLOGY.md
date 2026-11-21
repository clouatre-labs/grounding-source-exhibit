# Methodology

Experimental design and analysis plan for experiments in this repository. Replace each `TODO` section per experiment; keep this top-level document as the shared methodological contract.

## Research Question

Which grounding-source payload can an AI agent actually use to answer questions about clouatre.ca content: the curated `llms.txt`, the full frozen `knowledge-graph.json`, or the frozen OKF v0.3 bundle (index plus every cluster and concept page)? The question is framed so a null result is informative: if the curated file carries as much answerable signal as the full knowledge graph (primary endpoint not separated), publishers do not need the heavier artifact; if a payload cannot answer a question, a correct abstention scores 1, so failure to abstain is measurable rather than hidden.

The v2.1 preregistration is [seal-v2.json](seal-v2.json), sealed before any v2 run and superseding the archived [seal.json](seal.json) v1 seal after the v1 abort. Results: [results/findings.md](results/findings.md).

## Pre-Registration

Every experiment MUST have its protocol, rubric, and scoring prompts committed under `experiments/<slug>/` BEFORE any session is run. The commit containing the pre-registration must precede the first run record; edits after data collection begins require a dated addendum in the experiment's `protocol.md`.

- Rubric criteria are defined before examining any model output.
- Group assignments are sealed in `label-map.json` before scoring begins.
- Statistical tests are named in the protocol before data collection.

## Experimental Design

Three arms over the same 63 sealed questions (F1 citation edges: 20, F2 edgeStats link counts: 20, F3 forward cluster membership: 7, F4 cluster membership of a post: 16), only the grounding payload differs, sha256-pinned in seal-v2.json and verified at run start:

- Arm 1 `llms-txt`: frozen `llms.txt`
- Arm 2 `kg-json`: frozen `knowledge-graph.json`
- Arm 3 `okf-bundle`: frozen OKF v0.3 bundle

A per-family answerability map grades abstention: F1 and F2 are kg-json only, F3 is kg-json and llms.txt, F4 is all three arms. Model and sampling are fixed per the seal (@cf/google/gemma-4-26b-a4b-it, temperature 0, single attempt, retries on empty responses only). The primary endpoint is the per-arm item score (correct answer or correct abstention, n = 63) with pairwise McNemar exact tests and Holm-Bonferroni across the 3 pairs; the secondary endpoint is a paired permutation test on partial credit (10000 permutations, seed 20261123). A blocking pilot gate (floor, saturation, F3 competitiveness, llms-txt F4 extraction guard) must pass before the full run. Per-family breakdowns are labeled exploratory in the seal.

## Blind Scoring

Scoring is deterministic and sealed, not model-judged: [recipe/score-v2.py](recipe/score-v2.py) applies the per-family metric definitions (set equality / dice for F1, F3, F4; integer match for F2; abstention via the answerability map) to the raw responses in `results/raw-v2/`. The blinded question files (`ground-truth/blinded-*-v2.1.json`, committed pre-run) regenerate the sha256 hashes recorded in the seal; no group label, run metadata, or sibling output enters scoring.

## Analysis Plan

[analysis-v2.py](analysis-v2.py) derives every reported number from the committed raw records (`results/raw-v2/`): primary McNemar exact + Holm, secondary paired permutation on partial credit, conditional extraction and abstention accuracies, and truncation counts. Output lands in `results/analysis-v2.json` (schema in [DATA_DICTIONARY.md](DATA_DICTIONARY.md)); findings in `results/findings.md`; figures in `figures/` render from the same records.

## Threats to Validity

- Single model, single site, one deterministic attempt per item; run-to-run variance is unquantified by design (temperature 0), so rates carry item-sampling variance only (MDD ~22-24pp aggregate at n=63, per the seal).
- The composite endpoint mixes extraction and abstention credit; read conditional accuracies, not just headline rates.
- okf-bundle truncations reflect payload size interacting with the 4096-token completion budget, not ranking quality of the bundle's content; a larger budget or chunked retrieval could change its extraction accuracy (phase 2 candidate).
- The v2.0 abort means the preregistered question set changed once; the v2.1 seal is the operative registration and was sealed before any v2.1 item ran.
