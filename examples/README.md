# Examples

Runnable examples for the local detector. Each script reads the key from `AGENTAPIAI_KEY`; none of them writes it to disk.

| File | Protocol | Notes |
| --- | --- | --- |
| `openai-chat.sh` | OpenAI Chat Completions | the common case for GPT-family relays |
| `openai-responses.sh` | OpenAI Responses | `/v1/responses` endpoints |
| `anthropic.sh` | Anthropic Messages | Claude-family relays |
| `gemini.sh` | Gemini `generateContent` | Gemini relays on a `/v1` base |
| `github-action.yml` | any | drop-in workflow step |
| `python-api.py` | any | call `full_report()` and inspect the dict |

Before running, install the package:

```bash
python -m pip install agentapiai-check
```

Set the key in the environment, never in the script:

```bash
export AGENTAPIAI_KEY="sk-..."
```

Pass official prices only if you want the billing check to run. Without them, billing returns `skip`, which is honest but less useful.

```bash
bash examples/anthropic.sh
```
