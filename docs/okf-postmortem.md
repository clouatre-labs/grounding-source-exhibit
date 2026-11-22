# OKF bundle postmortem and revival path

This document separates two claims the main results intentionally conflate for the headline, then states what would have to change for the OKF v0.3 bundle to become a viable grounding surface for clouatre.ca. Hypotheses are labeled as hypotheses; only the measured numbers are claims.

## What actually failed

The experiment's `okf-bundle` arm served the **entire frozen bundle** (32 markdown files, index plus every cluster index and every concept page, 35,616 bytes concatenated) as a single payload into one completion with a 4096-token budget. The measured failures are:

- 23/63 runs truncated their context (`finish_reason == "length"`).
- 37.5% extraction accuracy on the 16 items the bundle was designed to answer.
- 53.2% abstention accuracy: confident wrong answers where abstention was correct.

[findings.md](../results/findings.md) already notes the confound: truncations reflect payload size interacting with the completion budget, not the quality of the bundle's content. The measured claim is therefore **scoped**: the whole-bundle-stuffing delivery failed for this model and budget. The experiment did not test OKF as a format under its own spec's intended consumption mode.

## Why this is a delivery mismatch, not a format verdict

The OKF v0.3 spec ([okf.md](https://okf.md/spec/)) describes a bundle as a navigable markdown tree: one `index.md`, typed concept pages, cross-linked as a graph. Its stated consumption mode is progressive disclosure — an agent walks index → cluster → concept and fetches only what the question needs. Community producer guidance (specification.website) likewise instructs producers to pair a bundle with an `llms.txt` pointer for discovery, not to make the bundle a one-shot context dump. Serving all 32 pages at once contradicts both.

## What would make OKF viable for clouatre.ca (phase 2 candidates)

Ordered by expected effect size, all untested:

1. **Index-plus-relevant-pages payload.** Answer each question with `index.md` plus only the cluster index and concept pages it names, instead of the full bundle. This matches the spec's intent and reduces the payload roughly tenfold; it directly targets the truncation and hallucination mechanisms.
2. **Agentic link-walking.** Let the agent fetch pages over multiple turns starting from `index.md`. Requires a multi-turn harness, not the single-completion design used here.
3. **Inline the content the stubs link out to.** Bundle concept pages are ~1 KB stubs: front matter, one-sentence description, and a link to the full post on clouatre.ca. If pages carried their content instead of a pointer, the bundle would be self-contained for questions about post substance, not just cluster membership.
4. **Larger completion budget.** Named in findings.md as a confound; a larger budget would remove truncations but not the structural retrieval problem, so it is the weakest candidate.
5. **One retrieval-augmented arm.** Same bundle, but select pages by similarity to the question. Changes the experiment's "payload-only" design, so it would need its own arm and seal.

Any of these would be a new preregistered arm under a new seal, not a rerun of this one.

## Hypothesized use cases where a bundle beats a single curated file

These are hypotheses, consistent with the spec's design and external practice, not results of this experiment. A single `llms.txt` wins when the whole answerable corpus fits in one context (the regime measured here). A bundle plausibly wins when it does not:

- **Large private wikis and runbooks.** When no single file can hold the corpus, a navigable tree with retrieval or link-walking is the only option; a curated file cannot scale.
- **Git-native knowledge bases.** A bundle that is already the shared source of truth for humans and agents (reviews in git, no second copy to rot) doubles as the grounding surface at near-zero marginal cost.
- **Multi-hop relational questions.** Cross-linked concept pages preserve the relationship layer a flat curated file flattens; an agent walking links can answer "how does X connect to Y" without the whole corpus in context.
- **Discovery-plus-depth pairing.** `llms.txt` as signpost, bundle as library: the curator keeps a small high-precision surface while the bundle holds depth agents can walk into on demand.

## Bottom line

For clouatre.ca today: keep the curated `llms.txt` as the primary grounding surface (the primary endpoint found it statistically indistinguishable from the full knowledge graph at n=63). The OKF bundle is not invalidated as a format by this run; it was tested in a delivery mode its own spec does not recommend. Reviving it for clouatre.ca requires a new seal testing delivery mode 1 or 2 above.
