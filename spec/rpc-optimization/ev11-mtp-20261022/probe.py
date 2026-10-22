#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EV-11 spike: GLM-5.3-Flash decode probe (B head :8080)."""
import json
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
MODEL = "glm-5.3-flash"
PROMPT = (
    "Write a detailed technical explanation of how a modern CPU cache hierarchy works. "
    "Cover L1/L2/L3, cache lines, associativity, write-back vs write-through, and inclusive "
    "vs exclusive caches. Use several paragraphs and concrete examples."
)


def once(i):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 128,
        "temperature": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        body = json.loads(r.read())
    wall = time.time() - t0
    t = body.get("timings", {})
    print("RESULT " + json.dumps({
        "run": i,
        "wall_s": round(wall, 3),
        "prompt_n": t.get("prompt_n"),
        "prompt_ms": t.get("prompt_ms"),
        "prompt_tps": t.get("prompt_per_second"),
        "predicted_n": t.get("predicted_n"),
        "predicted_ms": t.get("predicted_ms"),
        "predicted_tps": t.get("predicted_per_second"),
        "draft_n": t.get("draft_n"),
        "draft_n_accepted": t.get("draft_n_accepted"),
        "cache_n": t.get("cache_n"),
        "finish": (body.get("choices") or [{}])[0].get("finish_reason"),
    }), flush=True)


for i in range(1, 5):
    once(i)
