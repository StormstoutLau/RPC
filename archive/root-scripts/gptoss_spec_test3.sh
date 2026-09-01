#!/bin/bash
# gpt-oss 投机试验 v3: 先停 8080 主实例释放 GTT
set -u
exec 2>&1
GGUF120=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-Q4_K_M.gguf
DRAFT20=/home/scott-lau/.lmstudio/models/lmstudio-community/gpt-oss-20b-GGUF/gpt-oss-20b-MXFP4.gguf

echo "=== 0. 停 8080 主实例 ==="
sudo systemctl stop llama-server@gpt-oss-120b 2>/dev/null
pkill -f "llama-server.*gpt-oss-120b" 2>/dev/null
sleep 8
pgrep -af llama-server | grep -v grep || echo "(8080 已清)"

run_bench() {
  python3 - <<'EOF'
import json, time, urllib.request
API = "http://127.0.0.1:8099/v1/chat/completions"
def bench(prompt, mt, label):
    body = {"model": "x", "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": mt, "stream": False}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode())
    el = time.time() - t0
    u = d.get("usage", {})
    ct = u.get("completion_tokens", 0)
    print(f"{label}: {el:.1f}s, completion={ct} -> {ct/el:.1f} t/s")
bench("从 1 数到 400, 每行一个数字。", 512, "decode512")
bench("证明: 对椭圆 copula, Kendall tau = (2/pi)arcsin(rho)。给完整推导。", 2048, "long2048")
bench("写一个 Python 函数处理 CSV: 读取, 按列分组, 每组求均值方差, 输出 markdown 表。完整可运行代码。", 2048, "code2048")
EOF
}

echo "########## (a) ngram-simple ##########"
nohup /opt/llama.cpp/llama-server -m $GGUF120 -ngl 999 -c 32768 -t 16 --n-cpu-moe 8 \
  -fa on --spec-type ngram-simple --host 127.0.0.1 --port 8099 > /tmp/goss_ngram.out 2>&1 &
P=$!
for i in $(seq 1 60); do curl -sf http://127.0.0.1:8099/health >/dev/null 2>&1 && break; sleep 5; done
if curl -sf http://127.0.0.1:8099/health >/dev/null 2>&1; then
  echo READY
  curl -s http://127.0.0.1:8099/slots | grep -o '"speculative":[a-z]*' | head -1
  run_bench
else
  echo FAIL; tail -5 /tmp/goss_ngram.out
fi
kill $P 2>/dev/null; sleep 8

echo "########## (b) gpt-oss-20b draft-simple ##########"
nohup /opt/llama.cpp/llama-server -m $GGUF120 -md "$DRAFT20" -ngl 999 -ngld 999 \
  -c 32768 -t 16 --n-cpu-moe 8 -fa on --spec-type draft-simple \
  --host 127.0.0.1 --port 8099 > /tmp/goss_draft20.out 2>&1 &
P=$!
for i in $(seq 1 90); do curl -sf http://127.0.0.1:8099/health >/dev/null 2>&1 && break; sleep 5; done
if curl -sf http://127.0.0.1:8099/health >/dev/null 2>&1; then
  echo READY
  curl -s http://127.0.0.1:8099/slots | grep -o '"speculative":[a-z]*' | head -1
  run_bench
else
  echo FAIL; tail -8 /tmp/goss_draft20.out
fi
kill $P 2>/dev/null; sleep 3
pgrep -af "port 8099" | grep -v grep || echo "(试验 server 已清)"
echo DONE_SPEC_V3
