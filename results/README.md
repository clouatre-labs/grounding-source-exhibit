# results/

Analysis outputs and raw run records. Reported numbers re-derive from these directories via the committed [analysis-v2.py](../analysis-v2.py).

## Layout

| Path | Contents | Status |
| --- | --- | --- |
| `analysis-v2.json` | Statistics for the v2.1 full run: per-arm scores, Wilson intervals, McNemar exact + Holm, paired permutation, conditional accuracies, truncation rates | Operative |
| `findings.md` | Prose findings for the v2.1 full run, with threats to validity | Operative |
| `raw-v2/` | The v2.1 full run: `run-001..063.json` per arm (raw responses, usage, finish reason, sealed scores) | Operative |
| `raw-v2-pilot-pass/` | The 20-item v2.1 pilot run that passed the preregistered gate | Archived, gate evidence |
| `raw-v2-pilot-aborted/` | The v2.0 pilot run whose gate FAILED on `f3_competitiveness`; see `ABORT-PILOT.md` | Archived, aborted |
| `raw-v1-aborted/` | The v1 run halted for a coverage ceiling (llms.txt saturation); see `RUN-ABORTED.md`, unanalyzed | Archived, aborted |

## Regeneration

```
uv run python analysis-v2.py --questions ground-truth/full-v2.1.json \
  --pilot-questions ground-truth/pilot-v2.1.json
```

Rewrites `analysis-v2.json` from `raw-v2/` and prints the markdown summary. Only the statistics and figures are locally re-derivable; re-executing the bench itself requires Cloudflare model access plus sha256 re-verification of the frozen payloads per the seal.

Preregistration: [preregistration-v2.1.md](../preregistration-v2.1.md) (human-readable mirror of [seal-v2.json](../seal-v2.json)).
