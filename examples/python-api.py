// Call the detector as a library and inspect the report dict.
//   python examples/python-api.py
// The key is read from AGENTAPIAI_KEY and is never printed.
import json
import os
import sys

from agentapiai_check import full_report

key = os.environ.get("AGENTAPIAI_KEY", "")
if not key:
    sys.exit("set AGENTAPIAI_KEY first")

report = full_report(
    os.environ.get("RELAY_BASE_URL", "https://api.example.com/v1"),
    key,
    os.environ.get("MODEL", "gpt-5-5"),
    family=os.environ.get("FAMILY", "gpt"),
    official_in=float(os.environ.get("IN_PRICE", "3")),
    official_out=float(os.environ.get("OUT_PRICE", "15")),
    claimed_ctx=int(os.environ.get("CLAIMED_CONTEXT", "200000")),
    protocol=os.environ.get("PROTOCOL", "openai-chat"),
    samples=5,
)

print(json.dumps(report, ensure_ascii=False, indent=2))

# Fail loudly in CI; keep the JSON above as the artifact.
sys.exit({"pass": 0, "suspect": 2, "fail": 3, "skip": 4}[report["verdict"]])
