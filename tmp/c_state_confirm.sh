#!/bin/bash
# 确认当前干净状态 + 记录 Auto 档指标
set +e
echo "=== 1. 进程 ==="
pgrep -af llama-server || echo '(无 llama-server)'
echo "=== 2. VRAM 状态 ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
echo "=== 3. 服务状态 ==="
systemctl is-active llama-server@qwen3.8-27b-mtp.service 2>/dev/null
echo "=== 4. 内存 ==="
free -g | head -2
echo "=== 5. 当前 UMA 参数 ==="
grep -oE 'amdgpu.gttsize=[0-9]*|ttm.pages_limit=[0-9]*|amd_iommu=[a-z]*' /proc/cmdline