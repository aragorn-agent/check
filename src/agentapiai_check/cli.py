#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command-line interface for AgentApiAI Check."""
import argparse
import json
import os
import sys

from . import detect

VERDICT_COLORS = {
    "pass": "\033[32m",
    "suspect": "\033[33m",
    "fail": "\033[31m",
    "skip": "\033[90m",
}
RESET = "\033[0m"


def _color(text, verdict, enabled):
    if not enabled:
        return text
    return VERDICT_COLORS.get(verdict, "") + text + RESET


def _render_text(report, color=False):
    lines = []
    lines.append("AgentApiAI Check · %s" % report.get("checkedAt", ""))
    lines.append("Target    %s" % report.get("target", ""))
    lines.append("Model     %s" % report.get("model", ""))
    lines.append("Protocol  %s" % report.get("protocol", ""))
    if report.get("family"):
        lines.append("Family    %s" % report["family"])
    lines.append("Probes    v%s (%s)" % (
        report.get("probeVersion") or "?", report.get("probeUpdated") or "?"))
    lines.append("")
    width = max([20] + [len(i.get("label", "")) for i in report["items"]])
    lines.append("%-*s  %-8s  %s" % (width, "CHECK", "VERDICT", "EVIDENCE"))
    for item in report["items"]:
        verdict = item.get("verdict", "skip")
        evidence = item.get("evidence") or []
        first = evidence[0] if evidence else ""
        lines.append("%-*s  %s  %s" % (
            width, item.get("label", ""), _color("%-8s" % verdict, verdict, color), first))
        for line in evidence[1:]:
            lines.append("%-*s  %-8s  %s" % (width, "", "", line))
    s = report.get("summary") or {}
    lines.append("")
    lines.append("Overall: %s (%d pass, %d suspect, %d fail, %d skip)" % (
        _color(report.get("verdict", "skip"), report.get("verdict", "skip"), color),
        s.get("pass", 0), s.get("suspect", 0), s.get("fail", 0), s.get("skip", 0)))
    return "\n".join(lines)


def _md_escape(text):
    return str(text).replace("|", "\\|").replace("\n", "<br>")


def _render_markdown(report):
    lines = []
    lines.append("# AgentApiAI Check report")
    lines.append("")
    lines.append("- **Target:** `%s`" % report.get("target", ""))
    lines.append("- **Model:** `%s`" % report.get("model", ""))
    lines.append("- **Protocol:** `%s`" % report.get("protocol", ""))
    if report.get("family"):
        lines.append("- **Family:** `%s`" % report["family"])
    lines.append("- **Checked at:** %s" % report.get("checkedAt", ""))
    lines.append("- **Engine:** v%s · probes v%s (%s)" % (
        report.get("engineVersion", "?"), report.get("probeVersion") or "?",
        report.get("probeUpdated") or "?"))
    lines.append("- **Overall:** **%s**" % report.get("verdict", "skip"))
    lines.append("")
    lines.append("| Check | Verdict | Evidence |")
    lines.append("| --- | --- | --- |")
    for item in report["items"]:
        evidence = "<br>".join(_md_escape(e) for e in (item.get("evidence") or []))
        lines.append("| %s | `%s` | %s |" % (
            _md_escape(item.get("label", "")), item.get("verdict", "skip"), evidence))
    s = report.get("summary") or {}
    lines.append("")
    lines.append("Summary: %d pass, %d suspect, %d fail, %d skip." % (
        s.get("pass", 0), s.get("suspect", 0), s.get("fail", 0), s.get("skip", 0)))
    lines.append("")
    lines.append("> Key never leaves the machine. Reports contain no key material. "
                 "A `skip` verdict means insufficient evidence, not a pass.")
    return "\n".join(lines)


