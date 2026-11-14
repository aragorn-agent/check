#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the detection engine and CLI using a local fake relay."""
import contextlib
import io
import json
import re
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agentapiai_check import cli, detect


class FakeRelay(BaseHTTPRequestHandler):
    """A tiny OpenAI-chat-compatible relay with deterministic behavior."""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # silence test output
        pass

    def _send(self, code, payload, ctype="application/json"):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode() or "{}")
        except Exception:
            payload = {}
        model = str(payload.get("model") or "")
        if model.endswith("-nonexist"):
            self._send(400, {"error": {
                "message": "model not found",
                "type": "invalid_request_error",
                "code": "model_not_found",
            }})
            return

        messages = payload.get("messages") or []
        content = ""
        if messages:
            content = str((messages[-1] or {}).get("content") or "")
        elif payload.get("input"):
            content = str(payload.get("input") or "")

        # Streaming probe
        if payload.get("stream"):
            chunks = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"content": " world"}}]},
            ]
            body = "".join("data: %s\n\n" % json.dumps(c) for c in chunks)
            body += "data: [DONE]\n\n"
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # Tool-call probe
        if payload.get("tools"):
            self._send(200, {
                "choices": [{
                    "message": {"role": "assistant", "tool_calls": [{
                        "id": "call_1", "type": "function",
                        "function": {"name": "get_weather", "arguments": "{\"city\":\"北京\"}"},
                    }]},
                    "finish_reason": "tool_calls",
                }],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            })
            return

        # Context needle probe
        match = re.search(r"MANGO-\d+", content)
        if match:
            self._send(200, {
                "choices": [{"message": {"role": "assistant",
                                         "content": "暗号是 %s。" % match.group(0)},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": max(1, int(len(content) * 1.8)),
                          "completion_tokens": 8},
            })
            return

        # Parameter-adherence probe: max_tokens=16 must truncate
        if payload.get("max_tokens") == 16:
            self._send(200, {
                "choices": [{"message": {"role": "assistant", "content": "1,2,3"},
                             "finish_reason": "length"}],
                "usage": {"prompt_tokens": max(1, int(len(content) * 1.8)),
                          "completion_tokens": 16},
            })
            return

        # Default (authenticity / billing): gpt-like ratio 1.8, price 3/15 USD per 1M.
        pt = max(1, int(len(content) * 1.8))
        ct = 10 if payload.get("max_tokens") == 32 else 20
        cost = (pt * 3.0 + ct * 15.0) / 1e6
        self._send(200, {
            "choices": [{"message": {"role": "assistant", "content": "ok"},
                         "finish_reason": "length"}],
            "usage": {"prompt_tokens": pt, "completion_tokens": ct},
            "total_cost": cost,
        })


class FakeRelayCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeRelay)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d/v1" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()


class TestHelpers(unittest.TestCase):
    def test_infer_family(self):
        self.assertEqual(detect.infer_family("claude-sonnet-5-5"), "claude")
        self.assertEqual(detect.infer_family("gpt-5-5"), "gpt")
        self.assertEqual(detect.infer_family("gemini-3-pro"), "gemini")
        self.assertEqual(detect.infer_family("deepseek-v4"), "deepseek")
        self.assertEqual(detect.infer_family("qwen-max"), "qwen")
        self.assertEqual(detect.infer_family("grok-5"), "grok")
        self.assertEqual(detect.infer_family("unknown-model"), "")

    def test_endpoint_gemini_does_not_stack_v1beta(self):
        url = detect._endpoint("https://relay.example/v1", "gemini", "gemini-3-pro")
        self.assertEqual(url, "https://relay.example/v1beta/models/gemini-3-pro:generateContent")
        url = detect._endpoint("https://relay.example/v1beta", "gemini", "gemini-3-pro")
        self.assertEqual(url, "https://relay.example/v1beta/models/gemini-3-pro:generateContent")

    def test_host_removes_credentials(self):
        self.assertEqual(detect._host("https://user:pass@relay.example/v1"), "relay.example")


class TestFullReport(FakeRelayCase):
    def test_full_report_passes_against_fake_relay(self):
        report = detect.full_report(
            self.base, "sk-test", "gpt-5-5",
            family="gpt",
            official_in=3.0, official_out=15.0,
            claimed_ctx=20000,
            protocol="openai-chat",
            samples=2,
        )
        self.assertEqual(report["verdict"], "pass", report)
        self.assertEqual(report["target"], "127.0.0.1:%d" % self.server.server_address[1])
        items = {i["key"]: i for i in report["items"]}
        self.assertEqual(items["authenticity"]["verdict"], "pass")
        self.assertEqual(items["billing"]["verdict"], "pass")
        self.assertEqual(items["context"]["verdict"], "pass")
        self.assertEqual(items["errors"]["verdict"], "pass")
        self.assertEqual(items["params"]["verdict"], "pass")
        self.assertEqual(items["tools"]["verdict"], "pass")
        self.assertEqual(items["stream"]["verdict"], "pass")
        self.assertNotIn("sk-test", json.dumps(report))

    def test_unknown_family_skips_authenticity(self):
        report = detect.full_report(
            self.base, "sk-test", "unknown-model",
            protocol="openai-chat", samples=1,
        )
        items = {i["key"]: i for i in report["items"]}
        self.assertEqual(items["authenticity"]["verdict"], "skip")
        self.assertIn("unknown model family", items["authenticity"]["evidence"][0])

    def test_billing_skips_without_prices(self):
        report = detect.full_report(
            self.base, "sk-test", "gpt-5-5",
            family="gpt", protocol="openai-chat", samples=1,
        )
        items = {i["key"]: i for i in report["items"]}
        self.assertEqual(items["billing"]["verdict"], "skip")


class TestCli(FakeRelayCase):
    def test_cli_json_exit_zero(self):
        out = io.StringIO()
        argv = [
            "verify", "--base-url", self.base, "--key", "sk-test",
            "--model", "gpt-5-5", "--family", "gpt",
            "--official-input-price", "3", "--official-output-price", "15",
            "--claimed-context", "20000", "--samples", "2",
            "--format", "json", "--no-color",
        ]
        with contextlib.redirect_stdout(out):
            code = cli.main(argv)
        self.assertEqual(code, 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report["verdict"], "pass")

    def test_cli_missing_key(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main([
                "verify", "--base-url", self.base, "--model", "gpt-5-5",
                "--format", "json",
            ])
        self.assertEqual(code, 1)
        self.assertIn("AGENTAPIAI_KEY", err.getvalue())

    def test_cli_markdown_contains_no_key(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main([
                "verify", "--base-url", self.base, "--key", "sk-secret-value",
                "--model", "gpt-5-5", "--family", "gpt", "--samples", "1",
                "--format", "markdown",
            ])
        text = out.getvalue()
        self.assertIn("# AgentApiAI Check report", text)
        self.assertNotIn("sk-secret-value", text)
        self.assertIn(code, (0, 2, 3, 4))


if __name__ == "__main__":
    unittest.main()
