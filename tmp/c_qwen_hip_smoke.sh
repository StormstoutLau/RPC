#!/bin/bash
# C 站: Auto 档 qwen3.8 HIP 冒烟 + 吞吐
set +e
echo "=== 1. /health ==="
curl -s http://127.0.0.1:18082/health | head -1
echo ""
echo "=== 2. 生成冒烟 ==="
curl -s http://127.0.0.1:18082/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.8","messages":[{"role":"user","content":"hi, say hello in one word"}],"max_tokens":32}' \
  2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('choices',[{}])[0].get('message',{}).get('content','NO CONTENT'))" 2>/dev/null || echo '(解析失败，原始响应见下)'
echo "=== 3. timings? server 无则跳过 ==="
curl -s -X POST http://127.0.0.1:18082/props 2>/dev/null | head -c 200
echo ""
echo "=== 4. 进程状态 ==="
ps -o pid,stat,%cpu,time,rss -p 4201 2>/dev/null
echo "=== 5. qwen 服务 18080 仍在 (Vulkan) ==="
ss -tlnp 2>/dev/null | grep 18080 | head -1 | sed 's/users:.*/:(18080 up)/' || echo '(18080 down)'