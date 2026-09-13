#!/bin/bash
# probe_glm2.sh - inspect glm arch support detail on master llama.cpp (B)
M=/home/scott-lau/llama.cpp
echo "=== master build number ==="
grep -aE 'LLAMA_BUILD_NUMBER|LLAMA_COMMIT' "$M/include/llama.h" "$M/include/llama_version.h" 2>/dev/null | head -6
echo "=== arch list containing glm ==="
grep -an 'glm' "$M/src/llama-arch.cpp" 2>/dev/null | head -20
echo "=== arch names enum ==="
grep -an 'LLM_ARCH_' "$M/include/llama.h" 2>/dev/null | grep -i glm
echo "=== llama.cpp version of b10715 ==="
grep -aE 'LLAMA_BUILD_NUMBER|b10715|LLAMA_VERSION' /home/scott-lau/llama.cpp-vulkan-b10715/include/llama.h 2>/dev/null | head -5
strings /home/scott-lau/llama.cpp-vulkan-b10715/llama-server 2>/dev/null | grep -aiE 'b[0-9]{5}|v[0-9]+\.[0-9]+' | head -5
echo "=== glm5 / glm5next files on disk ==="
ls -la /data/models/gguf/*glm*/*.gguf /home/scott-lau/glm* 2>/dev/null | head
echo PROBE_GLM2_DONE