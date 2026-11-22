#!/usr/bin/env bash
# run-bench.sh - Exhibit-side bench runner for grounding-source-exhibit v2.
#
# v2 interface (seal-v2.json):
#
#   bash recipe/run-bench.sh <arm> <questions-file> <start> <count>
#
#   arm             one of: llms-txt | kg-json | okf-bundle | okf-index-relevant
#                   (okf-index-relevant is the v2.2 arm, seal-v3.json: a
#                   PER-QUESTION payload of freeze/okf/index.md plus only the
#                   cluster indexes and concept pages named by the item's
#                   derived gold-cluster set, per preregistration-v2.2.md)
#   questions-file  questions.json (blinded for pilot, plaintext for full;
#                   the v2.1 arms only read items[i].prompt so both work; the
#                   v2.2 arm also reads ground_truth and family for payload
#                   composition, so only the plaintext file supports it)
#   start           1-based index of the first item to run (pilot: 1)
#   count           number of items to run (pilot: 20, full: 63; F1=20, F2=20, F3=7, F4=16)
#
# Writes results/raw-v2/<arm>/run-NNN.json with the full raw response,
# finish_reason, usage, and v2 scores. Scoring via recipe/score-v2.py per
# the seal metric definitions (set equality + dice for F1/F3, integer
# match for F2, abstention scoring with the arm answerability map: F1 and
# F2 answerable only by kg-json, F3 answerable by kg-json and llms-txt (not
# okf-bundle), F4 answerable by all v2.1 arms and, under seal-v3.json
# (schema 2.2.0), also by the new okf-index-relevant arm.
#
# SEAL is parameterized per arm: the v2.1 arms verify against seal-v2.json,
# okf-index-relevant against seal-v3.json; SEAL_FILE overrides. The v2
# payload assembly below is untouched.
#
# Payload per arm:
#   llms-txt    the frozen snapshot text from freeze/llms.txt
#   kg-json     the FULL frozen snapshot text from freeze/knowledge-graph.json
#   okf-bundle  the FULL frozen bundle text: freeze/okf/index.md plus every
#               freeze/okf/clusters/<cluster>/index.md and concept page
#               (all frozen payloads are sha256-verified against
#               seal-v2.json frozen_payloads at run start; aborts loudly on
#               a missing file or hash mismatch)
#
# Requires: jq, uv (for score-v2.py). Env: CLOUDFLARE_API_TOKEN and
# CLOUDFLARE_ACCOUNT_ID must be set (never written to any file).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARM=${1:?usage: run-bench.sh <arm> <questions-file> <start> <count>}
QUESTIONS=${2:?usage: run-bench.sh <arm> <questions-file> <start> <count>}
START=${3:?usage: run-bench.sh <arm> <questions-file> <start> <count>}
COUNT=${4:?usage: run-bench.sh <arm> <questions-file> <start> <count>}
# Seal file per arm (v2.1 arms -> seal-v2.json, v2.2 arm -> seal-v3.json);
# SEAL_FILE env overrides for explicit reproduction runs.
case "$ARM" in
  okf-index-relevant) DEFAULT_SEAL="seal-v3.json" ;;
  *) DEFAULT_SEAL="seal-v2.json" ;;
esac
SEAL="${SEAL_FILE:-$DEFAULT_SEAL}"
SNAPSHOT="freeze/knowledge-graph.json"

: "${CLOUDFLARE_API_TOKEN:?CLOUDFLARE_API_TOKEN must be set}"
: "${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID must be set}"

MODEL="@cf/google/gemma-4-26b-a4b-it"
AI_URL="https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/run/${MODEL}"

# Portable sha256 helper: prefer coreutils sha256sum (Linux), fall back
# to shasum -a 256 (macOS). Both print the hex digest as the first field,
# so output is identical on either platform.
sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

# Verify every frozen payload listed in the arm's seal frozen_payloads
# before running: missing file or sha256 mismatch aborts loudly.
while IFS=$'\t' read -r EXPECTED_SHA FREEZE_PATH; do
  if [ ! -f "$FREEZE_PATH" ]; then
    echo "ERROR: frozen payload missing: $FREEZE_PATH" >&2
    exit 1
  fi
  ACTUAL_SHA=$(sha256_of "$FREEZE_PATH")
  if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
    echo "ERROR: frozen payload sha256 mismatch: $FREEZE_PATH: $ACTUAL_SHA (expected $EXPECTED_SHA)" >&2
    exit 1
  fi
done < <(jq -r '.frozen_payloads[] | "\(.sha256)\t\(.path)"' "$SEAL")

