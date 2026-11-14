# Changelog

All notable changes to `agentapiai-check` are recorded here. The format follows Keep a Changelog, and the project uses semantic versioning. Verdict-affecting changes also bump the probe registry version; see [docs/methodology.md](docs/methodology.md).

## [0.1.0] — 2026-11-15

First public alpha.

### Added

- Local detector for four wire protocols: OpenAI Chat Completions, OpenAI Responses, Anthropic Messages, Gemini `generateContent`.
- Seven checks: model authenticity (tokenizer fingerprint), billing, context needle, error shapes, parameter adherence, tool calls, streaming.
- Three-state verdicts (`pass` / `suspect` / `fail`) with `skip` for insufficient evidence; overall aggregation ranks fail above suspect above skip above pass.
- CLI: `verify`, `probes`; text, Markdown, and JSON output; `--output` and `--json-output`; `--fail-on`; exit codes 0/1/2/3/4.
- Versioned probe registry (`probes.json`, v1.0, 2026-11-13).
- Composite GitHub Action that runs the checks and writes a job summary.
- Read-only Node directory client (`@agentapiai/check`).
- Documentation: methodology, limitations, security policy, trademark policy, CLA, contributing guide, code of conduct.
- Tests against a local fake relay: engine, CLI, exit codes, key redaction.

### Known gaps

- Anthropic and Gemini tool calls, and Gemini streaming, are `skip` in v0.1.
- Authenticity bands cover six families only.
- No SARIF output, no history diffing, no hosted reports.