def _write_output(text, path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
        if not text.endswith("\n"):
            fh.write("\n")


def cmd_verify(args):
    key = args.key or os.environ.get("AGENTAPIAI_KEY") or ""
    if not key:
        print("error: provide --key or set AGENTAPIAI_KEY (the key is never stored).",
              file=sys.stderr)
        return 1
    protocol = "" if args.protocol == "auto" else args.protocol
    report = detect.full_report(
        args.base_url,
        key,
        args.model,
        family=args.family,
        official_in=args.official_input_price,
        official_out=args.official_output_price,
        claimed_ctx=args.claimed_context,
        protocol=protocol,
        samples=args.samples,
        timeout=args.timeout,
    )
    if args.format == "json":
        text = json.dumps(report, ensure_ascii=False, indent=2)
    elif args.format == "markdown":
        text = _render_markdown(report)
    else:
        color = (not args.no_color) and sys.stdout.isatty()
        text = _render_text(report, color=color)
    print(text)
    if args.output:
        _write_output(text, args.output)
    if args.json_output:
        _write_output(json.dumps(report, ensure_ascii=False, indent=2), args.json_output)

    verdict = report.get("verdict", "skip")
    if verdict == "pass":
        return 0
    if verdict == "suspect":
        return 3 if args.fail_on == "suspect" else 2
    if verdict == "fail":
        return 3
    return 4


def cmd_probes(args):
    summary = detect.probe_summary()
    if args.json:
        print(json.dumps({"summary": summary, "registry": detect.PROBES},
                         ensure_ascii=False, indent=2))
        return 0
    print("AgentApiAI Check probes v%s (%s)" % (
        summary.get("version"), summary.get("updated")))
    print("Requests: quick=%s full=%s" % (
        (summary.get("requestEstimate") or {}).get("quick"),
        (summary.get("requestEstimate") or {}).get("full")))
    print("")
    for probe in detect.PROBES.get("probes") or []:
        print("%-26s %-10s %-8s %s" % (
            probe.get("id", ""), probe.get("category", ""),
            probe.get("status", ""), probe.get("label", "")))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="agentapiai-check",
        description="The open-source ruler for AI API relays. Key never stored.",
    )
    p.add_argument("--version", action="version", version="agentapiai-check " + detect.VERSION)
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("verify", help="run seven checks against one endpoint")
    v.add_argument("--base-url", required=True,
                   help="relay base URL, e.g. https://api.example.com/v1")
    v.add_argument("--key", default="",
                   help="API key; prefer the AGENTAPIAI_KEY environment variable")
    v.add_argument("--model", required=True, help="model id, e.g. claude-sonnet-5-5")
    v.add_argument("--family", default="",
                   choices=["", "claude", "gpt", "gemini", "deepseek", "qwen", "grok"],
                   help="tokenizer family; inferred from --model when possible")
    v.add_argument("--protocol", default="auto",
                   choices=["auto", "openai-chat", "openai-responses", "anthropic", "gemini"],
                   help="wire protocol; inferred from --model when auto")
    v.add_argument("--official-input-price", type=float, default=None,
                   help="official input price in USD per 1M tokens (for billing check)")
    v.add_argument("--official-output-price", type=float, default=None,
                   help="official output price in USD per 1M tokens (for billing check)")
    v.add_argument("--claimed-context", type=int, default=None,
                   help="claimed context window in tokens (for the needle check)")
    v.add_argument("--samples", type=int, default=5, help="authenticity samples (default 5)")
    v.add_argument("--timeout", type=int, default=detect.TIMEOUT, help="per-request timeout seconds")
    v.add_argument("--format", default="text", choices=["text", "markdown", "json"])
    v.add_argument("--output", default="", help="also write the report to this path")
    v.add_argument("--json-output", default="", help="also write the raw JSON report to this path")
    v.add_argument("--fail-on", default="fail", choices=["fail", "suspect"],
                   help="exit non-zero on fail (default) or suspect as well")
    v.add_argument("--no-color", action="store_true", help="disable ANSI color")
    v.set_defaults(func=cmd_verify)

    pr = sub.add_parser("probes", help="print the probe registry")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_probes)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
