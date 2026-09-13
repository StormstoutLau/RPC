#!/bin/bash
# probe_glm_env.sh - inspect existing glm-5.3-flash instance env and its model file
echo "=== /etc/llama-instances/glm-5.3-flash.env ==="
cat /etc/llama-instances/glm-5.3-flash.env 2>/dev/null
echo "=== instance dir ==="
ls -la /etc/llama-instances/ 2>/dev/null
echo "=== model path referenced (parse MODEL= / MSM= ) ==="
grep -aE '^(MODEL|MSM|CTX|PORT|DEVICE|ALIAS)' /etc/llama-instances/*.env 2>/dev/null | grep -i glm
echo "=== check glm gguf existence by likely paths ==="
for p in $(grep -aE '\.gguf' /etc/llama-instances/glm-5.3-flash.env 2>/dev/null | sed -E 's/.*=//'); do
  echo -n "  exists? $p : "; [ -f "$p" ] && echo YES || echo NO
done
echo PROBE_GLM_ENV_DONE