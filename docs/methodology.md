# Methodology

> Version: engine 0.1.0 · probes 1.0 (2026-11-13)
> This document describes what AgentApiAI Check does, what each verdict means, and what it cannot prove. It is the contract behind every report.

## 1. Scope

One run tests **one endpoint + one model at one moment**. It does not test a provider's whole catalog, its uptime history, its invoices, or its security posture.

The tool sends requests directly from your machine to the endpoint you specify. There is no control plane, no proxy, and no key escrow.

## 2. Protocols and endpoints

| Protocol | Base URL | Request path |
| --- | --- | --- |
| `openai-chat` | `https://relay.example/v1` | `/chat/completions` |
| `openai-responses` | `https://relay.example/v1` | `/responses` |
| `anthropic` | `https://relay.example/v1` | `/messages` (or `/v1/messages` if the base has no `/v1`) |
| `gemini` | `https://relay.example/v1` | `/v1beta/models/<model>:generateContent` |

The protocol is inferred from the model id unless you pass `--protocol`. Inference is a convenience, not a guarantee: pass `--protocol` when the relay uses a non-standard shape.

## 3. Checks

### 3.1 Model authenticity

**Probe.** Send the same fixed Chinese text (1,120 characters) five times with `max_tokens=32`.

**Signal.** `usage.prompt_tokens / len(probe)` is a tokenizer fingerprint. Families compress Chinese differently. The calibrated bands are:

| Family | Tokens per character |
| --- | --- |
| claude | 0.90–1.40 |
| gpt | 1.60–2.20 |
| gemini | 0.45–0.85 |
| deepseek | 0.45–0.95 |
| qwen | 0.45–0.85 |
| grok | 0.65–1.05 |

**Decision.**

- All samples outside the band → `fail` (possible substitution).
- Any sample far outside (below 0.8x or above 1.25x the band) → `fail` (mixed backend).
- All samples inside the band but split into multiple clusters (>8% apart) → `suspect` (possibly different versions or mixed pool).
- All samples inside one cluster → `pass`.
- No `prompt_tokens` at all → `suspect` (metadata anomaly).
- Unknown family → `skip` (no band to compare against).

**What it proves.** The tokenizer behavior is consistent with the claimed family at that moment.

**What it does not prove.** The exact model version. A relay can forge `usage` fields. A middleware can rewrite token counts. A different version of the same family may use a different tokenizer.

### 3.2 Billing

**Probe.** Send one short prompt, read `usage.prompt_tokens` and `usage.completion_tokens`, and compute the official-price cost:

```
expected = prompt_tokens / 1e6 * official_input_price
         + completion_tokens / 1e6 * official_output_price
```

**Decision.**

- No official price baseline → `skip`.
- Response has no cost field → `suspect` (the relay does not return `total_cost`; the check falls back to the official-price baseline).
- `|cost - expected| / expected` ≤ 15% → `pass`.
- 15%–50% → `suspect`.
- > 50% → `fail`.

**What it proves.** The cost field returned by the API is consistent with the official price for the sampled request.

**What it does not prove.** The invoice is correct. Cached tokens, reasoning tokens, rounding, and price changes can all change the real bill. You must pass the official prices you are comparing against.

### 3.3 Context

**Probe.** A short-prompt control first: place a random code (`MANGO-####`) in a short prompt and ask the model to return it. If the control fails, the check is `skip` — we cannot attribute a long-prompt failure to truncation.

Then place the same code at ~22.5% of the claimed context window (capped at 60,000 characters of filler), with a request to return the code.

**Decision.**

- Control fails → `skip`.
- Long request fails → `fail` (possible fake capacity or relay length limit).
- Code recovered → `pass`.
- Code not recovered → `fail`, unless the reply is a safety refusal (then `skip`).

**What it proves.** The endpoint can carry a prompt of roughly that size and the model can retrieve a mid-prompt marker.

**What it does not prove.** The full claimed window is usable. Some relays summarize, compress, or silently drop the middle. A single needle position is a sample, not a proof.

