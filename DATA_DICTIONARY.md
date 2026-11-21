# Data Dictionary

This document defines the schema and field meanings for experiment data files in this repository. `validate_schema.py` enforces the required fields below; run `uv run python validate_schema.py` before every PR that touches `experiments/`.

## Layout

Experiment directories hold pre-registration artifacts and v1-format analysis records:

- `experiments/<slug>/analysis.json`: run metadata, message counts, and evaluation scores (schema below)
- `experiments/<slug>/scores.json`: per-criterion rubric scores with justifications
- `experiments/<slug>/protocol.md`, `runner-prompt.md`, `scorer-prompt.md`: pre-registration artifacts
- `experiments/<slug>/sessions/`: raw session logs or database exports

The v2.1 run data lives elsewhere:

- `results/raw-v2/<arm>/run-*.json`: per-run records (schema below)
- `results/analysis-v2.json`: sealed statistics (`statistics.primary` McNemar + Holm, `statistics.secondary` permutation, `comparisons` per pair)
- `results/findings.md`: reported findings

## analysis.json (`experiments/<slug>/analysis.json`)

### Top-level schema

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `experiment` | string | no | Experiment slug, matches the directory name |
| `schema_version` | string | no | Version of this schema the record conforms to |
| `title` | string | no | Human-readable experiment title |
| `issue` | string \| null | yes | Target issue or task reference |
| `date` | string | no | Experiment date (YYYY-MM-DD) |
| `model` | string | no | Model identifier under test |
| `n_per_group` | integer | no | Number of runs per group |
| `control_condition` | string | no | Description of the control condition |
| `treatment_condition` | string | no | Description of the treatment condition |
| `rubric_version` | string | no | Rubric identifier used for scoring |
| `orchestrator_session` | string \| null | yes | Orchestrator session reference, if any |
| `repo_head` | string | no | Repository commit at run time |
| `experiment_start` | string | no | ISO 8601 timestamp with UTC offset of first run |
| `experiment_end` | string | no | ISO 8601 timestamp with UTC offset of last run |
| `analyzed_at` | string | no | ISO 8601 timestamp with UTC offset of analysis |
| `runs` | object | no | Map of run ID to run record |
| `scores` | object | no | Scoring summary keyed by run ID |
| `statistical_test` | string | no | Pre-registered statistical test name |
| `conclusion` | string | no | Result summary |
| `pre_acknowledged_limitations` | array | no | Limitations stated before analysis |

## Run record (`results/raw-v2/<arm>/run-*.json`)

One JSON record per run; full raw response plus sealed scorer output:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `group` | string | no | Arm label: `llms-txt`, `kg-json`, or `okf-bundle` |
| `session_id` | string | no | Session identifier from the run harness |
| `messages` | integer | no | Message count in the session |
| `input_tokens` | integer | no | Accumulated input tokens |
| `output_tokens` | integer | no | Accumulated output tokens |
| `total_tokens` | integer | no | Sum of input and output tokens |
| `wall_clock_seconds` | number | no | Elapsed wall-clock seconds |
| `bytes` | integer \| null | yes | Session byte size, if recorded |
| `raw_response` | string | no | Full raw model response for the run, stored verbatim so scoring can be re-derived post-hoc |
| `item_id` | string | no | Sealed question identifier (`ground-truth/full-v2.1.json`) |
| `family` | string | no | Preregistered family: `F1` (citation edges), `F2` (edgeStats link counts), `F3` (forward cluster membership), or `F4` (cluster membership of a post) |
| `model` | string | no | Model identifier used for the run |
| `exact_match` | integer | no | Sealed scorer output: 1 if the parsed answer matches the sealed ground truth under the per-family metric (set equality / dice for F1, F3, F4; integer match for F2), else 0 |
| `partial_credit` | number | no | Secondary metric: dice overlap on set-valued families (F1, F3, F4) or fraction of correct integers on F2; 0.0 when the run abstained |
| `abstained` | boolean | no | True when the scorer found no parseable answer (counted as abstention) |
| `item_score` | integer \| null | no | Primary metric under the seal answerability map: 1 on a correct answer (answerable item) or a correct abstention (unanswerable item), 0 otherwise; null if scored without `--arm` |
| `prompt_tokens` | integer | no | Prompt tokens reported by the provider |
| `completion_tokens` | integer | no | Completion tokens reported by the provider |
| `reasoning_tokens` | integer \| null | yes | Reasoning tokens reported by the provider, if any |
| `finish_reason` | string | no | Provider finish reason (`stop`, `length`, ...); `length` flags a context truncation |
| `note` | string \| null | yes | Optional note (e.g. failure reason) |

## scores.json

Free-form per-criterion scoring keyed by run ID; each entry SHOULD include the score value, per-criterion results, and scorer justifications.
