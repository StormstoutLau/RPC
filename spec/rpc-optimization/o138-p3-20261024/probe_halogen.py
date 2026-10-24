#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O-138 P3: decode probe — 与 P1 的 probe.py **逐字同逻辑**，仅把 URL 参数化。

P1 原文件：spec/rpc-optimization/o138-p1-20261022/probe.py（目标 :8080 = llama.cpp）
本文件：同一 prompt 生成、同一 timings 取数，`--url` 默认 :8731（halogen）。
用途 = 让两个引擎跑**同一 prompt 形状**，读数可对照。
"""
import argparse
import json
import random
import secrets
import time
import urllib.request

VOCAB = [
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa",
    "quebec", "romeo", "sierra", "tango", "uniform", "victor", "whiskey",
    "xray", "yankee", "zulu", "system", "memory", "network", "process",
    "thread", "buffer", "kernel", "driver", "device", "compute", "graph",
    "tensor", "matrix", "vector", "stream", "packet", "socket", "server",
    "client", "request", "response", "context", "token", "model", "engine",
    "cache", "prompt", "decode", "prefill", "latency", "throughput",
    "cluster", "station", "worker", "layer", "block", "window", "queue",
]


def make_text(words, salt):
    rng = random.Random(salt)
    body = " ".join(rng.choice(VOCAB) for _ in range(words))
    return "Run %s. %s\n\nWrite a long, detailed continuation of the above, with many paragraphs." % (salt, body)


def post(url, payload, timeout=1800):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    return body, time.time() - t0


def run(url, model, words, runs, max_tokens):
    for i in range(runs):
        salt = secrets.token_hex(8)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": make_text(words, salt)}],
            "max_tokens": max_tokens,
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        body, wall = post(url, payload)
        t = body.get("timings", {})
        choice = (body.get("choices") or [{}])[0]
        spec = t.get("speculation") or {}
        print("RESULT " + json.dumps({
            "run": i + 1,
            "words": words,
            "salt": salt,
            "wall_s": round(wall, 3),
            "prompt_n": t.get("prompt_n"),
            "prompt_tps": t.get("prompt_per_second"),
            "predicted_n": t.get("predicted_n"),
            "predicted_tps": t.get("predicted_per_second"),
            "drafter": spec.get("drafter"),
            "draft_n": t.get("draft_n"),
            "draft_accepted": t.get("draft_n_accepted"),
            "reasoning_tokens": (body.get("usage") or {}).get("completion_tokens_details", {}).get("reasoning_tokens"),
            "finish": choice.get("finish_reason"),
        }), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8731/v1/chat/completions")
    ap.add_argument("--model", default="qwen3.8-flash-next")
    ap.add_argument("--words", type=int, required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=128)
    a = ap.parse_args()
    run(a.url, a.model, a.words, a.runs, a.max_tokens)


if __name__ == "__main__":
    main()
