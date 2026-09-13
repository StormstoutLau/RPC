#!/bin/bash
# C 站: Vulkan bug prompt eval + 更长生成基准
set +e
echo "=== 1. 完整 print_timing (含 prompt eval) ==="
grep 'print_timing' /tmp/c_gpt_vk.log | tail -3 | sed 's/.*slot //'
echo ""
echo "=== 2. 长生成 (128 tokens) 测稳定吞吐 ==="
curl -s http://127.0.0.1:18083/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"Count from one to ten, one per line."}],"max_tokens":128}' \
  2>/dev/null >/dev/null
sleep 3
echo "--- 该次 timings ---"
grep 'print_timing' /tmp/c_gpt_vk.log | tail -1 | sed 's/.*slot //'
echo "=== 3. 对照确认 ==="
echo "C 站 HIP:   prefill 152 t/s / decode 48.8 t/s"
echo "C 站 Vulkan: prefill ? / decode 53.3 t/s (首个冒烟)"