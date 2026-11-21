# RUN-ABORTED: grounding-source-exhibit v1

## Status

The v1 run was halted on 2026-11-21 by orchestrator decision before
completion and is archived here unanalyzed as evidence for the v1
deviation record.

## Stop reason

Coverage ceiling. The `llms-txt` and `kg-json` arms saturated because
`/llms.txt` lists all reading-chain sequences verbatim, making the
primary metric (exact sequence match) trivially solvable from that
payload alone. The `okf-bundle` arm lacks `readingChains` entirely.
The comparison therefore has no discriminative headroom: it measures
payload verbosity, not grounding quality.

## What happened

- The pilot passed the v1 floor gate (20/20 - 20/20 - 0/20), but the
  gate tested no headroom: two arms at ceiling could not separate.
- The run was stopped at 103/103 (`llms-txt`, `kg-json`) and 78
  (`okf-bundle`) captured runs.
- `results/analysis.json` was never produced (aborted before analysis);
  no partial analysis file is archived.
- `seal.json` (v1) is NOT edited. Per its `pilot_gate` rule, the only
  sanctioned responses at this point were `proceed` or
  `STOP-and-re-register`; this run is recorded as the latter.

## Contents

- `llms-txt/` — 103 raw run records (v1 pilot + partial full run)
- `kg-json/` — 103 raw run records
- `okf-bundle/` — 78 raw run records

These records are archived as-is. The v2 pre-registration
(`seal-v2.json`) supersedes this experiment with blinded ground truth,
discriminative question families, and paired statistics; see
`results/raw-v1-aborted/RUN-ABORTED.md` (this file) referenced from
`seal-v2.json`.
