#!/bin/bash
echo "=== unsloth 引擎版本 ==="
~/.unsloth/llama.cpp/llama-cli --version 2>/dev/null | head -2
echo "=== 架构支持 ==="
strings ~/.unsloth/llama.cpp/libllama.so 2>/dev/null | grep -oE "qwen4exp|qwen35|glm5next|minimax" | sort -u | head -8
echo "=== HIP 后端 so ==="
ls ~/.unsloth/llama.cpp/ | grep -iE "hip|cuda"
echo "=== Vulkan so 存在 ==="
ls ~/.unsloth/llama.cpp/libggml-vulkan.so 2>/dev/null || echo "no vulkan so"
echo "=== 与 /opt 对比 (当前主线) ==="
/opt/llama.cpp/llama-cli --version 2>/dev/null | head -2