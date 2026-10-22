#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EV-14 probe: llama-server on B (127.0.0.1:8080)."""
import argparse
import json
import random
import secrets
import time
import urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
MODEL = "deepseek-v4-flash-0731"
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
    return "Run %s. " % salt + " ".join(rng.choice(VOCAB) for _ in range(words))


def post(payload, timeout=600):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    return body, time.time() - t0


def emit(obj):
    print("RESULT " + json.dumps(obj), flush=True)


def prefill(words, runs):
    for i in range(runs):
        salt = secrets.token_hex(8)
        text = make_text(words, salt) + "\n\nReply with OK."
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 1,
            "temperature": 0,
        }
        body, wall = post(payload)
        t = body.get("timings", {})
        emit({
            "mode": "prefill", "run": i + 1, "words": words, "salt": salt,
            "wall_s": round(wall, 3),
            "prompt_n": t.get("prompt_n"),
            "prompt_ms": t.get("prompt_ms"),
            "prompt_tps": t.get("prompt_per_second"),
            "cache_n": t.get("cache_n"),
            "predicted_n": t.get("predicted_n"),
        })


def decode(runs):
    prompt = ("Write a long, detailed essay about the history of computing. "
              "Use many paragraphs and specific examples.")
    for i in range(runs):
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
            "temperature": 0,
        }
        body, wall = post(payload)
        t = body.get("timings", {})
        emit({
            "mode": "decode", "run": i + 1,
            "wall_s": round(wall, 3),
            "prompt_n": t.get("prompt_n"),
            "predicted_n": t.get("predicted_n"),
            "predicted_ms": t.get("predicted_ms"),
            "predicted_tps": t.get("predicted_per_second"),
            "finish": (body.get("choices") or [{}])[0].get("finish_reason"),
        })


def fixed():
    for i in range(1, 6):
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Reply with exactly AB_PONG_%d" % i}],
            "max_tokens": 64,
            "temperature": 0,
        }
        body, wall = post(payload)
        choice = (body.get("choices") or [{}])[0]
        t = body.get("timings", {})
        emit({
            "mode": "fixed", "run": i,
            "content": (choice.get("message") or {}).get("content"),
            "finish": choice.get("finish_reason"),
            "predicted_n": t.get("predicted_n"),
            "wall_s": round(wall, 3),
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["prefill", "decode", "fixed", "all"])
    ap.add_argument("--words", type=int, default=2000)
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    if a.mode in ("prefill", "all"):
        prefill(a.words, a.runs if a.mode == "prefill" else 7)
    if a.mode in ("decode", "all"):
        decode(a.runs)
    if a.mode in ("fixed", "all"):
        fixed()


if __name__ == "__main__":
    main()
