#!/bin/bash
# dual-node RPC chat verification on B
echo "=== CHAT ==="
curl -s --max-time 120 http://127.0.0.1:18081/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen-rpc","messages":[{"role":"user","content":"25*4=?"}],"max_tokens":128}' \
  -o /tmp/rpc_chat2.json 2>/dev/null
python3 -c '
import json
d = json.load(open("/tmp/rpc_chat2.json"))
m = d["choices"][0]["message"]
print("content:", repr(m.get("content")))
print("finish:", d["choices"][0]["finish_reason"])
print("usage:", d["usage"])
'
echo "=== B SPLIT LOG ==="
grep -iE 'split|n_tensor|rpc.*tensor|n_tensors_diff' ~/rpc_client_b2.log 2>/dev/null | head -6
echo "=== A RPC ACTIVE ==="
ssh -o ConnectTimeout=6 -o BatchMode=yes scott-lau@10.10.10.1 "tail -3 ~/rpc-server_a.log 2>/dev/null | cut -c1-90" 2>/dev/null
echo "=== C RPC ACTIVE ==="
ssh -o ConnectTimeout=6 -o BatchMode=yes scott-lau@10.10.11.3 "tail -3 ~/rpc-server_c.log 2>/dev/null | cut -c1-90" 2>/dev/null
echo "DONE"