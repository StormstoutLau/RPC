#!/bin/bash
# probe_glm_relocate.sh - find GLM gguf actual location + check deepseek env + binding
echo "=== unsloth dir on B ==="
ls -lah /data/models/gguf/unsloth/ 2>/dev/null
echo "=== deepseek-v4-flash.env ==="
cat /etc/llama-instances/deepseek-v4-flash-0731.env 2>/dev/null
echo "=== find GLM-5.3-Flash anywhere (B, /data /home /srv) ==="
find /data /home /srv -iname '*GLM-5.3-Flash*' 2>/dev/null | head
find /data /home -iname '*5.3*flash*.gguf' 2>/dev/null | head
echo "=== all ggufs (to see what models ARE present) ==="
find /data/models -iname '*.gguf' 2>/dev/null | sed 's|/[^/]*$||' | sort | uniq -c
echo PROBE_GLM_RELOCATE_DONE