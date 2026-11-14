#!/usr/bin/env bash
# OpenAI Chat Completions relay, e.g. a GPT-family endpoint.
# Exit codes: 0 pass · 2 suspect · 3 fail · 4 skip (see docs/methodology.md).
set -euo pipefail

: "${AGENTAPIAI_KEY:?set AGENTAPIAI_KEY in the environment first}"

exec agentapiai-check verify \
  --base-url "${RELAY_BASE_URL:-https://api.example.com/v1}" \
  --model "${MODEL:-gpt-5-5}" \
  --protocol openai-chat \
  --official-input-price "${IN_PRICE:-3}" \
  --official-output-price "${OUT_PRICE:-15}" \
  --claimed-context "${CLAIMED_CONTEXT:-200000}" \
  --samples "${SAMPLES:-5}" \
  --format markdown \
  --output report.md \
  --json-output report.json
