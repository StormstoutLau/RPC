#!/bin/bash
# probe_glm_arch_A.sh - does A active llama.cpp support glm5next? + actual server engine
echo "=== A running llama servers ==="
ps -ef | grep -E 'llama-server|llama.cpp' | grep -v grep | head -5
echo "=== A active engine dir ==="
for d in /home/scott-lau/llama.cpp-vulkan-b10715 /home/scott-lau/llama.cpp; do
  echo "  --- $d ---"
  echo -n "    glm5next in llama-arch: "; grep -ac 'glm5next\|arch_glm' "$d/src/llama-arch.cpp" 2>/dev/null || echo 0
  echo -n "    glm arch entries: "; grep -an '"glm\|glm5\|GLM5' "$d/src/llama-arch.cpp" 2>/dev/null | head -6
  echo -n "    dsv4_hc files: "; ls "$d"/src/ggml-vulkan/*dsv4* 2>/dev/null | head -2 || echo "  (none)"
  echo -n "    version: "; grep -aE 'LLAMA_BUILD_NUMBER' "$d/include/llama.h" 2>/dev/null | head -1
  echo -n "    git: "; (git -C "$d" log --oneline -1 2>/dev/null || echo "no-git")
done
echo "=== GLM gguf arch tag ==="
strings "/home/scott-lau/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS.gguf" 2>/dev/null | grep -ai 'GLM5NEXT\|general.architecture' | head -5
echo PROBE_GLM_ARCH_A_DONE