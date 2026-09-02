#!/usr/bin/env bash
# ============================================================================
# agent-cli-smoke.sh — 4 个 agent CLI 冒烟测试 (主控站 Git Bash 发起)
# 目的: 验证 B-claude / B-opencode / A-claude / A-opencode 及主控站 ssh 调度链路
# 调用形式 (2026-09-02 实测定版, 勿改):
#   claude:    timeout N claude -p '<prompt>' < /dev/null   (stdin 必须显式关闭)
#   opencode:  echo '<prompt>' | timeout N opencode run -m <provider/model>
#              (1.18.25 位置参数形式挂死, 只能用 stdin 管道形式)
# 前置: 两站模型已加载 (B: nemotron / A: gpt-oss-120b); 未加载时报 SKIP 不算 FAIL
# 用法: bash agent-cli-smoke.sh          # 全量
#       bash agent-cli-smoke.sh B        # 仅 B 站
#       bash agent-cli-smoke.sh A        # 仅 A 站
# 退出码: 0 = 全 PASS/SKIP; 1 = 有 FAIL
# ============================================================================
set -u
SCOPE="${1:-ALL}"
PASS=0; FAIL=0; SKIP=0
P='reply with exactly: OK'

report() { # name status detail
  printf '%-22s %-6s %s\n' "$1" "$2" "$3"
  case "$2" in PASS) PASS=$((PASS+1));; FAIL) FAIL=$((FAIL+1));; SKIP) SKIP=$((SKIP+1));; esac
}

# ---------------------------------------------------------------- B 站
if [ "$SCOPE" = "ALL" ] || [ "$SCOPE" = "B" ]; then
  HOST_B=scott-lau@scott-lau-GTR-Pro.local
  LOADED=$(ssh -o ConnectTimeout=10 "$HOST_B" "pgrep -c -f llama-server" 2>/dev/null || echo 0)
  if [ "${LOADED:-0}" -lt 1 ]; then
    report B-backend SKIP "llama-server 未运行, 先 infer-load nvidia-nemotron-3-super"
  else
    # B-claude: LiteLLM(4000)→nemotron; 冷缓存 33k 预填可能 ~20min, 热缓存 30-120s
    OUT=$(ssh "$HOST_B" 'bash -s' <<'REMOTE' 2>/dev/null
cd /tmp
out=/tmp/smoke-claude-$$.out
s=$(date +%s)
timeout 420 claude -p 'reply with exactly: OK' < /dev/null > "$out" 2>/dev/null
code=$?
e=$(date +%s)
echo "EXIT=$code DUR=$((e-s))s OUT=$(cat "$out" | head -1)"
rm -f "$out"
REMOTE
)
    if echo "$OUT" | grep -q 'EXIT=0 DUR=.* OUT=OK'; then
      report B-claude PASS "$OUT"
    else
      report B-claude FAIL "$OUT"
    fi
    # B-opencode: LiteLLM→nemotron, stdin 管道形式
    OUT=$(ssh "$HOST_B" 'bash -s' <<'REMOTE' 2>/dev/null
cd /tmp
out=$(echo 'reply with exactly: OK' | timeout 180 opencode run -m cluster-litellm/nemotron 2>/dev/null | tail -1)
echo "OUT=$out"
REMOTE
)
    if echo "$OUT" | grep -q 'OUT=OK'; then
      report B-opencode PASS "$OUT"
    else
      report B-opencode FAIL "$OUT (stdin 管道形式; 位置参数形式是已知 bug)"
    fi
  fi
fi

# ---------------------------------------------------------------- A 站
if [ "$SCOPE" = "ALL" ] || [ "$SCOPE" = "A" ]; then
  HOST_A=scott-lau@scott-lau-NEX.local
  LOADED=$(ssh -o ConnectTimeout=10 "$HOST_A" "pgrep -c -f llama-server" 2>/dev/null || echo 0)
  if [ "${LOADED:-0}" -lt 1 ]; then
    report A-backend SKIP "llama-server 未运行, 先 infer-load gpt-oss-120b"
  else
    # A-claude: 直连 A 本机 llama-server(8080) gpt-oss, 快
    OUT=$(ssh "$HOST_A" 'bash -s' <<'REMOTE' 2>/dev/null
cd /tmp
out=/tmp/smoke-claude-$$.out
s=$(date +%s)
timeout 240 claude -p 'reply with exactly: OK' < /dev/null > "$out" 2>/dev/null
code=$?
e=$(date +%s)
echo "EXIT=$code DUR=$((e-s))s OUT=$(cat "$out" | head -1)"
rm -f "$out"
REMOTE
)
    if echo "$OUT" | grep -q 'EXIT=0 DUR=.* OUT=OK'; then
      report A-claude PASS "$OUT"
    else
      report A-claude FAIL "$OUT"
    fi
    # A-opencode: cluster-litellm/gpt-oss (经 B 网关 USB4); 默认模型应已钉本地 cluster-local/gpt-oss
    OUT=$(ssh "$HOST_A" 'bash -s' <<'REMOTE' 2>/dev/null
cd /tmp
out=$(echo 'reply with exactly: OK' | timeout 180 opencode run -m cluster-litellm/gpt-oss 2>/dev/null | tail -1)
echo "OUT=$out"
REMOTE
)
    if echo "$OUT" | grep -q 'OUT=OK'; then
      report A-opencode PASS "$OUT"
    else
      report A-opencode FAIL "$OUT"
    fi
  fi
fi

echo "--------------------------------"
echo "PASS=$PASS FAIL=$FAIL SKIP=$SKIP"
[ "$FAIL" -eq 0 ]
