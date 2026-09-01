#!/usr/bin/env python3
"""B5j bench 补测: prefill 唯一 prompt (避免 prompt cache 污染)"""
import json, time, urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"

for i in range(3):
    # 每轮唯一 prompt (~2000 token 量级)
    prompt = f"第{i}组测试。请逐字复述以下编号序列，不要遗漏: " + " ".join(f"编号{i}-{j}项" for j in range(900))
    body = {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4,
    }
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    dt = time.time() - t0
    pt = r.get("usage", {}).get("prompt_tokens", 0)
    ct = r.get("usage", {}).get("completion_tokens", 0)
    decode_t = ct / 6.6  # 按 tg 6.6 估
    pp = pt / max(dt - decode_t, 0.01)
    print(f"run{i}: {pt} ptok, {ct} otok, total {dt:.2f}s → prefill ≈ {pp:.0f} tok/s")
