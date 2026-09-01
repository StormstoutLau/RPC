#!/bin/bash
# a4_diag_alloc.sh — 判定 torch 真实可用显存: 能否在 VRAM 上分配 40GiB
set -uo pipefail
PY=/home/scott-lau/vllm-rocm/bin/python3.14
SITE=/home/scott-lau/vllm-rocm/lib/python3.14/site-packages
export LD_LIBRARY_PATH="/home/scott-lau/vllm-rocm/lib:${SITE}/_rocm_sdk_core/lib:${SITE}/_rocm_sdk_libraries/lib"
export PYTORCH_HIP_ALLOC_CONF='expandable_segments:True'
"$PY" <<'EOF'
import torch
print("torch:", torch.__version__, "hip:", torch.version.hip)
print("props total_memory:", torch.cuda.get_device_properties(0).total_memory/2**30, "GiB")
free0, total0 = torch.cuda.mem_get_info(0)
print("mem_get_info BEFORE:", free0/2**30, "free /", total0/2**30, "total GiB")

# 尝试逐步分配, 找到真实上限
allocated = 0
sizes = [8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88]
tensors = []
for gb in sizes:
    nbytes = gb * 2**30
    try:
        t = torch.empty(nbytes, dtype=torch.uint8, device='cuda')
        t.zero_()  # 强制真实提交
        tensors.append(t)
        allocated = gb
        print(f"  allocated {gb:3d} GiB OK")
    except Exception as e:
        print(f"  allocated {gb:3d} GiB FAILED: {type(e).__name__}: {str(e)[:120]}")
        break

free1, total1 = torch.cuda.mem_get_info(0)
print("mem_get_info AFTER:", free1/2**30, "free /", total1/2**30, "total GiB")
print("RESULT: max_allocated =", allocated, "GiB")
del tensors
torch.cuda.empty_cache()
EOF
echo "DIAG_ALLOC_DONE"
