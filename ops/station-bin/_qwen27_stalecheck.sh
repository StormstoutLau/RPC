#!/bin/bash
B=/home/scott-lau/llama.cpp/build/bin/llama-server
echo "=== file stat ==="
stat -c '%y %n' "$B"
echo "=== master build sanity: does strings find other qwen archs? ==="
strings "$B" 2>/dev/null | grep -ao 'qwen[a-z0-9]*' | sort -u
echo "=== does it find glm / qwen35 anywhere ==="
strings "$B" 2>/dev/null | grep -ao 'qwen35' | sort -u
echo "=== source llama-arch qwen lines ==="
grep -n '"qwen' /home/scott-lau/llama.cpp/src/llama-arch.cpp 2>/dev/null
echo "=== is build dir configured for vulkan? ==="
grep -i 'GGML_VULKAN\|CMAKE_BUILD_TYPE' /home/scott-lau/llama.cpp/build/CMakeCache.txt 2>/dev/null | head -5
echo "=== cmake/make availability + cores ==="
nproc; which cmake make ninja 2>/dev/null