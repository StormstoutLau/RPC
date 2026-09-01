#!/bin/bash
# diag_link.sh — 诊断 v0.2.0 共享库解析（B 站）
cd /opt/llama.cpp-v0.2.0 || exit 1
echo "=== LD_LIBRARY_PATH 解析测试 ==="
LD_LIBRARY_PATH=. ldd ./llama-cli 2>&1 | grep -E 'not found|impl' | head -6
echo "=== 9859 对比 ==="
cd /opt/llama.cpp-9859 && LD_LIBRARY_PATH=. ldd ./llama-cli 2>&1 | grep -E 'impl' | head -4
echo "=== runpath 检查 ==="
readelf -d /opt/llama.cpp-v0.2.0/llama-cli | grep -i 'runpath\|rpath' || echo "v0.2.0 无 RUNPATH"
readelf -d /opt/llama.cpp-9859/llama-cli | grep -i 'runpath\|rpath' || echo "9859 无 RUNPATH"
