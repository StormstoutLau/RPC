#!/usr/bin/env python3
# nemotron_decode_bench.py — (a) smoke usage 提取 (b) 纯 decode 速度 (短 prompt + 512 tok)
import json, time, urllib.request

print("=== smoke usage (nemotron) ===")
with open("/tmp/b6_smoke_nemotron.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        u = r.get("usage", {})
        ct, pt, el = u.get("completion_tokens"), u.get("prompt_tokens"), r.get("elapsed_s")
        if ct and el:
            print(f"{r['id']}: compl={ct} prompt={pt} elapsed={el}s -> 纯decode≈{ct/el:.1f} t/s (含prefill高估)")

print()
print("=== 纯 decode 基准 (prompt 20 tok, 生成 512) ===")
API = "http://127.0.0.1:8080/v1/chat/completions"
body = {"model": "nvidia-nemotron-3-super-120b-a12b",
        "messages": [{"role": "user", "content": "从 1 数到 400, 每行一个数字。"}],
        "temperature": 0, "max_tokens": 512, "stream": False}
req = urllib.request.Request(API, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=600) as r:
    d = json.loads(r.read().decode())
el = time.time() - t0
u = d.get("usage", {})
ct = u.get("completion_tokens", 0)
print(f"耗时 {el:.1f}s, completion={ct} -> decode ≈ {ct/el:.1f} t/s (finish={d['choices'][0].get('finish_reason')})")

print()
print("=== 长生成基准 (think 2048, 冒烟 A3 同型) ===")
body2 = {"model": "nvidia-nemotron-3-super-120b-a12b",
         "messages": [{"role": "user", "content": "证明: 对椭圆 copula, Kendall tau = (2/pi)arcsin(rho)。给完整推导。"}],
         "temperature": 0, "max_tokens": 2048, "stream": False}
req = urllib.request.Request(API, data=json.dumps(body2).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=600) as r:
    d = json.loads(r.read().decode())
el = time.time() - t0
u = d.get("usage", {})
print(f"耗时 {el:.1f}s, prompt={u.get('prompt_tokens')} completion={u.get('completion_tokens')} "
      f"-> ≈ {u.get('completion_tokens',0)/el:.1f} t/s (finish={d['choices'][0].get('finish_reason')})")
