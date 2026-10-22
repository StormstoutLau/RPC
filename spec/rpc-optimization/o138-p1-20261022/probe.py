#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O-138 P1: Qwen3.8-Flash-Next Vulkan decode probe (C station :8080)."""
import argparse
import json
import random
import secrets
import time
import urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
MODEL = "qwen3.8-flash-next"
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


def post(payload, timeout=900):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    return body, time.time() - t0


def run(words, runs, max_tokens):
    for i in range(runs):
        salt = secrets.token_hex(8)
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": make_text(words, salt)}],
            "max_tokens": max_tokens,
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        body, wall = post(payload)
        t = body.get("timings", {})
        choice = (body.get("choices") or [{}])[0]
        print("RESULT " + json.dumps({
            "run": i + 1,
            "words": words,
            "salt": salt,
            "wall_s": round(wall, 3),
            "prompt_n": t.get("prompt_n"),
            "prompt_ms": t.get("prompt_ms"),
            "prompt_tps": t.get("prompt_per_second"),
            "predicted_n": t.get("predicted_n"),
            "predicted_ms": t.get("predicted_ms"),
            "predicted_tps": t.get("predicted_per_second"),
            "cache_n": t.get("cache_n"),
            "finish": choice.get("finish_reason"),
        }), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", type=int, required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=128)
    a = ap.parse_args()
    run(a.words, a.runs, a.max_tokens)


if __name__ == "__main__":
    main()
