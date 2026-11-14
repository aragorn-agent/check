# Limitations

> Read this before you use a report as a purchasing decision, a public claim, or a legal argument.

AgentApiAI Check measures a small number of observable behaviors at one moment. It is a ruler, not a judge. This page lists where the ruler is known to be wrong, blind, or easy to fool.

## 1. What a verdict means

| Verdict | Means |
| --- | --- |
| `pass` | The sampled behavior was consistent with the claim, at that moment, for that probe. |
| `suspect` | Something was inconsistent or missing, but not enough to call it a failure. |
| `fail` | The sampled behavior contradicted the claim, or the endpoint broke the protocol contract. |
| `skip` | There was not enough evidence to decide. **This is not a pass.** |

A `fail` on one check does **not** prove fraud. It proves that one observable contradicted one expectation. A relay can `fail` billing because its price list is stale, not because it is stealing.

## 2. Known false positives

Cases where a legitimate relay may be marked `suspect` or `fail`:

- **Region-specific tokenizers.** Some providers ship tokenizer variants per region or per model version. A Claude model served through a gateway with a re-tokenizing middleware can drift outside the 0.90–1.40 band.
- **Usage rewriting.** Gateways that normalize `usage` (for example, adding cached-token fields or re-counting with a local tokenizer) change the fingerprint without changing the backend.
- **Prompt caching.** A cached prompt can report fewer `prompt_tokens` than a cold one, which looks like a tokenizer shift.
- **Reasoning models.** Models that bill reasoning tokens in `completion_tokens` can exceed the parameter-adherence threshold (24 tokens for `max_tokens=16`) even when the parameter is honored.
- **Aggressive safety filters.** A context needle may be refused as suspicious content; the engine maps refusals to `skip`, but a partial refusal can look like a lost needle.
- **Load balancers with mixed versions.** Two versions of the same family behind one endpoint can produce two tokenizer clusters, which the engine reports as `suspect` (mixed pool).
- **Non-standard error envelopes.** Some relays wrap official errors in their own envelope. That is a compatibility finding, but it is not necessarily a sign of a swapped model.
- **Network middleboxes.** A corporate proxy that rewrites SSE or buffers chunks can make streaming look pseudo-streamed.

## 3. Known false negatives

Cases where a dishonest relay may still pass:

- **Forged `usage`.** A relay that copies the expected token counts and cost fields passes authenticity and billing while serving a different model. The fingerprint checks metadata, not the model's weights.
- **Correct-price billing on the sampled call.** A relay can bill the sampled request correctly and overcharge elsewhere (long outputs, cached tokens, peak hours, hidden fees).
- **One-path compliance.** A relay can special-case the invalid-model error path, the `max_tokens=16` call, and the forced tool call while other paths are broken.
- **Needle at 22.5%.** A relay that truncates at, say, 40% of the claimed window still recovers the needle. The check samples one depth.
- **Summarizing middleware.** A gateway that summarizes long prompts may still return the needle if the summary keeps it; the check does not verify fidelity of the rest.
- **Pseudo-streaming that satisfies the shape.** Two SSE chunks with text and a plausible TTFT pass, even if the whole answer was generated before the first chunk was sent.
- **Time-of-check effects.** A relay can behave correctly during a test and differently under production load, at other hours, or for other keys.

## 4. Per-check blind spots

| Check | Blind spot |
| --- | --- |
| Authenticity | Only six families have calibrated bands. Unknown models get `skip`. No band exists for image, embedding, rerank, or audio models. |
| Billing | Requires you to supply the official price. Without it: `skip`. No invoice reconciliation, no currency handling, no cache/reasoning token accounting. |
| Context | One needle depth, capped at 60,000 characters of filler. Does not test the full claimed window, multi-turn retention, or retrieval at several depths. |
| Error shapes | One invalid-model request. Does not cover auth errors, rate limits, quota errors, or streaming errors. |
| Parameters | `max_tokens` only. `temperature`, `top_p`, `stop`, `seed`, `response_format`, and penalties are not tested. |
| Tools | OpenAI protocols only in v0.1. Anthropic and Gemini tool calls are `skip`. No multi-turn or parallel tool calls. |
| Streaming | OpenAI Chat and Anthropic only. One request. TTFT is a single sample, not p50/p95. |

## 5. Environmental factors

A verdict can change between runs without any change at the relay:

- upstream provider incidents
- relay load and queueing
- your network path, proxy, or VPN
- DNS and TLS termination changes
- model deprecations and silent version upgrades
- price list updates

Run more than once before drawing a conclusion. Keep the timestamp; a report describes a moment.

## 6. What this tool is not

- **Not a security audit.** It does not test prompt injection, data exfiltration, key handling, logging practices, or isolation between customers.
- **Not a content-policy test.** It does not check moderation, jailbreak resistance, or output safety.
- **Not legal evidence.** A report is a technical observation, not a finding of fact in a dispute. It carries no chain of custody.
- **Not a certification.** A `pass` does not mean a relay is endorsed, safe, or honest. It means the sampled probes were consistent at that time.
- **Not a ranking.** The public directory has a separate, disclosed method. This tool does not produce scores, positions, or badges.

## 7. Authorized use

Only test endpoints you are authorized to use:

- your own endpoint, or one you hold a key for
- an endpoint whose operator asked you to test it
- a public evaluation endpoint that permits automated requests

Do not use this tool to overload, probe for vulnerabilities, or attack a service. A full run sends 12 requests and one long prompt; respect the provider's rate limits and terms. Publishing a report about a third party is your responsibility, not the tool's.

## 8. If you think a verdict is wrong

1. Re-run with a larger `--samples` value.
2. Re-run at a different time of day.
3. Check the evidence line, not just the verdict.
4. Open an issue with the report JSON (redact the key and any private host), the engine version, and the probe version.

False-positive reports are the most useful contribution this project can receive. The bands and thresholds are meant to be corrected by evidence.

## 9. Changes

Every change to a band, threshold, or decision rule bumps the probe registry version and is recorded in [methodology.md](methodology.md). A report keeps the version it ran with, so an old verdict can always be read against the rules that produced it.
