#!/bin/bash
echo "=== B 站 gpt-oss 模型 ==="
ls -la /data/models/gguf/lmstudio-community/ 2>/dev/null | grep -iE "gpt-oss|nemotron"
find /data/models -maxdepth 4 -iname "*gpt-oss*" 2>/dev/null | head
echo "=== unsloth 可用性 ==="
which unsloth 2>/dev/null; ls ~/.unsloth/llama.cpp/build/bin/llama-server 2>/dev/null && echo "ROCm llama OK"
ls ~/llama.cpp-vulkan-b10715/llama-server 2>/dev/null && echo "Vulkan b10715 OK"
echo "=== LiteLLM 网关 ==="
ss -tln 2>/dev/null | grep -E ":4000" | awk '{print $4}'
echo "=== elev/project dir for gpt-oss conf (B) ==="
ls /etc/llama-instances/ 2>/dev/null | grep -iE "gpt-oss|nemotron"