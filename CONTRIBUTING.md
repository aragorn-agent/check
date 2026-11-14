# Contributing

Thanks for helping improve the ruler. This project has an unusual contribution surface: most of its value is in **probes and decision rules**, not in features. Read this before opening a pull request.

## Ground rules

- Be civil. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- By contributing you agree to the [CLA](CLA.md): you keep your copyright, and you grant the project a license that includes commercial relicensing. Sign off every commit with `git commit -s` (DCO).
- Never include a real API key, a private endpoint, or a customer's report in a commit, an issue, or a screenshot.
- Do not add features that attack, overload, or fingerprint a third party beyond what the methodology describes.

## Development setup

```bash
git clone https://github.com/agentapiai/check.git
cd check
python -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

The package has no runtime dependencies and targets Python 3.9+. Keep it that way unless there is a strong reason.

## What lives where

| Path | Purpose |
| --- | --- |
| `src/agentapiai_check/detect.py` | protocol adapters, probes, decision rules |
| `src/agentapiai_check/cli.py` | argument parsing, rendering, exit codes |
| `src/agentapiai_check/probes.json` | versioned probe registry (data, not code) |
| `tests/test_detect.py` | fake relay + engine and CLI tests |
| `action/action.yml` | composite GitHub Action |
| `docs/methodology.md` | the contract behind every verdict |
| `docs/limitations.md` | known false positives and negatives |

## Adding or changing a probe

A probe is a claim plus a falsifiable test. A pull request that changes one must include:

1. **The claim.** One sentence: what does a `pass` mean?
2. **The evidence.** Which request, which field, which threshold, and why that threshold.
3. **The failure mode.** How can a legitimate relay fail it? Add the case to `docs/limitations.md`.
4. **The cost.** How many requests and how many tokens does it add?
5. **The version bump.** Update `version` and `updated` in `probes.json`, and update `docs/methodology.md` in the same PR.
6. **A test.** Extend `FakeRelay` so the probe has at least one passing and one failing path.

Probes that require sending customer data, storing a key, or calling a service other than the tested endpoint will not be merged.

## Changing a threshold or a band

Attach data. "The Claude band should be 0.85–1.45" needs sampled ratios from real endpoints, with dates and model ids, and an explanation of why the current band produced a wrong verdict. Threshold changes without evidence are declined.

## Code style

- Standard library only, Python 3.9 compatible.
- No new dependency without a discussion issue first.
- Keep user-facing report strings in English in `detect.py`; CLI rendering may localize later.
- Evidence lines must never contain the key, the full URL, or raw prompt text from a user.
- Error paths must degrade to `skip`, never to a silent `pass`.

## Pull request checklist

- [ ] `python -m unittest discover -s tests -v` passes
- [ ] no key, host, or private data in the diff
- [ ] `docs/methodology.md` updated if a rule changed
- [ ] `docs/limitations.md` updated if a new failure mode was added
- [ ] `probes.json` version bumped if a probe changed
- [ ] commit signed off (`git commit -s`)

## Out of scope

- ranking, scoring, or "best relay" features
- automatic publishing of results to third parties
- anything that requires holding a user's key server-side
- scrapers or crawlers for sites that do not permit them

Open an issue to discuss scope before writing a large patch.
