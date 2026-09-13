#!/bin/bash
# C 站: UMA=4G 后全面排查 + 清理残余
set +e
echo "=== 1. 系统负载 ==="
uptime
echo ""
echo "=== 2. 内核参数当前值 ==="
grep -oE 'amdgpu.gttsize=[0-9]*|ttm.pages_limit=[0-9]*|amd_iommu=[a-z]*' /proc/cmdline
echo ""
echo "=== 3. VRAM/GTT 基础 (UMA=4G 预期 vram_total≈4G) ==="
cat /sys/class/drm/card1/device/mem_info_vram_total 2>/dev/null | xargs echo 'vram_total='
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
cat /sys/class/drm/card1/device/mem_info_gtt_total 2>/dev/null | xargs echo 'gtt_total='
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null | xargs echo 'gtt_used='
echo ""
echo "=== 4. 进程 (llama/rpc/hip 全类) ==="
ps -eo pid,ppid,etime,%cpu,%mem,rss,cmd | grep -E 'llama|ggml|rpc|hip' | grep -v grep | head -10 || echo '(无)'
echo ""
echo "=== 5. 内存全景 ==="
free -g | head -3
echo ""
echo "=== 6. systemd llama 服务状态 ==="
systemctl list-units --type=service 2>/dev/null | grep -i llama | head -5
systemctl is-enabled llama-server@qwen3.8-27b-mtp.service 2>/dev/null
echo ""
echo "=== 7. 端口占用 ==="
ss -tlnp 2>/dev/null | grep -E '18080|18081|18082' || echo '(无 18080/81/82 监听)'
echo ""
echo "=== 8. 设备列表 (HIP 可用池关键看点) ==="
~/.unsloth/llama.cpp/build/bin/llama-server --list-devices 2>&1 | head -4