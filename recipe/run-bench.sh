#!/usr/bin/env bash
# run-bench.sh - Exhibit-side bench runner with full raw-response capture.
#
# Drives the upstream clouatre.ca experiments bench per arm and persists the
# FULL raw model response for every run to results/raw/<arm>/run-<id>.json.
# The upstream bench D1 samples table caps captured bodies at body_512b
# (experiments/schema.sql:33-34), which is insufficient for the pre-registered
# post-hoc partial-credit metric; this runner records untruncated responses
# alongside the bench-native scores.
#
# Usage:
#   bash recipe/run-bench.sh <arm> <n> [base-url]
#
# Arguments:
#   arm      one of: llms-txt | kg-json | okf-bundle
#   n        number of questions to run (103 for the full run; 20 for pilot)
#   base-url bench base URL (default: https://clouatre.ca)
#
# Requires: curl, jq, gh CLI authenticated with access to the bench D1 export.

set -euo pipefail

ARM=${1:?usage: run-bench.sh <arm> <n> [base-url]}
N=${2:?usage: run-bench.sh <arm> <n> [base-url]}
BASE_URL=${3:-https://clouatre.ca}

case "$ARM" in
  llms-txt) GROUNDING_URL="$BASE_URL/llms.txt" ;;
  kg-json)
    GROUNDING_URL="$BASE_URL/knowledge-graph.json"
    # Deterministic cluster slice: target post clusters frontmatter first
    # entry -> public/knowledge-graph/<id>.json. Injected per-question by
    # the bench grounding mechanism; this env var selects slice mode.
    export KG_CLUSTER_SLICE=1
    ;;
  okf-bundle)
    GROUNDING_URL="$BASE_URL/okf/index.md"
    # /okf/ root index plus concept files reachable via the same rule.
    export OKF_BUNDLE=1
    ;;
  *) echo "ERROR: unknown arm '$ARM' (expected llms-txt|kg-json|okf-bundle)" >&2; exit 1 ;;
esac

OUT_DIR="results/raw/$ARM"
mkdir -p "$OUT_DIR"

echo "Arm: $ARM"
echo "Grounding payload: $GROUNDING_URL"
echo "Runs: $N"
echo "Output: $OUT_DIR"

# Drive the bench through its HTTP runner, capturing the FULL raw response
# body per run. The bench's HTTP interface returns the raw model response;
# we store it untruncated regardless of the D1 body_512b cap, keyed by run
# ID and session ID for join-back with bench-native scores.
for i in $(seq 1 "$N"); do
  RUN_ID=$(printf '%s-%03d' "$ARM" "$i")
  OUT="$OUT_DIR/$RUN_ID.json"
  if [ -s "$OUT" ]; then
    echo "skip $RUN_ID (already captured)"
    continue
  fi
  curl -sf -X POST "$BASE_URL/api/bench/run" \
    -H 'content-type: application/json' \
    -d "$(jq -n --arg arm "$ARM" --arg grounding "$GROUNDING_URL" --argjson index "$i" \
      '{arm: $arm, grounding_url: $grounding, question_index: $argjson.index, raw_response: true}')" \
    > "$OUT"
  jq -e '.raw_response != null and .raw_response != ""' "$OUT" > /dev/null \
    || { echo "ERROR: $OUT missing raw_response" >&2; exit 1; }
  echo "captured $RUN_ID ($(wc -c < "$OUT") bytes)"
done

echo "Done. Full raw responses in $OUT_DIR."
