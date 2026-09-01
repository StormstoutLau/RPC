#!/bin/bash
# B5q §4 篡改检出集成实测: 改 1 字节 + 保 mtime (绕过 rsync quick check) → verify 须点名报错
# 之后恢复: rm 篡改文件 → 重跑 --go (rsync 重传) → verify PASS
set -uo pipefail
D=/data/models/gguf/Jackrong/Qwen3.5-27B-Gemini-3.1-Pro-Reasoning-Distill-GGUF
F="$D/Qwen3.5-27B.Q8_0.gguf"

echo '--- 1. 篡改 1 字节 (offset 1024) + 恢复 mtime ---'
MT=$(stat -c %y "$F")
printf 'Z' | sudo dd of="$F" bs=1 seek=1024 conv=notrunc 2>/dev/null
sudo touch -d "$MT" "$F"
echo "tampered: $(stat -c '%s %y' "$F")"

echo '--- 2. 重跑 b5k --go --verify (rsync 应跳过, verify 应报错) ---'
bash ~/scripts/b5k_sync.sh --go --usb4 --verify 2>&1 | grep -v 'xfr#' | tail -12
RC=${PIPESTATUS[0]}
echo "b5k rc=$RC (预期 6)"

echo '--- 3. 恢复: 删篡改文件重传 ---'
rm -f "$F"
bash ~/scripts/b5k_sync.sh --go --usb4 --verify 2>&1 | grep -v 'xfr#' | grep -E 'Jackrong|校验|===' | tail -6
echo "restored: $(sha256sum -c "$D/.sha256" 2>&1 | tail -1)"
