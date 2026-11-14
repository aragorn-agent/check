#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AgentApiAI Check — detection engine.

Runs seven checks against one AI API relay endpoint, using the caller's key and
only standard-library HTTP. The key is used to build request headers and is
never written to disk, logged, or returned in a report.

Checks (three-state verdicts: pass / suspect / fail; `skip` = insufficient evidence):
  A. model authenticity — tokenizer fingerprint + metadata behavior
  B. billing           — usage tokens x official price vs returned cost field
  C. context           — needle at ~22.5% of the claimed window
  D. error shapes      — invalid request must return the official 4xx envelope
  E. parameter adherence — max_tokens honored
  F. tool calls        — forced tool call returns a valid payload
  G. streaming         — SSE frames and TTFT

Data discipline: evidence only, no invented conclusions. A check without
evidence is `skip`, not `pass`.
"""
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

VERSION = "0.1.0"
UA = "agentapiai-check/0.1 (+https://github.com/aragorn-agent/check)"
TIMEOUT = 60
PROTOCOLS = ("openai-chat", "openai-responses", "anthropic", "gemini")
ANTHROPIC_VERSION = "2023-06-01"
ERR_PROTOCOL = {"openai-chat": "openai", "openai-responses": "openai",
                "anthropic": "anthropic", "gemini": "gemini"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

# Official model signature table: tokens per character, calibrated against the
# fixed Chinese probe below (2026-11-12). Different tokenizers compress Chinese
# very differently; the same input must be used for every family.
SIG = {
    "claude": (0.90, 1.40),
    "gpt": (1.60, 2.20),
    "gemini": (0.45, 0.85),
    "deepseek": (0.45, 0.95),
    "qwen": (0.45, 0.85),
    "grok": (0.65, 1.05),
}
# Probe: fixed Chinese text (1120 characters), distinguishable per family.
MARKER = "介绍量子计算的基本原理，涉及叠加态、量子比特与量子纠缠。" * 40
# Official error envelopes.
ERR_SIG = {
    "openai": {"body_keys": ["error"], "err_keys": ["message", "type", "code"]},
    "anthropic": {"body_keys": ["error"], "err_keys": ["type"]},
    "gemini": {"body_keys": ["error"], "err_keys": ["code", "message", "status"]},
}
# family -> official error envelope
ERR_FAMILY = {"claude": "anthropic", "gpt": "openai", "qwen": "openai",
              "deepseek": "openai", "gemini": "gemini", "grok": "openai"}


def load_probes(path=None):
    """Load the probe registry; an unreadable file must not break detection."""
    p = Path(path) if path else Path(__file__).with_name("probes.json")
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


PROBES = load_probes()


def probe_summary():
    probes = PROBES.get("probes") or []
    active = [p for p in probes if p.get("status") == "active"]
    return {
        "version": PROBES.get("version"),
        "updated": PROBES.get("updated"),
        "categories": PROBES.get("categories") or [],
        "count": len(probes),
        "active": len(active),
        "requestEstimate": PROBES.get("requestEstimate") or {},
    }


def _post(url, payload, key, timeout=TIMEOUT, headers=None):
    """Low-level JSON POST. URL and auth headers are built by _request()."""
    h = {"Content-Type": "application/json", "User-Agent": UA}
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=h)
    t0 = time.time()
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode()), round(time.time() - t0, 2), None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:2000]
        except Exception:
            pass
        return e.code, body, round(time.time() - t0, 2), None
    except Exception as e:
        return None, None, None, str(e)


def infer_protocol(model):
    m = (model or "").lower()
    if "claude" in m or "anthropic" in m:
        return "anthropic"
    if "gemini" in m:
        return "gemini"
    return "openai-chat"


def infer_family(model):
    """Map a model id to the tokenizer signature family, or '' if unknown.

    Unknown families are not guessed: authenticity returns `skip` rather than a
    broad-band pass.
    """
    m = (model or "").lower()
    if "claude" in m or "anthropic" in m:
        return "claude"
    if "gemini" in m:
        return "gemini"
    if "deepseek" in m:
        return "deepseek"
    if "qwen" in m or "tongyi" in m:
        return "qwen"
    if "grok" in m:
        return "grok"
    if "gpt" in m or "openai" in m or m.startswith(("o1", "o3", "o4")):
        return "gpt"
    return ""


def _endpoint(base, protocol, model):
    root = (base or "").rstrip("/")
    if protocol == "openai-chat":
        return root + "/chat/completions"
    if protocol == "openai-responses":
        return root + "/responses"
    if protocol == "anthropic":
        return root + ("/messages" if root.endswith("/v1") else "/v1/messages")
    if protocol == "gemini":
        # A relay base often ends in /v1 (OpenAI-shaped); Gemini's native
        # surface lives under /v1beta, so do not stack them.
        if not root.endswith("/v1beta"):
            root = root[:-3] + "/v1beta" if root.endswith("/v1") else root + "/v1beta"
        return f"{root}/models/{model}:generateContent"
    return root + "/chat/completions"


def _payload(protocol, model, content, max_tokens, key):
    if protocol == "openai-chat":
        return ({"model": model, "max_tokens": max_tokens,
                 "messages": [{"role": "user", "content": content}]},
                {"Authorization": f"Bearer {key}"})
    if protocol == "openai-responses":
        return ({"model": model, "max_output_tokens": max_tokens, "input": content},
                {"Authorization": f"Bearer {key}"})
    if protocol == "anthropic":
        return ({"model": model, "max_tokens": max_tokens,
                 "messages": [{"role": "user", "content": content}]},
                {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION})
    if protocol == "gemini":
        return ({"contents": [{"parts": [{"text": content}]}],
                 "generationConfig": {"maxOutputTokens": max_tokens}},
                {"x-goog-api-key": key})
    return ({"model": model, "max_tokens": max_tokens,
             "messages": [{"role": "user", "content": content}]},
            {"Authorization": f"Bearer {key}"})


def _text_of(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(str(p.get("text") or "") for p in value if isinstance(p, dict))
    return ""


def _normalize(protocol, data):
    """Map four provider response dialects onto the shape the checks consume."""
    data = data if isinstance(data, dict) else {}
    if protocol == "openai-chat":
        choice = (data.get("choices") or [{}])[0] or {}
        text = _text_of((choice.get("message") or {}).get("content"))
        usage = data.get("usage") or {}
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        finish = choice.get("finish_reason")
    elif protocol == "openai-responses":
        text = str(data.get("output_text") or "")
        if not text:
            text = "".join(_text_of(item.get("content")) for item in (data.get("output") or [])
                           if isinstance(item, dict))
        usage = data.get("usage") or {}
        prompt, completion = usage.get("input_tokens"), usage.get("output_tokens")
        finish = data.get("status") or (data.get("incomplete_details") or {}).get("reason")
    elif protocol == "anthropic":
        text = "".join(str(b.get("text") or "") for b in (data.get("content") or [])
                       if isinstance(b, dict))
        usage = data.get("usage") or {}
        prompt, completion = usage.get("input_tokens"), usage.get("output_tokens")
        finish = data.get("stop_reason")
    else:
        cand = (data.get("candidates") or [{}])[0] or {}
        text = _text_of((cand.get("content") or {}).get("parts"))
        usage = data.get("usageMetadata") or {}
        prompt, completion = usage.get("promptTokenCount"), usage.get("candidatesTokenCount")
        finish = cand.get("finishReason")
    return {
        "text": text,
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
        "choices": [{"message": {"content": text}, "finish_reason": finish}],
        "total_cost": data.get("total_cost") or (data.get("usage") or {}).get("cost"),
        "_protocol": protocol,
        "_raw": data,
    }


def _request(base, key, model, content, max_tokens, protocol="openai-chat",
             timeout=TIMEOUT, raw=False):
    protocol = (protocol or "").strip().lower()
    if protocol not in PROTOCOLS:
        protocol = infer_protocol(model)
    url = _endpoint(base, protocol, model)
    payload, headers = _payload(protocol, model, content, max_tokens, key)
    st, data, dt, err = _post(url, payload, key, timeout, headers=headers)
    if raw or err or st != 200:
        return st, data, dt, err
    return st, _normalize(protocol, data), dt, err


def _usage(data):
    return (data or {}).get("usage") or {}


def check_authenticity(base, key, model, family, samples=5, protocol="openai-chat"):
    """A. Model authenticity: sample tokenizer ratio across N requests.

    A single sample can be fooled by channel rotation (one model name backed by
    several backends). This check repeats the same request and observes:
      - whether the fingerprint is stable (same input -> same prompt_tokens)
      - whether it falls inside the family's signature band
    A mix of in-band and out-of-band samples is a fail, with per-sample evidence.
    """
    ev, verdict = [], "pass"
    if family not in SIG:
        return "skip", [
            "unknown model family (%s): no tokenizer signature band; "
            "use --family claude|gpt|gemini|deepseek|qwen|grok" % (family or "—")
        ]
    lo, hi = SIG[family]
    ratios, oks, over_max = [], [], 0
    raw = []
    for _ in range(max(1, samples)):
        st, data, dt, err = _request(base, key, model, MARKER, 32, protocol)
        if err or st != 200:
            return "fail", [("request failed: HTTP %s %s" % (st, err or ""))[:200]]
        u = _usage(data)
        pt, ct = u.get("prompt_tokens"), u.get("completion_tokens")
        if not pt:
            raw.append((None, ct))
            continue
        ratio = pt / len(MARKER)
        ratios.append(ratio)
        oks.append(lo <= ratio <= hi)
        raw.append((pt, ct))
        if ct and ct > 32 * 1.5:
            over_max += 1
    if not ratios:
        return "suspect", ["usage has no prompt_tokens (metadata anomaly)"]
    # Cluster: within 8% is the same tokenizer; multiple clusters = multiple backends.
    clusters = []
    for r in sorted(ratios):
        if clusters and (r - clusters[-1][-1]) / clusters[-1][-1] <= 0.08:
            clusters[-1].append(r)
        else:
            clusters.append([r])
    centers = [round(sum(c) / len(c), 3) for c in clusters]
    stable = len(clusters) == 1
    spread = "%.3f" % ratios[0] if len(set(ratios)) == 1 else "%.3f–%.3f" % (min(ratios), max(ratios))
    ev.append(
        "tokenizer fingerprint over %d samples: %s tokens/char "
        "(family band %s–%s)" % (len(ratios), spread, lo, hi)
    )
    if not stable:
        ev.append(
            "same input produced %d fingerprint clusters %s "
            "→ likely multiple backends behind one model name" % (len(clusters), centers)
        )
    in_band = sum(oks)
    far_out = any(r < lo * 0.8 or r > hi * 1.25 for r in ratios)
    if in_band == 0:
        verdict = "fail"
        ev.append("all samples outside the family tokenizer band → model may be substituted")
    elif far_out:
        verdict = "fail"
        ev.append(
            "%d/%d samples inside the band, the rest far outside "
            "→ a non-family backend is mixed in" % (in_band, len(ratios))
        )
    elif in_band == len(ratios) and stable:
        verdict = "pass"
        ev.append("all samples inside the band and stable → consistent with the official tokenizer")
    elif in_band == len(ratios):
        verdict = "suspect"
        ev.append(
            "all samples inside the band but multiple clusters "
            "→ possibly different versions of the same family; re-test recommended"
        )
    else:
        verdict = "suspect"
        ev.append(
            "%d/%d samples inside the band, deviation below the substitution threshold "
            "→ possible mixed pool" % (in_band, len(ratios))
        )
    if over_max:
        ev.append(
            "%d/%d samples exceeded 1.5x max_tokens "
            "→ backend does not honor the parameter" % (over_max, len(ratios))
        )
    elif ratios and raw and raw[0][1]:
        ev.append("completion_tokens=%s (max_tokens=32): billing shape looks normal" % raw[0][1])
    ev.append("samples: %s" % ", ".join("%.2f" % r for r in ratios))
    choice = (data.get("choices") or [{}])[0] if isinstance(data, dict) else {}
    sr = choice.get("finish_reason") or choice.get("stop_reason")
    ev.append("finish_reason=%s (metadata behavior sample)" % sr)
    return verdict, ev


def check_billing(base, key, model, official_in, official_out, billed_out=None,
                  protocol="openai-chat", out=None):
    """B. Billing: usage x official price vs the relay's returned cost field.

    Without a complete official price baseline this returns `skip`, not a
    zero-priced guess. `out` receives the computed facts for the report layer.
    """
    if official_in is None or official_out is None:
        return "skip", [
            "no complete official price baseline (input/output missing); "
            "billing check skipped"
        ]
    verdict, ev = "pass", []
    st, data, dt, err = _request(base, key, model, "用一句话解释什么是 API。", 60,
                                 protocol, timeout=120)
    if err or st != 200:
        return "fail", ["request failed: HTTP %s %s" % (st, err or "")]
    u = _usage(data)
    pt, ct = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    expect = (pt / 1e6) * (official_in or 0) + (ct / 1e6) * (official_out or 0)
    ev.append(
        "official-price cost ≈ $%.6f (prompt %s + completion %s tokens; "
        "official input=%s / output=%s)" % (expect, pt, ct, official_in, official_out)
    )
    if expect <= 0:
        return "skip", ev + ["official-price cost is 0; insufficient evidence"]
    cost = data.get("total_cost") or (data.get("usage") or {}).get("cost")
    if cost is None:
        ev.append("response has no cost field (relay does not return total_cost) "
                  "→ billing check uses the official-price baseline")
        verdict = "suspect"
    else:
        drift = abs(cost - expect) / max(expect, 1e-9)
        ev.append("relay-reported cost $%.6f, drift %.1f%%" % (cost, drift * 100))
        if drift > 0.5:
            verdict = "fail"
        elif drift > 0.15:
            verdict = "suspect"
    if out is not None:
        out.update({
            "expected": round(expect, 6),
            "billed": (round(float(cost), 6) if cost is not None else None),
            "multiplier": (round(float(cost) / expect, 3) if cost is not None and expect > 0 else None),
            "officialInput": official_in,
            "officialOutput": official_out,
            "promptTokens": pt,
            "completionTokens": ct,
        })
    return verdict, ev


def check_context(base, key, model, claimed_ctx, protocol="openai-chat"):
    """C. Context: place a needle at ~22.5% of the claimed window and retrieve it.

    A short-prompt control first proves the model can follow the instruction;
    only then can a long-prompt failure be attributed to truncation.
    """
    if not claimed_ctx or claimed_ctx < 16000:
        return "skip", ["claimed context too short; needle test skipped"]
    ev = []
    code = "MANGO-%d" % (int(time.time()) % 10000)
    needle = "本次会话的暗号是 %s。" % code
    st, data, dt, err = _request(base, key, model,
                                 "%s\n请只回答本次会话的暗号。" % needle, 24, protocol)
    if err or st != 200:
        return "skip", ["short-prompt control failed: HTTP %s; cannot judge long context" % st]
    ctrl = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "") or ""
    if code not in ctrl:
        return "skip", ["short-prompt control did not return the code (model behavior anomaly); "
                        "needle test skipped: %r" % ctrl[:60]]
    ev.append("short-prompt control: code recovered (model follows the instruction)")
    half = min(int(claimed_ctx * 0.225), 60000)
    filler_a = "这是填充段落。" * (half // 6)
    filler_b = "这是填充段落。" * (half // 6)
    prompt = "%s\n%s\n%s\n请只回答本次会话的暗号。" % (filler_a, needle, filler_b)
    st, data, dt, err = _request(base, key, model, prompt, 30, protocol, timeout=180)
    if err or st != 200:
        return "fail", ev + ["long-context request failed: HTTP %s (possible fake capacity or "
                             "relay length limit)" % st]
    txt = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "") or ""
    hit = code in txt
    pos = len(filler_a)
    ev.append("needle at %dK chars → %s" % (pos // 1000, "recovered" if hit else "not recovered"))
    if not hit:
        ev.append("model reply: %r" % txt[:80])
        if re.search(r"注入|injection|不会执行|无法执行", txt):
            ev.append("model refused under a safety policy (not truncation) → this needle test is skip")
            return "skip", ev
    return ("pass" if hit else "fail"), ev


def check_errors(base, key, model, family, protocol="openai-chat"):
    """D. Error shapes: an invalid request must return the official 4xx envelope."""
    verdict, ev = "pass", []
    proto_sig = ERR_PROTOCOL.get(protocol if protocol in PROTOCOLS else infer_protocol(model))
    sig = ERR_SIG.get(proto_sig or ERR_FAMILY.get(family or "", ""))
    if not sig:
        return "skip", ["unknown family; error-shape comparison skipped"]
    st, body, dt, err = _request(base, key, model + "-nonexist", "x", 5,
                                 protocol, raw=True)
    if st is None:
        return "fail", ["connection failed: %s" % (err or "")]
    try:
        j = json.loads(body) if isinstance(body, str) else body
    except Exception:
        j = {}
    top_ok = all(k in (j or {}) for k in sig["body_keys"]) if isinstance(j, dict) else False
    err_obj = (j or {}).get("error") if isinstance(j, dict) else None
    nested_ok = isinstance(err_obj, dict) and all(k in err_obj for k in sig["err_keys"])
    client_err = 400 <= int(st or 0) < 500
    ev.append("error response HTTP %s, top-level keys %s" % (
        st, list(j.keys())[:5] if isinstance(j, dict) else type(j).__name__))
    ev.append("error body %s the official shape (requires %s + %s)" % (
        "matches" if top_ok and nested_ok else "deviates from",
        sig["body_keys"], sig["err_keys"]))
    if client_err and top_ok and nested_ok:
        return "pass", ev
    if client_err and top_ok:
        ev.append("4xx but the error object is incomplete → error response may be rewritten")
        return "suspect", ev
    if not client_err:
        ev.append("invalid model returned %s (official semantics require 4xx) → "
                  "not handling errors as the official API does" % st)
        return "fail", ev
    return "suspect", ev


def check_params(base, key, model, protocol="openai-chat"):
    """E. Parameter adherence: max_tokens=16 must actually truncate."""
    st, data, dt, err = _request(base, key, model,
                                 "请从 1 数到 100，只输出数字，用逗号分隔。", 16, protocol)
    if err or st != 200:
        return "skip", ["parameter probe failed: HTTP %s %s" % (st, err or "")]
    u = _usage(data)
    ct = u.get("completion_tokens")
    finish = ((data.get("choices") or [{}])[0] or {}).get("finish_reason")
    ev = ["max_tokens=16, completion_tokens=%s, finish_reason=%s" % (ct, finish)]
    if ct is None:
        return "suspect", ev + ["response has no completion_tokens; cannot verify adherence"]
    if ct <= 24:
        return "pass", ev + ["output correctly truncated → backend honors max_tokens"]
    return "fail", ev + ["output %s tokens exceeds 1.5x max_tokens=16 → backend ignores the parameter" % ct]


def check_tools(base, key, model, protocol="openai-chat"):
    """F. Tool calls: a forced function call must return a valid payload."""
    if protocol not in ("openai-chat", "openai-responses"):
        return "skip", ["%s tool-call format is not covered in v0.1; skipped" % protocol]
    payload, headers = _payload(protocol, model, "北京现在天气怎么样？必须调用工具查询。", 64, key)
    tool = {"type": "function", "function": {
        "name": "get_weather", "description": "查询指定城市当前天气",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}},
                       "required": ["city"]}}}
    if protocol == "openai-chat":
        payload["tools"] = [tool]
        payload["tool_choice"] = {"type": "function", "function": {"name": "get_weather"}}
    else:
        payload["tools"] = [{"type": "function", "name": "get_weather",
                             "description": "查询指定城市当前天气",
                             "parameters": tool["function"]["parameters"]}]
        payload["tool_choice"] = {"type": "function", "name": "get_weather"}
    st, data, dt, err = _post(_endpoint(base, protocol, model), payload, key, headers=headers)
    if err or st != 200:
        return "fail", ["tool-call request failed: HTTP %s %s" % (st, err or "")]
    raw = data if isinstance(data, dict) else {}
    if protocol == "openai-chat":
        msg = ((raw.get("choices") or [{}])[0] or {}).get("message") or {}
        calls = msg.get("tool_calls") or []
        name = ((calls[0] or {}).get("function") or {}).get("name") if calls else ""
    else:
        calls = [c for c in (raw.get("output") or []) if isinstance(c, dict) and c.get("type") == "function_call"]
        name = (calls[0] or {}).get("name") if calls else ""
    ev = ["forced tool_choice=get_weather → %d tool call(s) returned" % len(calls)]
    if calls and name == "get_weather":
        return "pass", ev + ["tool-call structure and name are correct"]
    return "fail", ev + ["did not follow the tool protocol (name=%s) → tools may be stripped or "
                         "the response rewritten" % (name or "—")]


def check_stream(base, key, model, protocol="openai-chat"):
    """G. Streaming: SSE must arrive in chunks; record time to first token."""
    if protocol not in ("openai-chat", "anthropic"):
        return "skip", ["%s streaming format is not covered in v0.1; skipped" % protocol]
    payload, headers = _payload(protocol, model, "用一句话解释什么是流式输出。", 48, key)
    payload["stream"] = True
    h = {"Content-Type": "application/json", "User-Agent": UA}
    h.update(headers)
    req = urllib.request.Request(_endpoint(base, protocol, model),
                                 data=json.dumps(payload).encode(), headers=h)
    t0 = time.time()
    ttft, chunks, text = None, 0, ""
    ctype = ""
    try:
        with _OPENER.open(req, timeout=TIMEOUT) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            for raw in r:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                try:
                    j = json.loads(body)
                except Exception:
                    continue
                chunks += 1
                if protocol == "openai-chat":
                    delta = ((j.get("choices") or [{}])[0].get("delta") or {}).get("content") or ""
                else:
                    delta = (j.get("delta") or {}).get("text") or ""
                if delta and ttft is None:
                    ttft = round(time.time() - t0, 2)
                text += delta
                if len(text) > 120:
                    break
    except urllib.error.HTTPError as e:
        return "fail", ["streaming request HTTP %s → not SSE" % e.code]
    except Exception as e:
        return "skip", ["streaming request error: %s" % str(e)[:160]]
    ev = ["Content-Type=%s, %d data chunks, first token %ss" % (
        ctype or "—", chunks, ttft if ttft is not None else "—")]
    if chunks >= 2 and ttft is not None:
        return "pass", ev + ["SSE chunks arrive incrementally"]
    if chunks == 1 and text:
        return "suspect", ev + ["only one data chunk → possibly pseudo-streaming "
                                "(whole response emitted at once)"]
    return "fail", ev + ["no SSE content chunks parsed"]


# Rank used to combine item verdicts. fail > suspect > skip > pass.
_RANK = {"pass": 0, "skip": 1, "suspect": 2, "fail": 3}


def full_report(base, key, model, family=None, official_in=None, official_out=None,
                claimed_ctx=None, protocol="", samples=5, timeout=TIMEOUT):
    """Run all seven checks and return a report dict.

    The report never contains the key. `target` is the endpoint host only.
    """
    protocol = (protocol or "").strip().lower()
    if protocol not in PROTOCOLS:
        protocol = infer_protocol(model)
    family = (family or infer_family(model)).strip().lower()
    checks = [
        ("authenticity", "Model authenticity",
         lambda: check_authenticity(base, key, model, family, samples=samples, protocol=protocol)),
        ("billing", "Billing",
         lambda: check_billing(base, key, model, official_in, official_out,
                               protocol=protocol, out=billing_facts)),
        ("context", "Context",
         lambda: check_context(base, key, model, claimed_ctx, protocol=protocol)),
        ("errors", "Error shapes",
         lambda: check_errors(base, key, model, family, protocol=protocol)),
        ("params", "Parameter adherence",
         lambda: check_params(base, key, model, protocol=protocol)),
        ("tools", "Tool calls",
         lambda: check_tools(base, key, model, protocol=protocol)),
        ("stream", "Streaming",
         lambda: check_stream(base, key, model, protocol=protocol)),
    ]
    report = {
        "engine": "agentapiai-check",
        "engineVersion": VERSION,
        "probeVersion": PROBES.get("version"),
        "probeUpdated": PROBES.get("updated"),
        "model": model,
        "family": family or None,
        "protocol": protocol,
        "target": _host(base),
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "items": [],
    }
    billing_facts = {}
    overall = "pass"
    for key_name, label, fn in checks:
        t0 = time.time()
        try:
            v, ev = fn()
        except Exception as e:
            v, ev = "fail", ["check error: %s" % e]
        item = {
            "key": key_name,
            "label": label,
            "verdict": v,
            "evidence": ev,
            "ms": int((time.time() - t0) * 1000),
        }
        if key_name == "billing" and billing_facts:
            item["facts"] = dict(billing_facts)
        report["items"].append(item)
        if _RANK.get(v, 0) > _RANK.get(overall, 0):
            overall = v
    report["verdict"] = overall
    report["summary"] = {
        "pass": sum(1 for i in report["items"] if i["verdict"] == "pass"),
        "suspect": sum(1 for i in report["items"] if i["verdict"] == "suspect"),
        "fail": sum(1 for i in report["items"] if i["verdict"] == "fail"),
        "skip": sum(1 for i in report["items"] if i["verdict"] == "skip"),
    }
    return report


def _host(base):
    """Return the host (and port) of a base URL without credentials."""
    try:
        from urllib.parse import urlsplit
        p = urlsplit(base or "")
        return p.hostname + ((":" + str(p.port)) if p.port else "")
    except Exception:
        return ""
