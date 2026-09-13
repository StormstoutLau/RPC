#!/bin/bash
# C 站: gpt-oss-120b HIP 冒烟 + 吞吐
set +e
echo "=== 1. /health ==="
curl -s http://127.0.0.1:18081/health | head -1
echo ""
echo "=== 2. 生成冒烟 ==="
curl -s http://127.0.0.1:18081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"Reply with exactly: HIP LOAD PASS"}],"max_tokens":24}' \
  2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('CONTENT:', d.get('choices',[{}])[0].get('message',{}).get('content','NO CONTENT')[:200])" 2>/dev/null || echo '(解析失败)'
echo "=== 3. timings 从日志取 ==="
tail -30 /tmp/c_gpt_4g.log | grep -E 'print_timing|prompt eval|eval time' | tail -4
echo "=== 4. 进程状态 ==="
ps -o pid,stat,%cpu,time,rss -p 5229 2>/dev/null
echo "=== 5. VRAM 归属确认 (模型放哪) ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null | xargs echo 'gtt_used='
echo "=== 6. 新 page fault? ==="
sudo -n dmesg 2>/dev/null | grep -c 'gfxhub. page fault'