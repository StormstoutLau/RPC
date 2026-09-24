#!/usr/bin/env bash
# _zen_stability_sample.sh — O-43 稳定性采样：连跑 N 次 zen（伪 tty）+ 穿插 openrouter 对照
#   设计：
#     ① **站上落盘**：逐轮把结果**追加**到 CSV ⇒ 主控可随时回收，断连不丢部分结果
#     ② 每轮**换文件名与内容**（防模型复用缓存导致"假稳定"）
#     ③ 预算给足（默认 150s）—— 目的是区分"慢"与"挂死"
#     ④ 穿插**对照臂**（默认第 1 轮与最后一轮）⇒ 若对照组也变慢，说明是环境而非 zen
#     ⑤ 每轮记录三元状态：产出成功 / 返回但未产出 / 超时（RC=124）
#   用法（站上，建议 nohup 后台跑）：
#     nohup bash /tmp/_zen_stability_sample.sh [N=6] [budget=150] > /tmp/stab.log 2>&1 &
#     CSV: /tmp/zen_stability.csv
set -u
N="${1:-6}"
B="${2:-150}"
W="${3:-$HOME/agent-workspaces/dogfood}"
CSV=/tmp/zen_stability.csv
Z_M="opencode/nemotron-3.5-lightning-free"
O_M="openrouter/thinkingmachines/inkling:free"
mkdir -p "$W/out/stab"
cd "$W" || exit 1

: > "$CSV"
echo "iter,arm,mode,rc,elapsed,product,clean_bytes,esc,state,ts" >> "$CSV"
echo "# 采样开始 $(date -Is)  N=$N budget=${B}s workdir=$W" 

purify() { python3 - "$1" "$2" <<'PY'
import re, sys
raw = open(sys.argv[1], 'rb').read().decode('utf-8', 'replace')
t = re.sub(r'\x1b\[[0-9;?]*[ -/]*[@-~]', '', raw)
t = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', t)
t = re.sub(r'\x1b.', '', t)
t = t.replace('\r', '')
t = ''.join(c for c in t if c == '\n' or c == '\t' or ord(c) >= 32)
keep = [l for l in t.split('\n') if not re.match(r'^(脚本启动于|脚本完成于|Script started|Script done)', l.strip())]
out = []
for l in keep:
    if l.strip() == '' and (not out or out[-1].strip() == ''):
        continue
    out.append(l)
open(sys.argv[2], 'w', encoding='utf-8').write('\n'.join(out).strip() + '\n')
PY
}

one() {  # $1=iter $2=arm(Z|O) $3=model $4=mode(pty|pipe)
  local i="$1" A="$2" M="$3" MODE="$4"
  local IN="$W/out/.st$i.in" RAW="$W/out/.st$i.raw" CL="$W/out/.st$i.clean"
  local PROD="$W/out/stab/iter-$i.txt"
  printf '在当前目录下创建 out/stab/iter-%s.txt，内容只有一行 STAB_%s_OK\n不要读其它文件，不要解释。完成后 stdout 只输出一行 DONE_%s\n' "$i" "$i" "$i" > "$IN"
  rm -f "$RAW" "$CL" "$PROD"
  local T0 T1 RC
  T0=$(date +%s)
  if [ "$MODE" = pty ]; then
    timeout "$B" script -qec "opencode run -m $M < $IN" "$RAW" > /dev/null 2>&1
  else
    timeout "$B" opencode run -m "$M" < "$IN" > "$RAW" 2>&1
  fi
  RC=$?
  T1=$(date +%s)
  local EL=$((T1-T0)) PROD_YN="no" CB=0 ESCN=0 STATE
  [ -f "$PROD" ] && PROD_YN="yes"
  purify "$RAW" "$CL" 2>/dev/null || true
  CB=$(wc -c < "$CL" 2>/dev/null || echo 0)
  ESCN=$(grep -c $'\033' "$CL" 2>/dev/null || true); ESCN=${ESCN:-0}
  if [ "$PROD_YN" = "yes" ]; then STATE="PRODUCED"
  elif [ "$RC" = "124" ]; then STATE="TIMEOUT"
  else STATE="NO_PRODUCT"; fi
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' "$i" "$A" "$MODE" "$RC" "$EL" "$PROD_YN" "$CB" "$ESCN" "$STATE" "$(date -Is)" >> "$CSV"
  echo "[iter $i] arm=$A mode=$MODE rc=$RC ${EL}s product=$PROD_YN clean=${CB}B state=$STATE"
}

for i in $(seq 1 "$N"); do
  if [ "$i" = "1" ]; then one "$i" O "$O_M" pipe   # 首轮对照
  else one "$i" Z "$Z_M" pty
  fi
done
one "$((N+1))" O "$O_M" pipe                        # 末轮对照

echo ""
echo "########## 汇总 ##########"
echo "--- Z 臂（zen + 伪 tty）逐轮 ---"
awk -F, -v OFS=' | ' 'NR>1 && $2=="Z"{print "iter"$1, $5"s", $9}' "$CSV"
echo "--- 成功率（Z 臂, PRODUCED / 总）---"
awk -F, 'NR>1 && $2=="Z"{t++; if($9=="PRODUCED")p++} END{printf "PRODUCED=%d / %d = %.0f%%\n", p, t, (t?100*p/t:0)}' "$CSV"
echo "--- 状态分布（Z 臂）---"
awk -F, 'NR>1 && $2=="Z"{c[$9]++} END{for(k in c) printf "  %s=%d\n", k, c[k]}' "$CSV"
echo "--- 时延分位（Z 臂, 仅成功的）---"
awk -F, 'NR>1 && $2=="Z" && $9=="PRODUCED"{print $5}' "$CSV" | sort -n > /tmp/_lat.txt
if [ -s /tmp/_lat.txt ]; then
  awk '{a[NR]=$1; s+=$1} END{printf "  n=%d  min=%ds  median=%ds  max=%ds  mean=%.0fs\n", NR, a[1], (NR%2?a[(NR+1)/2]:(a[NR/2]+a[NR/2+1])/2), a[NR], s/NR}' /tmp/_lat.txt
else echo "  (无成功样本)"; fi
echo "--- 对照臂（openrouter）---"
awk -F, 'NR>1 && $2=="O"{print "  iter"$1, $5"s", $9}' "$CSV"
echo "--- 净化自检（应为 0）---"
awk -F, 'NR>1{ if($8!="0") n++ } END{print "  非零 ESC 轮次 = " n+0}' "$CSV"
echo "########## 采样结束 $(date -Is) ##########"
