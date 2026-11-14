#!/usr/bin/env bash
# Gemini generateContent relay. Use a /v1 base; the client appends /v1beta/models/<model>.
# Exit codes: 0 pass · 2 suspect · 3 fail · 4 skip (see docs/methodology.md).
set -euo pipefail

: "${AGENTAPIAI_KEY:?set AGENTAPIAI_KEY in the environment first}"

exec agentapiai-check verify \
  --base-url "${RELAY_BASE_URL:-https://api.example.com/v1}" \
  --model "${MODEL:-gemini-3-pro}" \
  --protocol gemini \
  --official-input-price "${IN_PRICE:-1.25}" \
  --official-output-price "${OUT_PRICE:-10}" \
  --claimed-context "${CLAIMED_CONTEXT:-1000000}" \
  --samples "${SAMPLES:-5}" \
  --format markdown \
  --output report.md \
  --json-output report.json
