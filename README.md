<p align="center">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Apache--2.0-blue.svg?style=for-the-badge" height="28"></a>
  <a href="https://conventionalcommits.org"><img alt="Conventional Commits" src="https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg?style=for-the-badge" height="28"></a>
  <a href="seal.json"><img alt="Result" src="https://img.shields.io/badge/result-pending_pilot_gate-3%2F20-orange.svg?style=for-the-badge" height="28"></a>
  <a href="seal.json"><img alt="Arms" src="https://img.shields.io/badge/arms-3_llms.txt_%7C_kg.json_%7C_okf-blue.svg?style=for-the-badge" height="28"></a>
  <a href="results/raw/"><img alt="Runs" src="https://img.shields.io/badge/runs-0%2F309_(103x3)_seeded-lightgrey.svg?style=for-the-badge" height="28"></a>
<a href="https://doi.org/10.5281/zenodo.24410381"><img alt="DOI" src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.24410381-blue.svg?style=for-the-badge" height="28"></a>
</p>

<h1 align="center">grounding-source-exhibit</h1>

grounding-source-exhibit is a pre-registered grounding-source comparison on reading-chain questions derived from clouatre.ca `readingChains`. [seal.json](seal.json) was committed before any run: it fixes 103 reading-chain questions across three grounding arms (`llms-txt`, `kg-json`, `okf-bundle`), a primary exact-match metric (scorer `resolveChainSequence` pinned to clouatre-labs/clouatre.ca at commit 74105922), a secondary partial-credit metric computed post-hoc from full raw responses, and a blocking 3/20 pilot gate. Every reported number re-derives from [results/raw/](results/raw/) by the committed [analysis.py](analysis.py) against the schema in [DATA_DICTIONARY.md](DATA_DICTIONARY.md). No runs have completed yet; the experiment is sealed and awaiting execution.

## Pipeline

```mermaid
graph TD
    frozen["Frozen question set\n103 reading-chain questions"] --> arm1["Arm 1\nllms.txt"]
    frozen --> arm2["Arm 2\nKG + cluster"]
    frozen --> arm3["Arm 3\nokf index"]
    arm1 --> bench["Bench runs\nresults/raw/"]
    arm2 --> bench
    arm3 --> bench
    bench --> score["Scoring\nexact + partial credit"]
    score --> analysis["analysis.py\nsealed statistics"]
    analysis --> figures["Figures\nmatplotlib"]
```

*Figure 1: The experiment pipeline. The frozen question set feeds all three arms, each grounded by a distinct payload (llms.txt alone; knowledge-graph.json plus its cluster slice; the /okf/ index plus concept files); the bench stores full raw responses per arm, scoring computes exact match plus post-hoc partial credit from those logs, analysis.py derives the sealed statistics, and the figures render from the same raw records.*

## Experiment Index

| Slug | Question | Status | Key Result |
|------|----------|--------|------------|
| `grounding-source-exhibit` | Does grounding-source payload (llms.txt vs knowledge-graph.json + cluster slice vs OKF v0.3) affect agent retrieval on reading-chain questions? | pre-registered | pending (sealed in [seal.json](seal.json)) |

## Repository Layout

- `experiments/` - one directory per pre-registered experiment (see [experiments/README.md](experiments/README.md))
- `recipe/` - analysis notebooks and scripts that regenerate figures
- `figures/` - generated figures
- [METHODOLOGY.md](METHODOLOGY.md) - shared experimental design contract
- [DATA_DICTIONARY.md](DATA_DICTIONARY.md) - schema for `analysis.json` and `scores.json`
- [CITATION.cff](CITATION.cff) and `.zenodo.json` - citation metadata
- [seal.json](seal.json) - frozen pre-registration (arms, metrics, pilot gate, statistics)

## Reproduction

1. Clone the repository and check out the tag matching the release.
2. Install [uv](https://docs.astral.sh/uv/).
3. Validate the dataset schema:

   ```bash
   uv run python validate_schema.py
   ```

4. Regenerate figures from the recipes in `recipe/`.

Each experiment directory under `experiments/` contains its protocol, runner and scorer prompts, raw sessions, and analysis records, so any result can be traced back to its pre-registered design.

## Figures

Figure scripts live in `figures/` and render from committed `results/raw/` records only; each exits with a message until the run produces data. The PNGs below render once `results/raw/` records exist.

![Exact-match proportion per grounding arm with 95% Wilson score intervals](figures/fig1-arm-comparison.png)

*Figure 2: Exact-match proportion per arm with 95% Wilson score intervals on the 103 reading-chain questions, the primary metric endpoint per arm.*

![Per-arm partial-credit distributions as a jittered strip over box plots with Welch t annotation](figures/fig2-partial-credit.png)

*Figure 3: Per-arm partial-credit distributions (jittered strip over box plot) with the Welch t annotation for the secondary metric.*

![Paired per-question exact-match deltas shown as improved, tied, or worsened counts for the two pairwise arm comparisons](figures/fig3-per-question-deltas.png)

*Figure 4: Paired per-question exact-match deltas (improved/tied/worsened) for the two pairwise arm comparisons.*

Regenerate with:

```bash
uv run --with matplotlib python figures/fig1-arm-comparison.py
uv run --with matplotlib python figures/fig2-partial-credit.py
uv run --with matplotlib python figures/fig3-per-question-deltas.py
```

## Raw-Response Logging

The upstream bench (clouatre-labs/clouatre.ca experiments/) persists captured bodies truncated to 512 bytes (`body_512b` in its D1 samples table). The pre-registered secondary metric (per-step prefix credit) is computed post-hoc from raw logs and requires untruncated responses, so this repository commits its own runner, `recipe/run-bench.sh`, which drives the bench per arm and stores the FULL raw response for every run under `results/raw/<arm>/run-<id>.json` before any scoring. This satisfies the pre-run verification requirement that raw responses are captured without truncation for all three arms (`llms-txt`, `kg-json`, `okf-bundle`), and `analysis.py` re-derives every reported number, including partial credit, from these artifacts.

## Pre-Registration

[seal.json](seal.json) was committed before the first run. It fixes the three arms and their exact payloads, n=103 per arm, the primary exact-sequence-match metric (scorer `resolveChainSequence`, pinned to clouatre-labs/clouatre.ca experiments/src/bench-do.ts at commit 74105922c993a06d06a2291d5b73c48dc445aa1a), the secondary partial-credit metric, a blocking pilot gate (best arm must reach at least 3/20 exact matches, otherwise STOP and re-register), and the statistical tests (two-proportion score test on exact-match deltas, Welch t on partial credit, raw p-values only).

## Citing This Work

See [CITATION.cff](CITATION.cff). DOI: 10.5281/zenodo.24410381.

## Repository Setup

This repository was created from clouatre-labs/template-exp-repo. Standard labels come from `bash scripts/bootstrap.sh`; the main-branch ruleset mirrors the house pattern (squash-only, deletion and non-fast-forward protection, DCO sign-off, required CI Result / Security Result / Lint markdown checks).
