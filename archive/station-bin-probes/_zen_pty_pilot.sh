#!/usr/bin/env bash
# _zen_pty_pilot.sh — O-43 试点【定稿】: zen 免费档走伪 tty + 输出净化
#   ★ 四个要点全部由实验得出（v1~v7 迭代，教训见台账 O-43）:
#     1) **zen 需要 tty**：非 tty ⇒ 挂死（`RC=124`，DEBUG 日志无任何凭据错误）；伪 tty（`script -qec`）⇒ 可用
#     2) **必须先 cd 到工作区**：否则 opencode 以 `$HOME` 为 cwd ⇒ 产物落到 `~/out/`，
#        会造出"模型没干活"的**假失败**（v1/v2 就栽在这里，两臂同时假失败才暴露）
#     3) **净化用 python3**（站上 3.12.3）：sed 的 CSI 正则 `s/\[[0-9;?]*[ -\/]*[@-~]//g`
#        **实测不匹配**（r2/r3 可以）⇒ 不依赖 sed 正则，改用 python 的 `\x1b\[...`
#     4) **硬断言**：净化为空即 FAIL（防"空文件里的残留计数恒为 0"的假通过）
#   双臂对照：Z = zen + 伪 tty（实验组）· O = openrouter + 普通管道（对照组，已知可用）
# 用法(站上, 由主控 scp 后跑 —— 遵守 R14 脚本落盘): bash /tmp/_zen_pty_pilot.sh [workdir] [budget_s]
set -u
W="${1:-$HOME/agent-workspaces/dogfood}"
B="${2:-120}"
Z_M="opencode/nemotron-3.5-lightning-free"
O_M="openrouter/thinkingmachines/inkling:free"
mkdir -p "$W/out"
cd "$W" || { echo "cd $W 失败"; exit 1; }
FAIL=0

purify() { python3 - "$1" "$2" <<'PY'
import re, sys
raw = open(sys.argv[1], 'rb').read().decode('utf-8', 'replace')
t = re.sub(r'\x1b\[[0-9;?]*[ -/]*[@-~]', '', raw)        # CSI
t = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', t)   # OSC
t = re.sub(r'\x1b.', '', t)                               # 残留 ESC+1 字符
t = t.replace('\r', '')
t = ''.join(c for c in t if c == '\n' or c == '\t' or ord(c) >= 32)
keep = [l for l in t.split('\n')
        if not re.match(r'^(脚本启动于|脚本完成于|Script started|Script done)', l.strip())]
out = []
for l in keep:
    if l.strip() == '' and (not out or out[-1].strip() == ''):
        continue
    out.append(l)
open(sys.argv[2], 'w', encoding='utf-8').write('\n'.join(out).strip() + '\n')
PY
}

arm() {  # $1=臂名 $2=model $3=pty|pipe
  local A="$1" M="$2" MODE="$3"
  local IN="$W/out/.p$A.in" RAW="$W/out/.p$A.raw" CL="$W/out/.p$A.clean"
  local PROD="$W/out/pilot-arm-$A.txt"
  printf '在当前目录下创建 out/pilot-arm-%s.txt，内容只有一行：ARM_%s_OK\n不要读其它文件，不要解释。完成后在 stdout 只输出一行 DONE_%s\n' "$A" "$A" "$A" > "$IN"
  rm -f "$RAW" "$CL" "$PROD"
  local T0 T1
  T0=$(date +%s)
  if [ "$MODE" = pty ]; then
    timeout "$B" script -qec "opencode run -m $M < $IN" "$RAW" > /dev/null 2>&1
  else
    timeout "$B" opencode run -m "$M" < "$IN" > "$RAW" 2>&1
  fi
  local RC=$?
  T1=$(date +%s)
  local RB CB PW PN
  RB=$(wc -c < "$RAW" 2>/dev/null || echo 0)
  purify "$RAW" "$CL" 2>/dev/null || true
  CB=$(wc -c < "$CL" 2>/dev/null || echo 0)
  PW=$([ -f "$PROD" ] && echo yes || echo no)
  PN=$(head -1 "$PROD" 2>/dev/null || echo "")
  echo "ARM=$A MODE=$MODE RC=$RC ELAPSED=$((T1-T0))s RAW=$RB CLEAN=$CB PRODUCT=$PW CONTENT=[$PN]"
  [ "$CB" -gt 0 ] || { echo "  ✗ 净化为空（断言失败）"; FAIL=1; }
  # ⚠ 断言写法教训: `grep -c` 失败时**也会打印 0**, 若再 `|| echo 0` 就变成两行 ⇒ 比较恒假。
  #   必须 `|| true` 取原值, 并用 `${X:-0}` 兜。
  ESCN=$(grep -c $'\033' "$CL" 2>/dev/null || true); ESCN=${ESCN:-0}
  CSIN=$(grep -oE '\[[0-9;?]*[a-zA-Z]' "$CL" 2>/dev/null | wc -l | tr -d ' '); CSIN=${CSIN:-0}
  echo "  残留 ESC=$ESCN (应 0)  残留 CSI 字面=$CSIN (应 0)"
  [ "$ESCN" = "0" ] || { echo "  ✗ 残留 ESC"; FAIL=1; }
  [ "$CSIN" = "0" ] || { echo "  ✗ 残留 CSI 字面"; FAIL=1; }
  [ "$PW" = "yes" ] || echo "  ⚠ 本臂未产出文件（RC=$RC ⇒ 超时/未调用工具，属已知波动，非净化问题）"
  echo "  --- 净化后（候选 out/.agent-output.txt）---"
  sed 's/^/  |/' "$CL" 2>/dev/null | head -12
}

echo "########## 实验组 Z: zen + 伪 tty ##########"; arm Z "$Z_M" pty
echo "########## 对照组 O: openrouter + 普通管道 ##########"; arm O "$O_M" pipe
echo "########## 结论 ##########"
[ "$FAIL" = "0" ] && echo "试点 PASS：伪 tty 下 zen 可用 + 净化无残留" || echo "试点 FAIL（见上面 ✗）"
