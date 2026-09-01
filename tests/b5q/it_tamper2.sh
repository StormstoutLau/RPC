#!/bin/bash
# B5q §4 GREEN: verify 范围修复后 — ① 文件缺失检出 (rc 6, 点名) ② 目录级恢复路径收敛
set -uo pipefail
D=/data/models/gguf/Jackrong/Qwen3.5-27B-Gemini-3.1-Pro-Reasoning-Distill-GGUF

echo '--- 1. 文件缺失检出 (verify 范围 = A_ONLY ∨ .sha256 标记; Jackrong 有标记 → 在范围内) ---'
bash ~/scripts/b5k_sync.sh --go --usb4 --verify 2>&1 | grep -v 'xfr#' | grep -E 'verify|校验|FATAL|失败' | head -10
echo "rc=${PIPESTATUS[0]} (预期 6)"

echo '--- 2. 目录级恢复 (rm 目录 → A_ONLY 触发重传) ---'
rm -rf "$D"
bash ~/scripts/b5k_sync.sh --go --usb4 --verify 2>&1 | grep -v 'xfr#' | grep -E 'A-only|Jackrong|verify|校验|===' | head -12
echo "rc=${PIPESTATUS[0]} (预期 0)"
