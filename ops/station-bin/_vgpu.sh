#!/bin/bash
echo "== nvidia-smi 是否存在 =="
which nvidia-smi 2>/dev/null && nvidia-smi -L 2>/dev/null || echo "NO nvidia-smi"
echo "== rocm 卡 =="
which rocminfo 2>/dev/null && rocminfo 2>/dev/null | grep -A3 "Marketing Name\|gfx[0-9]" | head -20 || echo "NO rocminfo"
echo "== lspci GPU =="
lspci 2>/dev/null | grep -Ei "vga|3d|display|radeon|nvidia" | head
echo "== 系统 llama-server 是 CUDA 还是 ROCm 构建？ =="
ldd /opt/llama.cpp/llama-server 2>/dev/null | grep -Ei "cuda|rocm|hip|vulkan|cudart" | head
strings /opt/llama.cpp/llama-server 2>/dev/null | grep -m3 -Ei "CUDA|ROCm|HIP|Vulkan" | head