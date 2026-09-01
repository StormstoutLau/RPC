#!/usr/bin/env python3
"""B5p 补测: pp512 口径对齐 (基线 llama-bench pp512=139)"""
import json, urllib.request

URL = "http://127.0.0.1:8080/completion"

best = 0
for i in range(4):
    prompt = f"第{i}组。请记录: " + "数据科学与交叉学科方法论。" * 60  # ~512 tok
    body = json.dumps({"prompt": prompt, "n_predict": 1, "stream": False}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    t = r["timings"]
    pp = t["prompt_n"] / t["prompt_ms"] * 1000
    best = max(best, pp)
    print(f"pp~512 run{i}: {t['prompt_n']} tok / {t['prompt_ms']:.0f} ms = {pp:.1f} tok/s")
print(f"=== pp512 最优 {best:.1f} tok/s (基线 139) ===")
