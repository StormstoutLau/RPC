#!/bin/bash
# C 站: BIOS iGPU=Auto 后复查 VRAM carveout + 环境
set +e
echo "=== 1. VRAM carveout (核心看点) ==="
cat /sys/class/drm/card1/device/mem_info_vram_total 2>/dev/null | xargs echo 'vram_total='
cat /sys/class/drm/card1/device/mem_info_gtt_total 2>/dev/null | xargs echo 'gtt_total='
echo "=== 2. dmesg VRAM 初始化 ==="
sudo -n dmesg 2>/dev/null | grep -E 'VRAM:' | head -2
echo "=== 3. cmdline (仍含 amd_iommu=off?) ==="
grep -oE 'amdgpu.gttsize=[0-9]*|ttm.pages_limit=[0-9]*|amd_iommu=[a-z]*' /proc/cmdline
echo "=== 4. 内存 ==="
free -g | head -2
echo "=== 5. load-gate ==="
bash /tmp/load-gate 60 2>&1 | tail -3 || echo '(load-gate 缺失需重部署)'
echo "=== 6. 引擎/设备 ==="
~/.unsloth/llama.cpp/build/bin/llama-server --list-devices 2>&1 | head -4