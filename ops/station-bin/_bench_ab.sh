#!/bin/bash
# A/B 基准: Jackrong(:18080, Q8_0) vs DavidAU(:18081, Q4_K_M non-MTP) -- 同题, temp=0
set -u
declare -a PROMPTS=(
"一个密码由 4 位数字组成，每位 0-9。已知各位数字之和为偶数，且密码不含数字 0。求这样的密码有多少个？请给出推理过程。"
"甲袋有 3 红 2 白，乙袋有 2 红 3 白。先从甲袋随机取 1 球放入乙袋，再从乙袋取 1 球。求最后从乙袋取到白球的概率。请给出推理过程。"
"一个水池有进水管和出水管，单开进水管 6 小时注满，单开出水管 9 小时放空。同时打开两管，多久注满？请给出推理过程。"
)
bench() {
  local port="$1" tag="$2"
  echo "########## ${tag} :${port} ##########"
  for i in 0 1 2; do
    local p="${PROMPTS[$i]}"
    local out tmp
    out=$(curl -s --max-time 300 http://127.0.0.1:${port}/v1/chat/completions \
      -H 'Content-Type: application/json' \
      -o /tmp/bench_resp.json -w '%{time_total}' \
      -d "{\"model\":\"x\",\"messages\":[{\"role\":\"user\",\"content\":$(python3 -c "import json,sys;print(json.dumps(sys.argv[1]))" "$p")}],\"max_tokens\":1024,\"temperature\":0}")
    tmp=$?
    [ $tmp -ne 0 ] || [ ! -s /tmp/bench_resp.json ] && { echo "Q$i FAIL rc=$tmp"; continue; }
    python3 - "$out" "$tag" "$i" <<'PY'
import sys, json
wall=float(sys.argv[1]); tag=sys.argv[2]; i=sys.argv[3]
try:
    d=json.load(open('/tmp/bench_resp.json'))
    c=d['choices'][0]['message']['content']
    u=d['usage']
    comp=u['completion_tokens']; prompt_t=u['prompt_tokens']
    # 拆思考与作答: Qwen3.8 推理内容通常是 思考段 + 作答段
    total_tokens_in_content = len(c)
    # 粗略: 用 completion_tokens 作为生成 token 数
    tps = comp/wall
    n=len(c)
    head=c[:90].replace('\n','\\n')
    print(f"Q{i} [{tag}] wall={wall:.1f}s prompt_t={prompt_t} completion_tokens={comp} ≈tps={tps:.1f} ans_len={n}")
    print(f"   head: {head}")
except Exception as e:
    print("Q%d parse err %s"%(i,e))
PY
  done
}
bench 18080 "JACKRONG-Q8_0"
bench 18081 "DAVIDAU-Q4K"
echo "ALL-DONE"