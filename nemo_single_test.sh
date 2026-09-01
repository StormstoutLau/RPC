#!/bin/bash
# nemotron 单机部署 + 同口径基准 (B 站, 无 RPC)
set -u
exec 2>&1

GGUF=/data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF/NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M-00001-of-00003.gguf

echo "=== 1. 停双机 (llama-server + A 站 rpc-server) ==="
sudo systemctl stop llama-server@nvidia-nemotron-3-super-120b-a12b 2>/dev/null
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 'sudo systemctl stop rpc-server@nvidia-nemotron-3-super-120b-a12b 2>/dev/null; echo A-rpc-stopped'
sleep 5

echo "=== 2. 单机起 llama-server (B 站, 无 --rpc) ==="
nohup /opt/llama.cpp/llama-server -m $GGUF -ngl 999 -c 131072 -t 16 --n-cpu-moe 8 \
  -fa on --host 127.0.0.1 --port 8080 > /tmp/nemo_single.out 2>&1 &
SRV=$!
echo "server pid=$SRV"

echo "=== 3. 等 READY (最长 10min) ==="
for i in $(seq 1 120); do
  if curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1; then
    echo "READY after ${i}x5s"; break
  fi
  sleep 5
done
curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1 || { echo "NOT READY"; tail -20 /tmp/nemo_single.out; exit 1; }

echo "=== 4. GTT 占用 ==="
grep -E "GTT|MemAvailable" /proc/meminfo | head -3
amdgpu_top -m 300 2>/dev/null | head -5 || cat /sys/class/drm/card*/device/mem_info_vram_used 2>/dev/null | head -1

echo "=== 5. 同口径 decode 基准 (512 tok) ==="
python3 - <<'EOF'
import json, time, urllib.request
API = "http://127.0.0.1:8080/v1/chat/completions"
body = {"model": "n", "messages": [{"role": "user", "content": "从 1 数到 400, 每行一个数字。"}],
        "temperature": 0, "max_tokens": 512, "stream": False}
req = urllib.request.Request(API, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=600) as r:
    d = json.loads(r.read().decode())
el = time.time() - t0
u = d.get("usage", {})
print(f"decode512: {el:.1f}s, completion={u.get('completion_tokens')} -> {u.get('completion_tokens',0)/el:.1f} t/s (finish={d['choices'][0].get('finish_reason')})")

body2 = {"model": "n", "messages": [{"role": "user", "content": "证明: 对椭圆 copula, Kendall tau = (2/pi)arcsin(rho)。给完整推导。"}],
         "temperature": 0, "max_tokens": 2048, "stream": False}
req = urllib.request.Request(API, data=json.dumps(body2).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=600) as r:
    d = json.loads(r.read().decode())
el = time.time() - t0
u = d.get("usage", {})
print(f"long2048: {el:.1f}s, completion={u.get('completion_tokens')} -> {u.get('completion_tokens',0)/el:.1f} t/s (finish={d['choices'][0].get('finish_reason')})")
EOF

echo "=== 6. 同口径 24k needle (与 RPC 版完全同题) ==="
python3 /tmp/nemotron_ctx16k.py

echo "=== 7. 收尾: 停单机, 交还集群标准态 ==="
kill $SRV 2>/dev/null; sleep 3
pkill -f "llama-server -m /data/models/gguf/lmstudio-community/NVIDIA-Nemotron" 2>/dev/null
sleep 2
pgrep -af "llama-server" | grep -v grep || echo "(单机已停, 集群回零自加载态)"
echo DONE_SINGLE
