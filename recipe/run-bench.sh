#!/usr/bin/env bash
# run-bench.sh - Exhibit-side bench runner with full raw-response capture.
#
# Standalone driver hitting Workers AI REST directly (same pinned model and
# temperature 0 as the upstream bench) and persisting the FULL raw model
# response for every run to results/raw/<arm>/run-NNN.json per the
# DATA_DICTIONARY.md run-record schema. The upstream bench D1 samples table
# caps captured bodies at body_512b, insufficient for the pre-registered
# post-hoc partial-credit metric; this runner records untruncated responses.
#
# Usage:
#   bash recipe/run-bench.sh <arm> <n> [base-url]
#
# Arguments:
#   arm       one of: llms-txt | kg-json | okf-bundle
#   n         number of questions to run (103 full; 20 pilot)
#   base-url  grounding payload base URL (default: https://clouatre.ca)
#
# Requires: curl, jq, recipe/score.py. Env: CLOUDFLARE_API_TOKEN and
# CLOUDFLARE_ACCOUNT_ID must be set (never written to any file).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARM=${1:?usage: run-bench.sh <arm> <n> [base-url]}
N=${2:?usage: run-bench.sh <arm> <n> [base-url]}
BASE_URL=${3:-https://clouatre.ca}

: "${CLOUDFLARE_API_TOKEN:?CLOUDFLARE_API_TOKEN must be set}"
: "${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID must be set}"

MODEL="@cf/google/gemma-4-26b-a4b-it"
AI_URL="https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/run/${MODEL}"

# Deterministic question order: sort readingChains ids once.
KG_JSON="$(curl -sf "${BASE_URL}/knowledge-graph.json")"
CHAIN_IDS="$(jq -r '.readingChains | map(.id) | sort | .[]' <<<"$KG_JSON")"
# Word-split assignment (chain ids are slugs with no whitespace); avoids
# readarray/mapfile, which macOS's stock bash 3.2 lacks.
SORTED_CHAINS=($CHAIN_IDS)
CHAIN_COUNT=${#SORTED_CHAINS[@]}
if [ "$CHAIN_COUNT" -eq 0 ]; then
  echo "ERROR: no readingChains in ${BASE_URL}/knowledge-graph.json" >&2
  exit 1
fi

# Cluster lookup: the clusters[] entry whose posts array contains a slug.
find_cluster() {
  local slug=$1
  jq -r --arg slug "$slug" \
    '.clusters[]? | select(.id != null and (.posts | type == "array") and ($slug as $s | .posts | index($s)) != null) | .id' \
    <<<"$KG_JSON" | head -1
}

OUT_DIR="results/raw/${ARM}"
mkdir -p "$OUT_DIR"

fetch() {
  local url=$1
  curl -sf "$url" || { echo "ERROR: fetch failed: $url" >&2; exit 1; }
}

echo "Arm: $ARM"
echo "Base URL: $BASE_URL"
echo "Runs: $N"
echo "Output: $OUT_DIR"
EMPTY_COUNT=0

for i in $(seq 1 "$N"); do
  RUN_ID="$(printf 'run-%03d' "$i")"
  OUT="${OUT_DIR}/${RUN_ID}.json"
  if [ -s "$OUT" ]; then
    echo "skip $RUN_ID (already captured)"
    continue
  fi

  CHAIN="${SORTED_CHAINS[$(( (i - 1) % CHAIN_COUNT ))]}"

  # Expected sequence for scoring (resolved from knowledge-graph.json).
  EXPECTED=$(jq -c --arg chain "$CHAIN" \
    '[.readingChains[] | select(.id == $chain) | .sequence][0]' <<<"$KG_JSON")
  FIRST_SLUG=$(jq -r '.[0]' <<<"$EXPECTED")
  CLUSTER=$(find_cluster "$FIRST_SLUG")
  if [ -z "$CLUSTER" ]; then
    echo "ERROR: no cluster found for first slug '$FIRST_SLUG' (chain $CHAIN)" >&2
    exit 1
  fi

  # Per-arm grounding payload.
  case "$ARM" in
    llms-txt)
      PAYLOAD="$(fetch "${BASE_URL}/llms.txt")"
      ;;
    kg-json)
      SLICE_URL="${BASE_URL}/knowledge-graph/${CLUSTER}.json"
      PAYLOAD="${KG_JSON}
$(fetch "$SLICE_URL")"
      ;;
    okf-bundle)
      PAYLOAD="$(fetch "${BASE_URL}/okf/index.md")
$(fetch "${BASE_URL}/okf/clusters/${CLUSTER}/index.md")"
      ;;
    *) echo "ERROR: unknown arm '$ARM' (expected llms-txt|kg-json|okf-bundle)" >&2; exit 1 ;;
  esac

  PROMPT="${PAYLOAD}

