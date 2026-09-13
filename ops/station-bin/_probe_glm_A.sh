#!/bin/bash
# probe_glm_A.sh - locate GLM + deepseek gguf on A station
echo "=== A models dir ==="
ls -lah /data/models/gguf/ 2>/dev/null
echo "=== A find GLM-5.3-Flash / glm5next gguf ==="
find /data /home /srv -iname '*GLM-5.3-Flash*' -o -iname '*glm-5.3*' 2>/dev/null | grep -i gguf | head
echo "=== A find deepseek ==="
find /data/models -iname '*DeepSeek-V4*' 2>/dev/null | head
echo "=== A all gguf top dirs ==="
find /data/models -iname '*.gguf' 2>/dev/null | sed 's|/[^/]*$||' | sort | uniq -c
echo "=== A llama.cpp dirs + glm5next ==="
ls -d /home/scott-lau/llama.cpp* 2>/dev/null
grep -rl 'glm5next' /home/scott-lau/llama.cpp*/src 2>/dev/null | head -3
echo PROBE_GLM_A_DONE