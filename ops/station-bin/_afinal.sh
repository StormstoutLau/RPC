#!/bin/bash
echo "==== A 站 CLI 端点最终状态 ===="
echo "== opencode cluster-local (应 8087 + sk-unsloth-581f) =="
grep -A4 '"cluster-local"' /home/scott-lau/.config/opencode/opencode.jsonc | grep -E 'baseURL|apiKey'
echo
echo "== claude settings (应 8087, 恢复 fable 遗留模型名) =="
grep -E 'ANTHROPIC_BASE_URL|ANTHROPIC_MODEL|"model"' /home/scott-lau/.claude/settings.json
echo
echo "== 当前 unsloth gpt-oss 实例 =="
ps -eo pid,etime,rss,cmd | grep '[l]lama-server' | grep -v defunct | awk '{printf "pid=%s etime=%s rss=%.1fG\n",$1,$2,$3/1048576}'
grep -oe 'running at http://[0-9.:]*' /home/scott-lau/.unsloth/run-gpt-kvq.log | head -1
grep -oe 'sk-unsloth-[a-f0-9]*' /home/scott-lau/.unsloth/run-gpt-kvq.log | tail -1
echo
echo "== opencode 主通道最终验证 (stdin 管道) =="
echo 'Reply with exactly the single word OPENCODE-FINAL-OK' | timeout 120 opencode run -m cluster-local/gpt-oss 2>&1 | tail -3
echo "[rc=${PIPESTATUS[1]}]"