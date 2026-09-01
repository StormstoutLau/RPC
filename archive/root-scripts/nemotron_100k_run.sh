#!/bin/bash
# 100k 测试编排: conf 提 CTX=131072 → restart → 等 READY → 跑 needle → 落盘
set -u
CONF=/etc/llama-instances/nvidia-nemotron-3-super-120b-a12b.env
exec 2>&1

echo "=== 1. conf CTX 32768 → 131072 ==="
sudo cp -a $CONF $CONF.bak.ctx32k
sudo sed -i 's/^CTX=32768/CTX=131072/' $CONF
grep -E "^CTX" $CONF

echo "=== 2. restart llama-server (B 站) ==="
sudo systemctl restart llama-server@nvidia-nemotron-3-super-120b-a12b

echo "=== 3. 等 READY (最长 8min) ==="
for i in $(seq 1 96); do
  if curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1; then
    echo "READY after ${i}x5s"; break
  fi
  sleep 5
done
curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1 || { echo "NOT READY — abort"; exit 1; }

echo "=== 4. 100k needle ==="
python3 /tmp/nemotron_ctx100k.py
touch /tmp/ctx100k_done
