#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""halogen image-version A/B probe (2026-10-22).

Runs ON the station against http://127.0.0.1:8080.
Two modes:
  prefill   --words 8000|32000 --runs N   -> cold prefill timing (max_tokens=1)
  fairness  --words 32000 --runs N        -> (a) short request arrives while a long
                                             prompt is read in; (b) an in-flight
                                             streaming reply meets a long prompt.
Outputs one JSON object per line (prefix RESULT) for host-side collection.
"""
import argparse
import json
import random
import secrets
import threading
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
    return "Run %s. " % salt + " ".join(rng.choice(VOCAB) for _ in range(words))


def post(payload, stream=False, timeout=600):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        URL, data=data, headers={"Content-Type": "application/json"}
    )
    return urllib.request.urlopen(req, timeout=timeout)


def chat_prefill(words, salt, max_tokens=1):
    text = make_text(words, salt) + "\n\nReply with OK."
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    t0 = time.time()
    with post(payload) as r:
        body = json.loads(r.read())
    wall = time.time() - t0
    t = body.get("timings", {})
    return {
        "wall_s": round(wall, 3),
        "prompt_n": t.get("prompt_n"),
        "prompt_ms": t.get("prompt_ms"),
        "prompt_tps": t.get("prompt_per_second"),
        "cache_n": t.get("cache_n"),
        "predicted_n": t.get("predicted_n"),
    }


def stream_short(trigger=None, max_tokens=1024):
    prompt = (
        "Write a very long, detailed essay about the history of computing. "
        "Use many paragraphs and specific examples."
    )
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    t0 = time.time()
    first = None
    last = None
    gaps = []
    triggered_at = None
    trigger_done = False
    chars = 0
    chunks = 0
    with post(payload, stream=True) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            delta = (obj.get("choices") or [{}])[0].get("delta") or {}
            txt = delta.get("content") or ""
            if not txt:
                continue
            now = time.time()
            if first is None:
                first = now
            if last is not None:
                gaps.append(now - last)
            last = now
            chars += len(txt)
            chunks += 1
            if trigger is not None and not trigger_done:
                trigger_done = True
                triggered_at = now
                trigger()
    total = time.time() - t0
    after = []
    if triggered_at is not None:
        # gaps that END after the trigger are the ones that matter for splice
        idx = 0
        cursor = t0
        for g in gaps:
            cursor += g
            if cursor >= triggered_at:
                after.append(g)
    return {
        "ttft_s": round(first - t0, 3) if first else None,
        "total_s": round(total, 3),
        "chunks": chunks,
        "chars": chars,
        "max_gap_s": round(max(gaps), 3) if gaps else None,
        "max_gap_after_trigger_s": round(max(after), 3) if after else None,
        "gaps_after_trigger_n": len(after),
    }


def run_prefill(words, runs):
    for i in range(runs):
        salt = secrets.token_hex(8)
        r = chat_prefill(words, salt)
        r.update({"mode": "prefill", "words": words, "run": i + 1, "salt": salt})
        print("RESULT " + json.dumps(r), flush=True)


def run_fairness(words, runs):
    for i in range(runs):
        # A: a short request arrives while a long prompt is being read in
        out = {}
        salt_a = secrets.token_hex(8)
        holder = {}

        def long_req():
            holder["long"] = chat_prefill(words, salt_a)

        th = threading.Thread(target=long_req)
        th.start()
        time.sleep(0.5)
        short_a = stream_short()
        th.join()
        out["nest"] = {
            "short": short_a,
            "long": holder.get("long"),
            "salt": salt_a,
            "run": i + 1,
        }

        # B: an in-flight streaming reply meets a long prompt
        salt_b = secrets.token_hex(8)
        holder2 = {}

        def long_req2():
            holder2["long"] = chat_prefill(words, salt_b)

        state = {"th": None}

        def trigger():
            state["th"] = threading.Thread(target=long_req2)
            state["th"].start()

        short_b = stream_short(trigger=trigger)
        if state["th"] is not None:
            state["th"].join()
        out["splice"] = {
            "short": short_b,
            "long": holder2.get("long"),
            "salt": salt_b,
            "run": i + 1,
        }
        out["mode"] = "fairness"
        out["words"] = words
        print("RESULT " + json.dumps(out), flush=True)


def main():
    global URL, MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--model", default="halogen-qwen3.8-flash-next")
    ap.add_argument("mode", choices=["prefill", "fairness"])
    ap.add_argument("--words", type=int, required=True)
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    URL = a.url.rstrip("/") + "/v1/chat/completions"
    MODEL = a.model
    if a.mode == "prefill":
        run_prefill(a.words, a.runs)
    else:
        run_fairness(a.words, a.runs)


if __name__ == "__main__":
    main()
