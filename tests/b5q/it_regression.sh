#!/bin/bash
# B5q §5 回归验收 (零破坏不变式) — 同步/校验全部完成后执行
# m27 生产链路 / LiteLLM 网关 / gpt-oss 单机 / GTT 释放
set -uo pipefail

echo '--- R1 m27 生产链路 (infer-load → 生成 → unload) ---'
INFER=/usr/local/bin/infer-load
timeout 300 $INFER m27 2>&1 | tail -3
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1 && { echo "health OK (${i}x5s)"; break; }
  sleep 5
done
echo '--- m27 实际命令行 RPC 展开 (§2.2 R1 佐证) ---'
ps -ef | grep 'llama[-]server' | grep -o '\--rpc [^ ]*' | head -2
echo '--- 生成测试 ---'
curl -sf http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m2","messages":[{"role":"user","content":"回复两个字: 正常"}],"max_tokens":16}' \
  | head -c 400; echo

echo '--- R2 LiteLLM 网关 (4000 → 8080) ---'
KEY=$(grep -o 'master_key: *.*' ~/litellm/config.yaml 2>/dev/null | awk '{print $2}' | tr -d '"')
if [ -n "$KEY" ]; then
  curl -sf http://127.0.0.1:4000/v1/chat/completions -H "Authorization: Bearer $KEY" \
    -H 'Content-Type: application/json' \
    -d '{"model":"minimax-m2","messages":[{"role":"user","content":"回复两个字: 网关"}],"max_tokens":16}' \
    | head -c 400; echo
else
  echo '(key 文件未找到, 跳过 R2 — 手动验证)'
fi

echo '--- R1 收尾: unload ---'
/usr/local/bin/infer-unload m27 2>&1 | tail -2
sleep 5

echo '--- R3 gpt-oss 单机 (空值 conf, 命令行不含 --rpc) ---'
timeout 300 $INFER gpt-oss 2>&1 | tail -2
sleep 3
PSLINE=$(ps -ef | grep 'llama[-]server' | grep -i 'gpt' | head -1)
echo "$PSLINE" | head -c 300; echo
if echo "$PSLINE" | grep -q '\--rpc'; then echo 'FAIL: gpt-oss 带 --rpc (静默翻转!)'; else echo 'PASS: gpt-oss 无 --rpc (单机语义保持)'; fi
/usr/local/bin/infer-unload gpt-oss 2>&1 | tail -1

echo '--- R4 两站 GTT 释放 (<2G) ---'
echo "B: $(grep '^GttMemUsed' /proc/meminfo)"
ssh -o BatchMode=yes 10.10.10.1 'grep "^GttMemUsed" /proc/meminfo' 2>&1 | sed 's/^/A: /'
echo '--- R5 rpc-server 恢复验收前状态 (inactive) ---'
ssh -o BatchMode=yes 10.10.10.1 'sudo systemctl stop rpc-server@m27-q4ks 2>/dev/null; systemctl is-active rpc-server@m27-q4ks'
echo '=== 回归脚本完 ==='
