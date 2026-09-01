#!/usr/bin/env python3
"""B5p: M2.7 双机 RPC 推理基准 (40G 新线 vs 基线 pp512=139 / tg128=20.6)
走 llama-server /completion 的 timings 字段, 3 轮取优, prompt 唯一化防 cache 污染"""
import json, time, urllib.request

URL = "http://127.0.0.1:8080/completion"

def comp(prompt, n_predict):
    body = json.dumps({"prompt": prompt, "n_predict": n_predict, "stream": False}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    t = r.get("timings", {})
    return t

# --- tg128: 短 prompt 长生成 (3 轮, 后续轮 prompt 走 cache 纯 decode) ---
best_tg = 0
for i in range(3):
    t = comp(f"测试{i}。", 128)
    tg = t["predicted_n"] / t["predicted_ms"] * 1000
    best_tg = max(best_tg, tg)
    print(f"tg128  run{i}: {t['predicted_n']} tok / {t['predicted_ms']:.0f} ms = {tg:.1f} tok/s")

# --- pp512: 唯一长 prompt 短生成 (3 轮, 每轮换前缀防 cache) ---
best_pp = 0
for i in range(3):
    prompt = f"第{i}组基准。请逐字记录以下序列: " + "数据科学与交叉学科方法论研究。" * 120
    t = comp(prompt, 1)
    pp = t["prompt_n"] / t["prompt_ms"] * 1000
    best_pp = max(best_pp, pp)
    print(f"pp512  run{i}: {t['prompt_n']} tok / {t['prompt_ms']:.0f} ms = {pp:.1f} tok/s")

print(f"\n=== 最优: tg128 = {best_tg:.1f} tok/s (基线 20.6) | pp512 = {best_pp:.1f} tok/s (基线 139) ===")