# Per-arm grounding payload, read once at run start from the frozen tree.
case "$ARM" in
  llms-txt)
    PAYLOAD="$(cat freeze/llms.txt)"
    ;;
  kg-json)
    PAYLOAD="$(cat "$SNAPSHOT")"
    ;;
  okf-bundle)
    PAYLOAD="$(cat freeze/okf/index.md)"
    # Every cluster index and concept page (full frozen bundle), same
    # enumeration the freeze used over index.md links.
    for CLUSTER_LINK in $(grep -oE '\]\(/clusters/[^)]+\)' freeze/okf/index.md \
        | tr -d '()]' | sort -u); do
      PAYLOAD="${PAYLOAD}
$(cat "freeze/okf${CLUSTER_LINK}")"
    done
    for CLUSTER in $(ls freeze/okf/clusters); do
      for CONCEPT in $(grep -oE '\]\([a-z0-9-]+\.md\)' \
          "freeze/okf/clusters/${CLUSTER}/index.md" | tr -d '()]' | sort -u); do
        PAYLOAD="${PAYLOAD}
$(cat "freeze/okf/clusters/${CLUSTER}/${CONCEPT}")"
      done
    done
    ;;
  # okf-index-relevant composes its payload per question inside the
  # item loop (PER_QUESTION_PAYLOAD=1); no fixed payload here.
  okf-index-relevant) : ;;
  *) echo "ERROR: unknown arm '$ARM' (expected llms-txt|kg-json|okf-bundle|okf-index-relevant)" >&2; exit 1 ;;
esac

# The v2.2 arm composes a PER-QUESTION payload inside the item loop; the
# v2 arms keep the fixed payloads assembled above (lines untouched).
case "$ARM" in
  okf-index-relevant) PER_QUESTION_PAYLOAD=1 ;;
  *) PER_QUESTION_PAYLOAD=0 ;;
esac

# Per-question payload composition for okf-index-relevant
# (preregistration-v2.2.md, pinned before sealing): freeze/okf/index.md
# plus, per derived gold cluster, its index and its linked concept pages.
# NOTE: per-question composition is deterministic only while the freeze
# tree and the questions file are unchanged; both are sha256-pinned in
# seal-v3.json (frozen_payloads + dataset) and enforced at run time by
# the per-item pin check in the item loop below. Derivation:
# nodes[].category -> clusters[] -> post-slug filenames (concept pages
# are post slugs, NOT nodes[].concepts slugs). All enumerations use
# `sort -u` (deterministic); prints one file path per line.
okf_relevant_pages() {
  python3 -c '
import json, pathlib, re, sys
questions, idx, snap, okf = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
import pathlib
questions, snap, okf = pathlib.Path(questions), pathlib.Path(snap), pathlib.Path(okf)
item = json.loads(open(questions).read())["items"][int(idx) - 1]
kg = json.loads(snap.read_text())
cat = {n["slug"]: n["category"] for n in kg["nodes"] if n["kind"] == "post"}
clusters = {c["id"]: c for c in kg["clusters"]}
fam = item["family"]
if fam == "F4":
    seeds = sorted({s for c in item["ground_truth"] for s in clusters[c]["posts"]})
elif fam == "F2":
    seeds = [re.search(r"slug ([a-z0-9-]+)", item["prompt"]).group(1)]
elif fam == "F1":
    src = re.search(r"slug ([a-z0-9-]+)", item["prompt"]).group(1)
    seeds = [src] + list(item["ground_truth"])
else:
    seeds = list(item["ground_truth"])
pages = [okf / "index.md"]
for c in sorted({cat[s] for s in seeds}):
    d = okf / "clusters" / c
    idxp = d / "index.md"
    pages.append(idxp)
    for p in sorted(set(re.findall(r"\(([a-z0-9-]+)\.md\)", idxp.read_text()))):
        f = d / (p + ".md")
        if f.is_file():
            pages.append(f)
print("\n".join(str(p) for p in pages))
' "$1" "$2" "$SNAPSHOT" freeze/okf
}

# Composed-payload sha256 using the exact derivation that produced the
# seal's per_question_payloads pins: python join of page texts, preserving
# per-file trailing newlines (bash command substitution strips them, so
# the pin check must not hash the shell-assembled PAYLOAD string).
okf_composed_sha() {
  okf_relevant_pages "$1" "$2" | python3 -c '
import hashlib, pathlib, sys
print(hashlib.sha256(
    "\n".join(pathlib.Path(p).read_text() for p in sys.stdin.read().splitlines())
    .encode()).hexdigest())
'
}

OUT_DIR="results/raw-v2/${ARM}"
mkdir -p "$OUT_DIR"

echo "Arm: $ARM"
echo "Questions: $QUESTIONS (items $START..$((START + COUNT - 1)))"
echo "Output: $OUT_DIR"
EMPTY_COUNT=0

