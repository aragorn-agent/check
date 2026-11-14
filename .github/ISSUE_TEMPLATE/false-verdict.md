---
name: A verdict looks wrong
about: Report a false positive or false negative from a real run
title: "[verdict] "
labels: ["verdict"]
---

**Do not paste your API key, your private endpoint, or anyone's customer data.** Redact the host if needed.

## What happened

- Engine version (`agentapiai-check --version`):
- Probe version (from the report `probes` line):
- Protocol and model:
- Verdict received:
- Verdict you expected:

## Evidence

Paste the relevant part of the report JSON (redacted). The `items` array is enough; drop `target` if the host is private.

```json

```

## Why you think the verdict is wrong

- [ ] The relay is known-good, and the check contradicts a second source.
- [ ] The evidence line is misread by the engine.
- [ ] A documented limitation in `docs/limitations.md` applies.
- [ ] Something else:

## Reproduction

- Did you re-run with `--samples 10`?
- Did you re-run at another time of day?
- Does the endpoint sit behind a proxy or gateway that rewrites payloads?
