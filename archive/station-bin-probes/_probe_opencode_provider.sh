#!/bin/bash
# _probe_opencode_provider.sh — 判别"站上 opencode 的某个 provider/model 到底能不能用"
#
# 为什么需要它 (2026-09-21, P3 实弹副产物):
#   `opencode/*`(= zen, opencode 自带网关) 在**没有凭据**时**不报错、只静默挂死** ——
#   表现为 `timeout 120` 被掐断 3 次(360s)、输出只有 `> build · <model>` banner。
#   它**不会**像别的 provider 那样记 `stream error`, 故"挂了"与"慢"在外部不可区分。
#   本脚本用**有界预算**把这个静默失败暴露成 `PROBE_RC=124`。
#
# 用法 (在**站上**跑; 由主控 `ssh <host> 'bash /tmp/_probe_opencode_provider.sh <model> [budget]'`):
#   bash _probe_opencode_provider.sh                       # 默认探 zen 的 lightning
#   bash _probe_opencode_provider.sh openrouter/thinkingmachines/inkling:free 45
#
# 判据 (2026-09-21 实测标定, B 站 opencode 1.18.25):
#   PROBE_RC=0   + 输出含 `ZEN-OK`        ⇒ provider 可用 (openrouter 实测 16s)
#   PROBE_RC=124 + 只有 banner、无错误行  ⇒ **静默挂死** (zen 无凭据实测如此; 见 OPEN-ISSUES)
#   PROBE_RC=1   + 输出含 stream error…   ⇒ 快速失败 (如地区墙/模型下架) —— 可读、可修
#
# ⚠ 用 stdin 管道而非位置参数: 位置参数形式在 opencode 1.18.25 会挂死(项目日志实证)。
# ⚠ ASCII-only + LF-only (站上 bash 跑; 勿加 BOM, 否则 shebang 变 \xEF\xBB\xBF#! 直接不可执行)。
set -uo pipefail
MODEL="${1:-opencode/nemotron-3.5-lightning-free}"
BUDGET="${2:-30}"
IN=/tmp/_probe_oc_in.txt
OUT=/tmp/_probe_oc_out.txt
printf 'reply with exactly: ZEN-OK\n' > "$IN"
cd "$HOME" || exit 8
START=$(date +%s)
timeout "$BUDGET" opencode run -m "$MODEL" < "$IN" > "$OUT" 2>&1
RC=$?
ELAPSED=$(( $(date +%s) - START ))
echo "PROBE_MODEL=$MODEL"
echo "PROBE_RC=$RC"
echo "PROBE_ELAPSED=${ELAPSED}s"
echo "PROBE_OUT_BYTES=$(wc -c < "$OUT")"
echo "--- opencode auth list (凭据实况; 这决定 provider 能不能用) ---"
opencode auth list 2>&1 | head -n 6
echo "--- output head ---"
head -n 25 "$OUT"
echo "--- auth/error-ish lines ---"
grep -inE "auth|credential|401|403|api key|login|error|fail|forbidden|not available" "$OUT" | head -n 12
exit 0
