#!/bin/bash
L=~/.lmstudio/server-logs/2026-09/2026-09-10.1.log
echo "=== 引擎/后端/模型/推理相关行 ==="
grep -iE "version|hip|vulkan|rocm|gfx1151|llama_server|model:|loaded|reasoning|qwen" "$L" | head -30
echo "=== 尾部 15 行 (最近运行) ==="
tail -15 "$L"