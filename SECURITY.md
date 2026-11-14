# Security policy

## Supported versions

Only the latest release of `agentapiai-check` receives security fixes while the project is in alpha.

| Version | Supported |
| --- | --- |
| 0.1.x | yes |
| older | no |

## Reporting a vulnerability

**Do not open a public issue.**

Use GitHub's private reporting: go to the repository's **Security** tab → **Report a vulnerability**. If that is unavailable, write to **hello@agentapiai.com** with the subject line `security: agentapiai-check`.

Please include:

- the version (`agentapiai-check --version`) and the platform
- a description of the issue and its impact
- steps to reproduce, preferably a minimal script
- whether the issue requires a malicious relay, a malicious report file, or only local access

You will get an acknowledgement within 5 working days. We will tell you whether we accept the report, and we will credit you in the release notes unless you ask otherwise.

## Scope

In scope:

- key leakage (to disk, to logs, to a report, to another host, or through a redirect)
- request forgery or SSRF reachable through `--base-url`
- denial of service triggered by a malicious endpoint response (crash, unbounded memory, unbounded write)
- code execution or path traversal through report paths or probe data
- supply-chain issues in the build or release process

Out of scope:

- a relay lying in its responses. That is the product's subject matter, not a vulnerability; report it as a false negative in a normal issue.
- missing hardening that requires an already-compromised machine
- findings that require the user to pass an attacker-controlled `--key`
- rate limiting on a third-party endpoint

## Safe harbor

We will not pursue legal action against researchers who:

- test only on their own endpoint or a local fake relay,
- avoid privacy violations, data destruction, and service disruption,
- give us a reasonable window to fix the issue before publishing.

## How the tool handles secrets

- The key is read from `AGENTAPIAI_KEY` or `--key`, used to build an `Authorization` header, and kept in memory.
- The key is never written to a report, a log line, or an error message.
- Reports contain the endpoint host only; userinfo in the URL is stripped.
- Redirects are disabled, so a relay cannot bounce a request (and the key) to another host.
- There is no telemetry and no network call other than to the endpoint you specify.
