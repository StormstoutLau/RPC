#!/bin/bash
# C 站: 清理 Auto 档 HIP 实例 + 评估 gpt-oss 可行性
set +e
echo "=== 1. 清理 qwen HIP 实例 (保留 18080 Vulkan qwen) ==="
pkill -9 -f 'llama-server.*18082' 2>/dev/null
pkill -9 -f 'llama-server.*qwen3.8-27b.*ROCm' 2>/dev/null
sleep 2
echo '--- 18082 ---'
ss -tlnp 2>/dev/null | grep 18082 || echo '(freed)'
echo '--- 18080 保留 ---'
ss -tlnp 2>/dev/null | grep 18080 | head -1 | sed 's/users:.*/:(18080 up)/' || echo '(18080 down!)'
echo "=== 2. 内存现状 ==="
free -g | head -2
echo "=== 3. gpt-oss 60G 可行性矩阵 ==="
echo "Auto 档(当前): 系统 62G, gpt-oss 60G + KV => 不可行(超限)"
echo "1G 档(之前):   系统 124G, gpt-oss 60G 可行但 HIP page fault"
echo "=> 两者互斥: 既需小 carveout(HIP 可用) 又需大系统内存(gpt-oss 承载)"
echo "=== 4. 检查 B 站是否有小档位线索 (UMA 档位表) ==="
echo "B 站 BIOS 版本 GTRPR07 (AZW), A 站 1.02 (TianBei) — C 站需影核 BIOS 提供 0.5G/1G 档位内可承载档"