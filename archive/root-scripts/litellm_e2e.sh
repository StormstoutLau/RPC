#!/bin/bash
# E2E 验证: load-mem-gate → infer-load nemotron → 经 :4000 网关真实调用 → unload 回干净态
set -u
exec 2>&1

echo "=== 1. 内存门 (80G) ==="
load-mem-gate 80 || { echo "内存门拒绝, 终止"; exit 1; }

echo "=== 2. infer-load nemotron (双机 RPC, ~3min) ==="
infer-load nvidia-nemotron-3-super 2>&1 | tail -3

echo "=== 3. E2E: 经 LiteLLM :4000 调用 nemotron 路由 ==="
KEY=$(grep master_key /home/scott-lau/litellm/config.yaml | awk '{print $2}')
python3 - <<EOF
import json, time, urllib.request
body = {
    "model": "nemotron",
    "messages": [{"role": "user", "content": "一句话回答: Heston 模型中 rho 的符号如何影响波动率微笑?"}],
    "temperature": 0, "max_tokens": 1024,
}
req = urllib.request.Request(
    "http://127.0.0.1:4000/v1/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json", "Authorization": "Bearer $KEY"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=300) as r:
    d = json.loads(r.read().decode())
el = time.time() - t0
m = d["choices"][0]["message"]
print(f"耗时 {el:.1f}s | finish={d['choices'][0].get('finish_reason')}")
print("reasoning_len:", len(m.get("reasoning_content") or ""))
print("content:", (m.get("content") or "")[:300])
u = d.get("usage", {})
print("tokens:", u.get("prompt_tokens"), "->", u.get("completion_tokens"))
print("E2E_OK" if d["choices"][0].get("finish_reason") == "stop" and len(m.get("content") or "") > 20 else "E2E_FAIL")
EOF

echo "=== 4. unload 回干净态 ==="
infer-unload 2>&1 | tail -2
echo DONE_E2E