Read the readingChains entry \"${CHAIN}\" in the provided payload. List its sequence in order. Respond with JSON {\"sequence\": [<slugs>]}."

  START=$(date +%s)
  ATTEMPTS=0
  RESPONSE=""
  RAW_RESPONSE=""
  EMPTY_AFTER_RETRIES=0
  # A reasoning model can spend the whole completion budget on
  # reasoning_content and return empty content (same fallback as the upstream
  # experiments/src/llm.ts caller: content first, then reasoning_content).
  # A successful HTTP response yielding BOTH empty is treated as a failed
  # attempt and retried within the same 3-attempt budget.
  while :; do
    ATTEMPTS=$((ATTEMPTS + 1))
    BODY=$(jq -n --arg prompt "$PROMPT" \
      '{messages: [{role: "user", content: $prompt}], max_completion_tokens: 2048, temperature: 0}')
    if RESPONSE=$(curl -s -X POST "$AI_URL" \
      -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
      -H 'Content-Type: application/json' -d "$BODY"); then
      if jq -e '.success == true' >/dev/null 2>&1 <<<"$RESPONSE"; then
        RAW_RESPONSE=$(jq -j '.result.choices[0].message.content // ""' <<<"$RESPONSE")
        if [ -z "$RAW_RESPONSE" ]; then
          RAW_RESPONSE=$(jq -j '.result.choices[0].message.reasoning_content // ""' <<<"$RESPONSE")
        fi
        if [ -n "$RAW_RESPONSE" ]; then
          break
        fi
        echo "WARN: attempt $ATTEMPTS returned empty content and reasoning_content (chain $CHAIN)" >&2
        if [ "$ATTEMPTS" -ge 3 ]; then
          EMPTY_AFTER_RETRIES=1
          break
        fi
        sleep $((2 ** ATTEMPTS))
        continue
      fi
    fi
    if [ "$ATTEMPTS" -ge 3 ]; then
      echo "ERROR: Workers AI failed after 3 attempts (chain $CHAIN)" >&2
      exit 1
    fi
    sleep $((2 ** ATTEMPTS))
  done
  END=$(date +%s)

  INPUT_TOKENS=$(jq -r '.result.usage.prompt_tokens' <<<"$RESPONSE")
  OUTPUT_TOKENS=$(jq -r '.result.usage.completion_tokens' <<<"$RESPONSE")

  RAW_FILE="$(mktemp)"
  printf '%s' "$RAW_RESPONSE" > "$RAW_FILE"
  if [ "$EMPTY_AFTER_RETRIES" -eq 1 ]; then
    # Nothing to score; persist usage metadata with a loud note.
    EXACT_MATCH=false
    PARTIAL_CREDIT=null
    NOTE="empty response after retries"
    EMPTY_COUNT=$((EMPTY_COUNT + 1))
    echo "EMPTY AFTER RETRIES: $RUN_ID (chain $CHAIN)"
  else
    SCORE=$(uv run python "${SCRIPT_DIR}/score.py" \
      <(printf '%s' "$KG_JSON") "$CHAIN" "$RAW_FILE")
    EXACT_MATCH=$(jq -r '.exact_match' <<<"$SCORE")
    PARTIAL_CREDIT=$(jq -r '.partial_credit' <<<"$SCORE")
    NOTE=null
  fi
  rm -f "$RAW_FILE"

  jq -n \
    --arg group "$ARM" \
    --arg session_id "${ARM}-${RUN_ID}" \
    --argjson input "$INPUT_TOKENS" \
    --argjson output "$OUTPUT_TOKENS" \
    --argjson wall "$((END - START))" \
    --arg raw "$RAW_RESPONSE" \
    --argjson exact "$EXACT_MATCH" \
    --argjson partial "$PARTIAL_CREDIT" \
    --arg note "$NOTE" \
    '{group: $group, session_id: $session_id, messages: 1,
      input_tokens: $input, output_tokens: $output,
      total_tokens: ($input + $output),
      wall_clock_seconds: $wall, bytes: ($raw | length),
      raw_response: $raw, exact_match: ($exact == 1),
      partial_credit: (if $partial == null then null else $partial end),
      note: ($note | if . == "null" then null else . end)}' > "$OUT"
  echo "captured $RUN_ID (chain $CHAIN, cluster $CLUSTER, exact=$EXACT_MATCH, partial=$PARTIAL_CREDIT)"
done

if [ "$EMPTY_COUNT" -gt 0 ]; then
  echo "============================================================" >&2
  echo "WARNING: $EMPTY_COUNT run(s) in arm '$ARM' returned empty" >&2
  echo "content and reasoning_content after 3 attempts (note:" >&2
  echo "'empty response after retries'). Inspect before scoring." >&2
  echo "============================================================" >&2
fi

echo "Done. Full raw responses in $OUT_DIR."
