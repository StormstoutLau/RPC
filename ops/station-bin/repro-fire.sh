#!/bin/bash
# repro-fire.sh — 并发两个长上下文请求到 unsloth 前端, 观察 slot 卡死 (#20906 复现)
# 用法: bash repro-fire.sh <key> <port>
set -u
KEY="$1"; P="${2:-8080}"
URL="http://127.0.0.1:${P}/v1/completions"
MODEL="gpt-oss-120b-MXFP4"
# 长 prompt: 约 3000 词 随机文本 (制造较长 prefill; batching 让两 slot 同批)
PROMPT_A=$(python3 - <<'PY'
import random
random.seed(1)
words=["alpha","bravo","charlie","delta","echo","foxtrot","golf","hotel","india","juliett","kilo","lima","mike","november","oscar","papa","quebec","romeo","sierra","tango","uniform","victor","whiskey","xray","yankee","zulu"]
print(" ".join(random.choice(words) for _ in range(1500)))
PY
)
PROMPT_B=$(python3 - <<'PY'
import random
random.seed(2)
words=["quant","risk","factor","model","copula","volatility","skew","tail","garch","regime","moment","basis","return","shock","credit","asset","hedge","duration","convexity","spread"]
print(" ".join(random.choice(words) for _ in range(1500)))
PY
)
echo "promptA_len=${#PROMPT_A} promptB_len=${#PROMPT_B}"
# 并发两请求, stream=false, 限定 max_tokens 小值让 decode 短 (聚焦 prefill/batch 阶段卡死)
echo "== fire A (bg) =="
( curl -s --max-time 300 -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"prompt\":\"$PROMPT_A\",\"max_tokens\":16,\"stream\":false,\"temperature\":0}" \
    "$URL" > /tmp/repro-A.out 2>/tmp/repro-A.err; echo "A_RC=$?" > /tmp/repro-A.rc ) &
echo "== fire B (bg) =="
( curl -s --max-time 300 -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"prompt\":\"$PROMPT_B\",\"max_tokens\":16,\"stream\":false,\"temperature\":0}" \
    "$URL" > /tmp/repro-B.out 2>/tmp/repro-B.err; echo "B_RC=$?" > /tmp/repro-B.rc ) &
echo "fired, waiting..."
# 观察窗口: 60s 内各自应完成(prefill 4000 tok 数十秒级); 若某端返回极慢或挂死候选卡死
for i in $(seq 1 20); do
  sleep 15
  A=$(cat /tmp/repro-A.rc 2>/dev/null || echo running)
  B=$(cat /tmp/repro-B.rc 2>/dev/null || echo running)
  echo "[$((i*15))s] A=$A B=$B"
  [ "$A" != "running" ] && [ "$B" != "running" ] && break
done
echo "== A.out =="; cat /tmp/repro-A.out 2>/dev/null | head -c 200; echo
echo "== B.out =="; cat /tmp/repro-B.out 2>/dev/null | head -c 200; echo
echo "== 卡死判定: 若 300s 超时且 rc 空 == 挂起(reproduce) =="
echo "A_rc=$(cat /tmp/repro-A.rc 2>/dev/null||echo none) B_rc=$(cat /tmp/repro-B.rc 2>/dev/null||echo none)"
echo OK