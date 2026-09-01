#!/usr/bin/env python3
# gptoss tg 基准: 纯 decode + 长生成 (同口径 nemotron/m27 可比)
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"

def bench(prompt, mt, label):
    body = {"model": "gpt-oss-120b", "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": mt, "stream": False}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode())
    el = time.time() - t0
    u = d.get("usage", {})
    ct = u.get("completion_tokens", 0)
    print(f"{label}: {el:.1f}s, completion={ct} -> {ct/el:.1f} t/s (finish={d['choices'][0].get('finish_reason')})")

bench("从 1 数到 400, 每行一个数字。", 512, "decode512")
bench("证明: 对椭圆 copula, Kendall tau = (2/pi)arcsin(rho)。给完整推导。", 2048, "long2048")
# 代码负载 (ngram 投机的目标场景: 高重复模式)
bench("写一个 Python 函数处理 CSV: 读取, 按列分组, 每组求均值方差, 输出 markdown 表。完整可运行代码。", 2048, "code2048")
