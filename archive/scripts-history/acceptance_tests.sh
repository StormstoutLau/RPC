#!/bin/bash
# acceptance_tests.sh — C5/C8/C9/C10 验收测试（B 站执行）
set -uo pipefail
M=/opt/llama.cpp-9859/MANIFEST

echo "=== C8: 不一致注入（篡改 version 字段） ==="
sudo sed -i 's/^version      = 9859/version      = 9999/' "$M"
bash /tmp/check_llama_version.sh
echo "C8_exit=$?  (预期 1)"
sudo sed -i 's/^version      = 9999/version      = 9859/' "$M"
bash /tmp/check_llama_version.sh > /dev/null 2>&1
echo "恢复后 exit=$?  (预期 0)"

echo ""
echo "=== C5: MANIFEST 缺失降级 ==="
sudo mv "$M" "$M.bak"
bash /tmp/check_llama_version.sh 2>&1 | grep -E "NO_MANIFEST|指纹|❌" | head -3
echo "C5_exit=${PIPESTATUS[0]}"
sudo mv "$M.bak" "$M"
bash /tmp/check_llama_version.sh > /dev/null 2>&1 && echo "恢复后正常 (exit 0)"

echo ""
echo "=== C9: md5sum -c 重放（两站） ==="
cd /opt/llama.cpp-9859 && sed -n '/\[md5\]/,$p' MANIFEST | tail -n +2 | md5sum -c 2>&1 | tail -2
ssh -o BatchMode=yes scott-lau@scott-lau-NEX.local 'cd /opt/llama.cpp-9859 && sed -n "/\[md5\]/,\$p" MANIFEST | tail -n +2 | md5sum -c 2>&1 | tail -2'

echo ""
echo "=== C10: 回滚演练（切回自身 9859 + 冒烟） ==="
sudo ln -sfn llama.cpp-9859 /opt/llama.cpp
/opt/llama.cpp/llama-cli --version 2>&1 | head -1
echo "C10 完成 (readlink: $(readlink /opt/llama.cpp))"

echo ""
echo "=== 验收测试完成 ==="