### 3.4 Error shapes

**Probe.** Request a non-existent model (`<model>-nonexist`) and inspect the response.

**Decision.**

- 4xx with the official top-level `error` object and required nested keys → `pass`.
- 4xx with the top-level object but incomplete nested keys → `suspect`.
- Non-4xx (for example 5xx or 200) → `fail`.

Official envelopes used:

- OpenAI: `{"error": {"message", "type", "code"}}`
- Anthropic: `{"error": {"type"}}`
- Gemini: `{"error": {"code", "message", "status"}}`

**What it proves.** The sampled invalid-model path follows the official error shape.

**What it does not prove.** Every error path is compliant. A relay can special-case this one path.

### 3.5 Parameter adherence

**Probe.** Ask the model to count from 1 to 100 with `max_tokens=16`.

**Decision.**

- `completion_tokens` ≤ 24 → `pass`.
- `completion_tokens` > 24 → `fail` (the backend ignored the parameter).
- Missing `completion_tokens` → `suspect`.

**What it proves.** `max_tokens` is honored on this request.

**What it does not prove.** `temperature`, `stop`, `top_p`, or other parameters are honored. Token counting differences can shift the boundary.

### 3.6 Tool calls

**Probe.** Force a `get_weather` function call via `tool_choice`. Only OpenAI Chat Completions and OpenAI Responses are covered in v0.1.

**Decision.**

- A `tool_calls` / `function_call` payload with the correct name → `pass`.
- Any other response → `fail`.
- Unsupported protocol → `skip`.

**What it proves.** The sampled tool-call path is wired through.

**What it does not prove.** Tool-call quality, multi-turn tool use, or parallel calls.

### 3.7 Streaming

**Probe.** Request `stream=true` and read SSE frames. Only OpenAI Chat Completions and Anthropic are covered in v0.1.

**Decision.**

- At least two `data:` chunks and a first-token time → `pass`.
- One chunk with text → `suspect` (possible pseudo-streaming).
- No content chunks → `fail`.
- Unsupported protocol → `skip`.

**What it proves.** SSE framing is present and the first token arrived.

**What it does not prove.** Streaming is never buffered under load. TTFT is a single sample, not a percentile.

## 4. Verdict aggregation

Per check: `pass` / `suspect` / `fail` / `skip`.

Overall rank: `fail` > `suspect` > `skip` > `pass`. A single `fail` makes the overall verdict `fail`; otherwise a `suspect` makes it `suspect`; otherwise a `skip` makes it `skip`; otherwise `pass`.

`skip` means **insufficient evidence**, not success. The CLI exits `4` when the overall verdict is `skip`.

## 5. Evidence and reproducibility

Each item records:

- check key and label
- verdict
- evidence lines (redacted)
- elapsed milliseconds
- billing facts, when applicable (expected cost, billed cost, multiplier, token counts)

The report records:

- engine version
- probe registry version and date
- model, inferred family, protocol
- endpoint **host** (not the full URL)
- timestamp in Asia/Shanghai

The key is never included. Redirects are disabled. No telemetry is sent.

To reproduce a report, run the same engine version against the same endpoint and model with the same official prices and claimed context. The endpoint's behavior may have changed; that is a finding, not a bug.

## 6. Request budget

A full run sends 12 requests:

| Check | Requests |
| --- | --- |
| Authenticity | 5 |
| Billing | 1 |
| Context | 2 |
| Errors | 1 |
| Parameters | 1 |
| Tools | 1 |
| Streaming | 1 |

A short prompt and a long prompt are billed by the relay as normal usage. The cost depends on the model and the relay's price. The tool does not reimburse usage.

## 7. Known limitations

See [limitations.md](limitations.md). Read it before using a report as a purchasing or legal decision.

## 8. Changes

The probe registry has a version and date in `probes.json`. Any change to a probe, a band, or a decision threshold must update the version and this document. Reports keep the version they ran with.
