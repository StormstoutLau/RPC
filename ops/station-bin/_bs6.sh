#!/bin/bash
# bs6-test.sh — BS-6: 统一内存带宽竞争实测 (unsuloth 后端并发短 prefill 吞吐对比)
# 用 B 站 unsloth:8080 (gpt-oss, KV q8_0, NVK). 串行 vs 并发请求 decode/prefill tok/s
set -u
P=8080
KEY=$(grep -oE 'sk-unsloth-[a-f0-9]+' "$HOME/.unsloth/run-gpt-oss-120b.log" | tail -1)
[ -n "$KEY" ] || KEY=$(grep -oE 'sk-unsloth-[a-f0-9]+' /tmp/pre-repro-key.txt | tail -1)
URL="http://127.0.0.1:${P}/v1/completions"
MODEL="gpt-oss-120b-MXFP4"
echo "keylen=${#KEY}"

# 短 prefill 文本 (300 token 级)
PROMPT=" market volatility skew tail regime basis frontier covariance $(python3 -c 'print(" ".join(["risk factor copula momentum"]*80))') "

fire() { # name max_tokens
  RES=$(curl -s --max-time 300 -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"prompt\":\"$PROMPT\",\"max_tokens\":${2:-32},\"temperature\":0}" \
    "$URL")
  PT=$(echo "$RES" | grep -oE '"prompt_tok_s":[0-9.]+' | head -1 | cut -d: -f2)
  GT=$(echo "$RES" | grep -oE '"gen_tok_s":[0-9.]+' | head -1 | cut -d: -f2)
  PN=$(echo "$RES" | grep -oE '"prompt_tokens":[0-9]+' | head -1 | cut -d: -f2)
  echo "$1 prep=(${PN:-0}) pp_s=(${PT:-?}) gen_s=(${GT:-?})"
}

echo "== 串行基线: 4 次短请求 依次 =="
T0=$(date +%s%N)
for i in 1 2 3 4; do fire C$i 32; done
E0=$(date +%s%N); echo "串行4次总_ms=$(( (E0-T0)/1000000 ))"

echo "== 并发: 4 次短请求 同时发 =="
T1=$(date +%s%N)
for i in 1 2 3 4; do (fire D$i 32) & done
wait
E1=$(date +%s%N); echo "并发4次总_ms=$(( (E1-T1)/1000000 ))"
echo "== 判据: 并发总耗时 vs 串行×1 → 若并发总耗时≈串行总耗时(带宽无增益) 或 >串行(竞争降速)=BS-6; 若≈单次(满并行)=无竞争 =="
echo OK