for i in $(seq "$START" $((START + COUNT - 1))); do
  RUN_ID="$(printf 'run-%03d' "$i")"
  OUT="${OUT_DIR}/${RUN_ID}.json"
  if [ -s "$OUT" ]; then
    echo "skip $RUN_ID (already captured)"
    continue
  fi

  ITEM_ID=$(jq -r --argjson idx "$((i - 1))" '.items[$idx].id' "$QUESTIONS")
  FAMILY=$(jq -r --argjson idx "$((i - 1))" '.items[$idx].family' "$QUESTIONS")
  QUESTION_PROMPT=$(jq -r --argjson idx "$((i - 1))" '.items[$idx].prompt' "$QUESTIONS")
  if [ -z "$ITEM_ID" ] || [ "$ITEM_ID" = "null" ]; then
    echo "ERROR: no question item at index $i in $QUESTIONS" >&2
    exit 1
  fi

  if [ "$PER_QUESTION_PAYLOAD" = "1" ]; then
    # Pages are joined with a single newline, no leading newline; this
    # matches the sealed per_question_payloads composition exactly.
    PAYLOAD=""
    while IFS= read -r PAGE; do
      if [ ! -f "$PAGE" ]; then
        echo "ERROR: composed payload page missing: $PAGE (item $ITEM_ID)" >&2
        exit 1
      fi
      PAGE_TEXT="$(cat "$PAGE")"
      if [ -z "$PAYLOAD" ]; then
        PAYLOAD="$PAGE_TEXT"
      else
        PAYLOAD="${PAYLOAD}
${PAGE_TEXT}"
      fi
    done < <(okf_relevant_pages "$QUESTIONS" "$i")

    # Seal precondition 3: when the seal pins a composed payload for this
    # item, recompute the composed payload sha256 and abort loudly on
    # mismatch. Pilot items without a pin skip the check. The hash is
    # recomputed with the same derivation that produced the seal pins
    # (python join over the composed pages, preserving per-file trailing
    # newlines), so a freeze-tree or questions-file change is detected.
    EXPECTED_PIN=$(jq -r --arg id "$ITEM_ID" \
      '.per_question_payloads[] | select(.item_id == $id) | .sha256' "$SEAL")
    if [ -n "$EXPECTED_PIN" ] && [ "$EXPECTED_PIN" != "null" ]; then
      ACTUAL_PIN=$(okf_composed_sha "$QUESTIONS" "$i")
      if [ "$ACTUAL_PIN" != "$EXPECTED_PIN" ]; then
        echo "ERROR: composed payload sha256 mismatch for item $ITEM_ID: $ACTUAL_PIN (expected $EXPECTED_PIN)" >&2
        exit 1
      fi
    fi
  fi

  PROMPT="The payload below is the ONLY permitted knowledge source. Do not use any knowledge outside it. If the payload does not determine the answer, respond with {\"answer\": null}.

${PAYLOAD}

