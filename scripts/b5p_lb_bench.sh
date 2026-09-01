#!/bin/bash
# B5p 补充: llama-bench 原口径复测 (与基线 139.19 完全同参数)
# 基线: llama-bench -m <gguf> --rpc 10.10.10.1:50052 -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -p 512 -n 128 -r 2
set -e
source /etc/llama-instances/m27-q4ks.env 2>/dev/null || true
MODEL="${MODEL_PATH:-/data/models/MiniMax-M2.7-Q4_K_S.gguf}"
[ -f "$MODEL" ] || MODEL=$(find -L /data/models -name 'MiniMax-M2.7*Q4_K_S*.gguf' 2>/dev/null | head -1)
echo "MODEL=$MODEL"

BENCH=/opt/llama.cpp/llama-bench
[ -x "$BENCH" ] || BENCH=$(find /opt/llama.cpp -maxdepth 3 -name llama-bench -type f 2>/dev/null | head -1)
echo "BENCH=$BENCH"

# 1. 起 A 站 rpc-server (llama-bench 自任 client)
ssh scott-lau@scott-lau-NEX.local "sudo systemctl start rpc-server@m27-q4ks" 2>/dev/null || \
  ssh 10.10.10.1 "sudo systemctl start rpc-server@m27-q4ks"
sleep 3
for i in $(seq 1 10); do
  if ssh 10.10.10.1 "ss -tln | grep -q 50052" 2>/dev/null; then echo "rpc-server up"; break; fi
  sleep 2
done

# 2. llama-bench (基线同参数)
echo "=== llama-bench pp512/tg128 (基线口径, 40G 线) ==="
"$BENCH" -m "$MODEL" --rpc 10.10.10.1:50052 -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -p 512 -n 128 -r 2 2>&1 | tail -5
