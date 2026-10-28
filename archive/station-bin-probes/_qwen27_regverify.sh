#!/bin/bash
echo "=== systemd instance ==="
systemctl is-active llama-server@qwen3.8-27b-mtp
echo "=== engine proc ==="
pgrep -a -f 'qwen3.8-27b-mtp\|18080' | grep llama-server | head -1
echo "=== MTP/spec in journal ==="
sudo journalctl -u llama-server@qwen3.8-27b-mtp --no-pager 2>/dev/null | grep -iE 'draft-mtp|spec.*impl|addressing speculative|model loaded' | head -6
echo "=== health ==="
curl -s --max-time 3 http://127.0.0.1:18080/health
echo
echo "=== quick completion ==="
curl -s --max-time 60 http://127.0.0.1:18080/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen3.8-27b-mtp","messages":[{"role":"user","content":"用一句话介绍因子投资。"}],"max_tokens":40,"temperature":0}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print("content:",d["choices"][0]["message"]["content"]); u=d["usage"]; print("tps:", round(u["completion_tokens"]/(u["completion_tokens"]/10 if u["completion_tokens"] else 1),2))' 2>&1 || echo "(python parse skip)"