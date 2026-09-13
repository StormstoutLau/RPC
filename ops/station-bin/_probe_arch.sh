#!/bin/bash
# probe_arch.sh - probe glm5next / dsv4_hc / git head across llama.cpp dirs on B
for d in /home/scott-lau/llama.cpp /home/scott-lau/llama.cpp-vulkan-b10715; do
  echo "=== $d ==="
  echo -n "  dir_exists: "; [ -d "$d" ] && echo yes || echo no
  [ -d "$d" ] || continue
  echo -n "  glm5next in llama-arch: "; grep -ac 'glm5next\|arch_glm' "$d/src/llama-arch.cpp" 2>/dev/null || echo 0
  echo -n "  glm_arch in llama-arch: "; grep -ac 'LLM_ARCH_GLM\|"glm"' "$d/src/llama-arch.cpp" 2>/dev/null || echo 0
  echo "  dsv4_hc files:"; ls "$d"/src/ggml-vulkan/*dsv4* 2>/dev/null || grep -rl 'dsv4_hc\|DSV4_HC' "$d/src" 2>/dev/null | head -3 || echo "  (none)"
  echo -n "  git head: "; (git -C "$d" log --oneline -1 2>/dev/null || echo "no-git($d)") 
done
echo "=== master llama.cpp version header ==="
grep -E 'LLAMA_VERSION_(MAJOR|MINOR|PATCH)|LLAMA_BUILD_NUMBER' /home/scott-lau/llama.cpp/include/llama.h /home/scott-lau/llama.cpp-vulkan-b10715/include/llama.h 2>/dev/null | head -8
echo PROBE_ARCH_DONE