${QUESTION_PROMPT}"

  START_TS=$(date +%s)
  ATTEMPTS=0
  RESPONSE=""
  RAW_RESPONSE=""
  EMPTY_AFTER_RETRIES=0
  # A reasoning model can spend the whole completion budget on
  # reasoning_content and return empty content (same fallback as v1:
  # content first, then reasoning_content, then a JSON scan).
  while :; do
    ATTEMPTS=$((ATTEMPTS + 1))
    BODY=$(jq -n --arg prompt "$PROMPT" \
      '{messages: [{role: "user", content: $prompt}], max_completion_tokens: 4096, temperature: 0}')
    if RESPONSE=$(curl -s -X POST "$AI_URL" \
      -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
      -H 'Content-Type: application/json' -d "$BODY"); then
      if jq -e '.success == true' >/dev/null 2>&1 <<<"$RESPONSE"; then
        RAW_RESPONSE=$(jq -j '.result.choices[0].message.content // ""' <<<"$RESPONSE")
        REASONING=$(jq -j '.result.choices[0].message.reasoning_content // ""' <<<"$RESPONSE")
        if [ -z "$RAW_RESPONSE" ] && [ -n "$REASONING" ]; then
          RAW_RESPONSE="$REASONING"
        fi
        if [ -n "$RAW_RESPONSE" ]; then
          break
        fi
        # Both empty: try a balanced JSON scan over the whole response text.
        if [ -n "$(jq -r '.result.choices[0].message | tostring' <<<"$RESPONSE" \
            | grep -o '{"answer"[^}]*}' | head -1)" ]; then
          RAW_RESPONSE=$(jq -r '.result.choices[0].message | tostring' <<<"$RESPONSE")
          break
        fi
        echo "WARN: attempt $ATTEMPTS returned empty content and reasoning_content (item $ITEM_ID)" >&2
        if [ "$ATTEMPTS" -ge 3 ]; then
          EMPTY_AFTER_RETRIES=1
          break
        fi
        sleep $((2 ** ATTEMPTS))
        continue
      fi
    fi
    if [ "$ATTEMPTS" -ge 3 ]; then
      echo "ERROR: Workers AI failed after 3 attempts (item $ITEM_ID)" >&2
      exit 1
    fi
    sleep $((2 ** ATTEMPTS))
  done
  END=$(date +%s)

  FINISH_REASON=$(jq -r '.result.choices[0].finish_reason // "unknown"' <<<"$RESPONSE")
  PROMPT_TOKENS=$(jq -r '.result.usage.prompt_tokens // 0' <<<"$RESPONSE")
  COMPLETION_TOKENS=$(jq -r '.result.usage.completion_tokens // 0' <<<"$RESPONSE")
  REASONING_TOKENS=$(jq -r '.result.usage.reasoning_tokens // null' <<<"$RESPONSE")

  RAW_FILE="$(mktemp)"
  printf '%s' "$RAW_RESPONSE" > "$RAW_FILE"
  if [ "$EMPTY_AFTER_RETRIES" -eq 1 ]; then
    EXACT_MATCH=false
    PARTIAL_CREDIT=null
    ABSTAINED=null
    ITEM_SCORE=null
    NOTE="empty response after retries"
    EMPTY_COUNT=$((EMPTY_COUNT + 1))
    echo "EMPTY AFTER RETRIES: $RUN_ID (item $ITEM_ID)"
  else
    # Reasoning fallback: score LAST balanced answer object when the text
    # came from reasoning_content (mirrors score-v2.py semantics).
    SCORE_FLAGS=()
    if [ -n "$REASONING" ] && [ -z "$(jq -j '.result.choices[0].message.content // ""' <<<"$RESPONSE")" ]; then
      SCORE_FLAGS+=(--reasoning-fallback)
    fi
    SCORE=$(uv run python "${SCRIPT_DIR}/score-v2.py" "$QUESTIONS" "$ITEM_ID" "$RAW_FILE" --arm "$ARM" "${SCORE_FLAGS[@]+"${SCORE_FLAGS[@]}"}")
    EXACT_MATCH=$(jq -r '.exact_match' <<<"$SCORE")
    PARTIAL_CREDIT=$(jq -r '.partial_credit' <<<"$SCORE")
    ABSTAINED=$(jq -r '.abstained' <<<"$SCORE")
    ITEM_SCORE=$(jq -r '.item_score' <<<"$SCORE")
    NOTE=null
  fi
  rm -f "$RAW_FILE"

  jq -n \
    --arg group "$ARM" \
    --arg session_id "v2-${ARM}-${RUN_ID}" \
    --arg item_id "$ITEM_ID" \
    --arg family "$FAMILY" \
    --arg model "$MODEL" \
    --arg raw "$RAW_RESPONSE" \
    --arg finish_reason "$FINISH_REASON" \
    --argjson prompt_tokens "$PROMPT_TOKENS" \
    --argjson completion_tokens "$COMPLETION_TOKENS" \
    --argjson reasoning_tokens "$REASONING_TOKENS" \
    --argjson wall "$((END - START_TS))" \
    --argjson exact "$EXACT_MATCH" \
    --argjson partial "$PARTIAL_CREDIT" \
    --argjson abstained "$ABSTAINED" \
    --argjson item_score "$ITEM_SCORE" \
    --arg note "$NOTE" \
    '{group: $group, session_id: $session_id, item_id: $item_id,
      family: $family, model: $model,
      finish_reason: $finish_reason,
      prompt_tokens: $prompt_tokens,
      completion_tokens: $completion_tokens,
      reasoning_tokens: (if $reasoning_tokens == null then null else $reasoning_tokens end),
      wall_clock_seconds: $wall,
      raw_response: $raw,
      exact_match: ($exact == 1),
      partial_credit: (if $partial == null then null else $partial end),
      abstained: (if $abstained == null then null else $abstained end),
      item_score: (if $item_score == null then null else ($item_score == 1) end),
      note: ($note | if . == "null" then null else . end)}' > "$OUT"
  echo "captured $RUN_ID (item $ITEM_ID, family $FAMILY, exact=$EXACT_MATCH, partial=$PARTIAL_CREDIT, abstained=$ABSTAINED)"
done

if [ "$EMPTY_COUNT" -gt 0 ]; then
  echo "============================================================" >&2
  echo "WARNING: $EMPTY_COUNT run(s) in arm '$ARM' returned empty" >&2
  echo "content and reasoning_content after 3 attempts. Inspect" >&2
  echo "before scoring." >&2
  echo "============================================================" >&2
fi

echo "Done. Full raw responses in $OUT_DIR."
