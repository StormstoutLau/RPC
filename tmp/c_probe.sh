#!/bin/bash
curl -s --max-time 15 http://127.0.0.1:18080/props -o /tmp/props.json
grep -oE '"n_ctx":[ ]*[0-9]+' /tmp/props.json | head -1
grep -oE '"model_path":"?[^",]*"' /tmp/props.json | head -1
grep -oE '"n_gpu":[ ]*[0-9]+' /tmp/props.json | head -1
grep -oE 'GFX1151|Radeon' /tmp/props.json | head -2
echo "--- chat smoke ---"
curl -s --max-time 40 http://127.0.0.1:18080/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen3.8-27b","messages":[{"role":"user","content":"1+1=?"}],"max_tokens":32}' | grep -oE '"content":"[^"]*"|"finish_reason":"[^"]*"' | head -4