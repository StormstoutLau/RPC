#!/bin/bash
# C 站: gpt-oss Vulkan 冒烟 + 吞吐
set +e
echo "=== 1. /health ==="
curl -s http://127.0.0.1:18083/health | head -1
echo ""
echo "=== 2. 生成冒烟 ==="
curl -s http://127.0.0.1:18083/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"Reply with exactly: VULKAN LOAD PASS"}],"max_tokens":24}' \
  2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('CONTENT:', d.get('choices',[{}])[0].get('message',{}).get('content','NO CONTENT')[:200])" 2>/dev/null || echo '(解析失败)'
echo "=== 3. timings ==="
tail -40 /tmp/c_gpt_vk.log | grep -E 'print_timing' | tail -3
echo "=== 4. 进程 ==="
ps -o pid,stat,%cpu,time,rss -p 6190 2>/dev/null
echo "=== 5. 新 fault? ==="
sudo -n dmesg 2>/dev/null | grep -c 'gfxhub. page fault'