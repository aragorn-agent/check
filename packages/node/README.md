# @agentapiai/check — Node directory client

Read-only client for the public agentapiai.com API. It reads the directory and published verdicts; **it does not run the local detector**. For local detection, use the Python package (`pip install agentapiai-check`) or the [GitHub Action](../../action/action.yml).

```bash
npx @agentapiai/check sites --grade a --limit 10
npx @agentapiai/check site totokenscc
npx @agentapiai/check stats
npx @agentapiai/check detect api.example.com
npx @agentapiai/check reports
```

No API key. No writes. No telemetry.

| Command | Reads | Returns |
| --- | --- | --- |
| `sites` | `GET /v1/sites` | table of sites: grade, online, latency, samples, slug |
| `site <slug>` | `GET /v1/sites/<slug>` | full site record as JSON |
| `stats` | `GET /v1/stats` | dataset snapshot as JSON |
| `detect <host>` | `GET /v1/detect/latest?host=` | latest **published** verdict for a host |
| `reports` | `GET /v1/reports` | published reports |

Options for `sites`: `--limit`, `--grade a|b|c`, `--q text`, `--sort samples|online|latency|price|name`.

Set `AGENTAPIAI_API` to point at a staging host; the default is `https://agentapiai.com`.

## What the data means

Grades describe **availability and latency only**. They are not a statement about model authenticity. A published verdict is the result of one run at one time; read [docs/limitations.md](../../docs/limitations.md) before treating it as more than that.

The dataset snapshot is licensed CC BY 4.0; cite it as described in the [main README](../../README.md#use-the-public-data). This package's code is Apache-2.0.
