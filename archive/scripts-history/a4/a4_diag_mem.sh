#!/bin/bash
# a4_diag_mem.sh — 诊断 torch 显存探测 vs 实际 GTT/VRAM (Strix Halo iGPU)
set -uo pipefail
PY=/home/scott-lau/vllm-rocm/bin/python3.14
SITE=/home/scott-lau/vllm-rocm/lib/python3.14/site-packages
export LD_LIBRARY_PATH="/home/scott-lau/vllm-rocm/lib:${SITE}/_rocm_sdk_core/lib:${SITE}/_rocm_sdk_libraries/lib"

echo "===== 1. sysfs 显存 (每张 card) ====="
for d in /sys/class/drm/card*/device; do
  echo "--- $d ---"
  for f in mem_info_vram_total mem_info_vram_used mem_info_gtt_total mem_info_gtt_used mem_info_vis_vram_total mem_info_vis_vram_used; do
    [ -f "$d/$f" ] && printf "  %-28s = %s\n" "$f" "$(cat "$d/$f")"
  done
done

echo "===== 2. 内核参数 (amdgpu/ttm) ====="
cat /proc/cmdline 2>/dev/null
echo "--- amdgpu.gttsize ---"
cat /sys/module/amdgpu/parameters/gttsize 2>/dev/null || echo "n/a"
echo "--- ttm.pages_limit ---"
cat /sys/module/ttm/parameters/pages_limit 2>/dev/null || echo "n/a"

echo "===== 3. torch HIP 显存探测 ====="
"$PY" <<'EOF'
import torch
print("torch:", torch.__version__, "hip:", torch.version.hip)
print("is_available:", torch.cuda.is_available())
print("device_count:", torch.cuda.device_count())
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print("name:", p.name)
    print("total_memory:", p.total_memory, "=", p.total_memory/2**30, "GiB")
    free, total = torch.cuda.mem_get_info(0)
    print("mem_get_info: free=", free, "total=", total, "=>", free/2**30, "GiB free")
EOF

echo "===== 4. 占用进程 (RSS>1G) ====="
ps -eo pid,stat,rss,comm --sort=-rss | awk 'NR==1 || $3>1048576' | head -12

echo "===== 5. rocm-smi (若存在) ====="
which rocm-smi >/dev/null 2>&1 && rocm-smi --showmeminfo vram 2>/dev/null | head -30 || echo "rocm-smi not in PATH"
echo "DIAG_MEM_DONE"
