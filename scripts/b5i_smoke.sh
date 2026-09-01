#!/bin/bash
# b5i_smoke.sh — B5i 冒烟验证: 服务状态 + API 生成 + A 站联动
echo "===== B5i 冒烟 @ $(date '+%F %T') ====="
echo "--- [1] 两站服务状态 ---"
systemctl is-active llama-server@m27-q4ks
ssh -o BatchMode=yes scott-lau@scott-lau-NEX.local "systemctl is-active rpc-server@m27-q4ks; cat /sys/class/drm/card*/device/mem_info_gtt_used | head -1"
echo "B 站 GTT: $(cat /sys/class/drm/card*/device/mem_info_gtt_used | head -1)"

echo "--- [2] conf 内容 ---"
cat /etc/llama-instances/m27-q4ks.env

echo "--- [3] API 生成测试 (8080 直连) ---"
T0=$(date +%s.%N)
R=$(curl -s --max-time 120 http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m2","messages":[{"role":"user","content":"用一句话回答: 1+1=?"}],"max_tokens":20}')
T1=$(date +%s.%N)
echo "耗时: $(echo "$T1 $T0" | awk '{printf "%.1fs", $1-$2}')"
echo "$R" | python3 -c "
import json,sys
try:
  d=json.load(sys.stdin)
  print('回复:', d['choices'][0]['message']['content'][:80])
  print('usage:', d.get('usage',{}))
except Exception as e:
  print('PARSE FAIL:', e); print(sys.stdin.read()[:200])
"

echo "--- [4] LiteLLM 网关链路 (:4000) ---"
curl -s --max-time 120 http://127.0.0.1:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m2","messages":[{"role":"user","content":"回答OK即可"}],"max_tokens":10}' \
  | python3 -c "
import json,sys
try:
  d=json.load(sys.stdin)
  print('网关回复:', d['choices'][0]['message']['content'][:50])
except Exception as e:
  print('网关 FAIL:', e)
"
