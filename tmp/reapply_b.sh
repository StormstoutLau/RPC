#!/bin/bash
# 应用修改后的 boot_q38f_b.sh 重启引擎，并重启 runner（无 preserve 修复）
set -uo pipefail
cd /tmp
scp -q /c/tmp/boot_q38f_b.sh scott-lau@scott-lau-GTR-Pro.local:/tmp/boot_q38f_b.sh 2>/dev/null || true
bash /tmp/boot_q38f_b.sh 8094 2>&1 | tail -5
echo "== 引擎就绪，清理旧空答并重启 runner =="
rm -rf /tmp/res_q38f_fix /tmp/res_q38f_fix2
sleep 1
echo "done"