#!/usr/bin/env python3
"""B5j bench: DeepSeek-V4-Flash RPC 生成速度基准 (tg decode / prefill TTFT)"""
import json, time, urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"

def gen(prompt_len, n_tokens, label):
    prompt = "数" * prompt_len if prompt_len < 50 else "请总结以下文字的规律: " + "数据科学是一门交叉学科。" * (prompt_len // 12)
    body = {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": n_tokens,
        "stream": False,
    }
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    best = None
    for i in range(2):  # 2 轮取优
        t0 = time.time()
        r = json.loads(urllib.request.urlopen(req, timeout=600).read())
        dt = time.time() - t0
        ct = r.get("usage", {}).get("completion_tokens", n_tokens)
        pt = r.get("usage", {}).get("prompt_tokens", prompt_len)
        tg = ct / dt if dt > 0 else 0
        if best is None or tg > best[0]:
            best = (tg, dt, pt, ct)
    tg, dt, pt, ct = best
    # ttft 估算: 短生成时总时≈decode; 长prompt时用 stream 才准, 此处给总吞吐
    print(f"{label}: total {dt:.1f}s, prompt~{pt} tok, out {ct} tok, 吞吐 {tg:.2f} tok/s")
    return tg, dt

# tg decode 主导 (短 prompt 长生成)
gen(8, 128, "tg128 ")
gen(8, 256, "tg256 ")
# prefill 主导 (长 prompt 短生成)
gen(2048, 16, "pp2048")
